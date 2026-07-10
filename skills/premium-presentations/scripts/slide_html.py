#!/usr/bin/env python3
"""Parse and safely replace authored slide HTML without rewriting the deck."""

from __future__ import annotations

import html as html_lib
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Mapping, Sequence

from slide_spec import ID_RE, SlideSpecRow, decoded_title


FORBIDDEN_TAGS = frozenset({"html", "head", "body", "script", "style", "link"})
FORBIDDEN_IDS = frozenset(
    {"deck", "controls", "presenter-popup", "premium-regen-state", "glossary"}
)
FORBIDDEN_CLASSES = frozenset(
    {"premium-controller", "presenter-popup", "presenter-controls"}
)
SCRIPT_URL_ATTRIBUTES = frozenset(
    {"href", "src", "action", "formaction", "xlink:href"}
)
VOID_ELEMENTS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


class SlideHtmlError(ValueError):
    pass


@dataclass(frozen=True)
class SlideSpan:
    slide_id: str
    title: str
    start: int
    end: int
    raw: str


@dataclass(frozen=True)
class JsonScriptSpan:
    element_id: str
    start: int
    end: int
    content_start: int
    content_end: int
    content: str
    inside_deck: bool


@dataclass(frozen=True)
class _SlideRecord:
    span: SlideSpan
    start_tag_end: int


def _class_tokens(attrs: list[tuple[str, str | None]]) -> set[str]:
    values = [value or "" for name, value in attrs if name.casefold() == "class"]
    return {token for value in values for token in value.split()}


def _attrs(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, value in attrs:
        values.setdefault(name.casefold(), value or "")
    return values


def _duplicate_attributes(attrs: list[tuple[str, str | None]]) -> list[str]:
    names = [name.casefold() for name, _ in attrs]
    return list(dict.fromkeys(name for name in names if names.count(name) > 1))


class _OffsetParser(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=False)
        self.source = source
        self._line_starts = [0]
        self._line_starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._line_starts[line - 1] + column

    def _start_tag_end(self) -> int:
        raw = self.get_starttag_text()
        if raw is None:
            raise SlideHtmlError("could not locate start tag")
        return self._offset() + len(raw)

    def _end_tag_end(self) -> int:
        end = self.source.find(">", self._offset())
        if end < 0:
            raise SlideHtmlError("unterminated end tag")
        return end + 1


class _SlideParser(_OffsetParser):
    def __init__(self, source: str) -> None:
        super().__init__(source)
        self.stack: list[tuple[str, bool]] = []
        self.deck_count = 0
        self.active: dict[str, object] | None = None
        self.records: list[_SlideRecord] = []
        self.seen_ids: set[str] = set()

    def _inside_deck(self) -> bool:
        return any(is_deck for _, is_deck in self.stack)

    def _direct_child_of_deck(self) -> bool:
        return bool(self.stack and self.stack[-1][1])

    def _start(self, tag: str, attrs: list[tuple[str, str | None]], self_closing: bool) -> None:
        tag = tag.casefold()
        values = _attrs(attrs)
        classes = _class_tokens(attrs)
        is_deck = tag == "div" and values.get("id") == "deck"
        if is_deck:
            self.deck_count += 1
            if self.deck_count > 1:
                raise SlideHtmlError("multiple div#deck roots")

        is_slide = tag == "section" and "slide" in classes
        if is_slide:
            duplicates = _duplicate_attributes(attrs)
            if duplicates:
                raise SlideHtmlError(
                    f"slide tag contains duplicate attribute {duplicates[0]!r}"
                )
            if self_closing:
                raise SlideHtmlError("slide sections must not be self-closing")
            if self.active is not None:
                raise SlideHtmlError("slide sections must not be nested")
            if not self._direct_child_of_deck():
                raise SlideHtmlError("slide sections must be direct children of div#deck")

            slide_id = values.get("id", "")
            if slide_id and slide_id in self.seen_ids:
                raise SlideHtmlError(f"duplicate slide ID {slide_id!r}")
            if slide_id:
                self.seen_ids.add(slide_id)
            self.active = {
                "slide_id": slide_id,
                "title": values.get("data-nav-title", ""),
                "start": self._offset(),
                "start_tag_end": self._start_tag_end(),
                "section_depth": 1,
            }
        elif self.active is not None and tag == "section" and not self_closing:
            self.active["section_depth"] = int(self.active["section_depth"]) + 1

        if not self_closing and tag not in VOID_ELEMENTS:
            self.stack.append((tag, is_deck))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs, True)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if self.active is not None and tag == "section":
            depth = int(self.active["section_depth"]) - 1
            self.active["section_depth"] = depth
            if depth == 0:
                start = int(self.active["start"])
                end = self._end_tag_end()
                span = SlideSpan(
                    slide_id=str(self.active["slide_id"]),
                    title=str(self.active["title"]),
                    start=start,
                    end=end,
                    raw=self.source[start:end],
                )
                self.records.append(
                    _SlideRecord(span=span, start_tag_end=int(self.active["start_tag_end"]))
                )
                self.active = None

        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def _parse_slide_records(source: str) -> list[_SlideRecord]:
    parser = _SlideParser(source)
    parser.feed(source)
    parser.close()
    if parser.deck_count == 0:
        raise SlideHtmlError("missing div#deck root")
    if parser.active is not None:
        raise SlideHtmlError("unclosed slide section")
    return parser.records


def parse_slide_spans(html: str) -> list[SlideSpan]:
    return [record.span for record in _parse_slide_records(html)]


@dataclass
class _PendingJsonScript:
    start: int
    content_start: int
    inside_deck: bool


class _JsonScriptParser(_OffsetParser):
    def __init__(self, source: str, element_id: str) -> None:
        super().__init__(source)
        self.element_id = element_id
        self.stack: list[tuple[str, bool]] = []
        self.pending: _PendingJsonScript | None = None
        self.matches: list[JsonScriptSpan] = []

    def _inside_deck(self) -> bool:
        return any(is_deck for _, is_deck in self.stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = _attrs(attrs)
        is_deck = tag == "div" and values.get("id") == "deck"
        if (
            tag == "script"
            and values.get("id") == self.element_id
            and values.get("type") == "application/json"
        ):
            self.pending = _PendingJsonScript(
                start=self._offset(),
                content_start=self._start_tag_end(),
                inside_deck=self._inside_deck(),
            )
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, is_deck))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag.casefold():
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == "script" and self.pending is not None:
            content_end = self._offset()
            end = self._end_tag_end()
            self.matches.append(
                JsonScriptSpan(
                    element_id=self.element_id,
                    start=self.pending.start,
                    end=end,
                    content_start=self.pending.content_start,
                    content_end=content_end,
                    content=self.source[self.pending.content_start : content_end],
                    inside_deck=self.pending.inside_deck,
                )
            )
            self.pending = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


def parse_json_script_span(html: str, element_id: str) -> JsonScriptSpan:
    parser = _JsonScriptParser(html, element_id)
    parser.feed(html)
    parser.close()
    if parser.pending is not None:
        raise SlideHtmlError(f"unclosed JSON script {element_id!r}")
    if not parser.matches:
        raise SlideHtmlError(f"JSON script {element_id!r} not found")
    if len(parser.matches) > 1:
        raise SlideHtmlError(f"multiple JSON scripts found for {element_id!r}")
    match = parser.matches[0]
    if match.inside_deck:
        raise SlideHtmlError(f"JSON script {element_id!r} must not be inside #deck")
    return match


def assign_slide_ids(html: str, ids: Sequence[str]) -> str:
    records = _parse_slide_records(html)
    validated = tuple(ids)
    if len(validated) != len(records):
        raise SlideHtmlError(
            f"expected {len(records)} slide IDs, received {len(validated)}"
        )
    if any(not isinstance(slide_id, str) or not ID_RE.fullmatch(slide_id) for slide_id in validated):
        raise SlideHtmlError("slide IDs must contain only letters, digits, underscores, and hyphens")
    if len(set(validated)) != len(validated):
        raise SlideHtmlError("slide IDs must be unique")

    insertions: list[tuple[int, str]] = []
    for record, requested_id in zip(records, validated):
        current_id = record.span.slide_id
        if current_id:
            if not ID_RE.fullmatch(current_id):
                raise SlideHtmlError(f"existing slide ID {current_id!r} is malformed")
            if current_id != requested_id:
                raise SlideHtmlError(
                    f"existing slide ID {current_id!r} does not match {requested_id!r}"
                )
            continue
        insertions.append(
            (record.start_tag_end - 1, f' id="{html_lib.escape(requested_id, quote=True)}"')
        )

    output = html
    for offset, insertion in reversed(insertions):
        output = output[:offset] + insertion + output[offset:]
    return output


def splice_sections(source: str, replacements: Mapping[str, str]) -> str:
    spans = parse_slide_spans(source)
    by_id = {span.slide_id: span for span in spans}
    missing = sorted(set(replacements) - set(by_id))
    if missing:
        raise SlideHtmlError(f"replacement IDs not present in deck: {', '.join(missing)}")
    output = source
    for slide_id in sorted(replacements, key=lambda key: by_id[key].start, reverse=True):
        span = by_id[slide_id]
        output = output[: span.start] + replacements[slide_id] + output[span.end :]
    return output


class _FragmentInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.stack: list[str] = []
        self.root_count = 0
        self.root_tag = ""
        self.root_classes: frozenset[str] = frozenset()
        self.root_id = ""
        self.root_title = ""
        self.direct_children: list[tuple[str, frozenset[str]]] = []
        self.direct_notes = 0
        self.outside_errors: list[str] = []
        self.forbidden_tag_errors: list[str] = []
        self.forbidden_control_errors: list[str] = []
        self.markup_errors: list[str] = []

    @staticmethod
    def _append_once(errors: list[str], message: str) -> None:
        if message not in errors:
            errors.append(message)

    def _inspect_start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = _attrs(attrs)
        classes = frozenset(_class_tokens(attrs))
        depth = len(self.stack)
        if depth == 0:
            self.root_count += 1
            if self.root_count == 1:
                self.root_tag = tag
                self.root_classes = classes
                self.root_id = values.get("id", "")
                self.root_title = values.get("data-nav-title", "")
        elif depth == 1:
            self.direct_children.append((tag, classes))
            if tag == "aside" and "notes" in classes:
                self.direct_notes += 1

        if tag in FORBIDDEN_TAGS:
            self._append_once(self.forbidden_tag_errors, f"forbidden tag <{tag}>")

        for name in _duplicate_attributes(attrs):
            self._append_once(
                self.forbidden_control_errors, f"duplicate attribute {name!r}"
            )
        for name, value in attrs:
            normalized_name = name.casefold()
            if normalized_name.startswith("on"):
                self._append_once(
                    self.forbidden_control_errors,
                    f"forbidden event-handler attribute {normalized_name!r}",
                )
            normalized_value = "".join((value or "").split()).casefold()
            if (
                normalized_name in SCRIPT_URL_ATTRIBUTES
                and normalized_value.startswith("javascript:")
            ):
                self._append_once(
                    self.forbidden_control_errors,
                    f"javascript: URL in attribute {normalized_name!r}",
                )

        element_id = values.get("id", "")
        if element_id in FORBIDDEN_IDS:
            self._append_once(
                self.forbidden_control_errors, f"forbidden control id {element_id!r}"
            )
        for class_name in sorted(classes & FORBIDDEN_CLASSES):
            self._append_once(
                self.forbidden_control_errors,
                f"forbidden control class {class_name!r}",
            )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_start(tag, attrs)
        if tag.casefold() not in VOID_ELEMENTS:
            self.stack.append(tag.casefold())

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._inspect_start(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if not self.stack or self.stack[-1] != tag:
            self._append_once(
                self.markup_errors, "fragment contains unclosed or mismatched markup"
            )
            if tag in self.stack:
                del self.stack[self.stack.index(tag) :]
            return
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if not self.stack and data.strip():
            self._append_once(
                self.outside_errors, "fragment contains content outside the root element"
            )

    def handle_comment(self, data: str) -> None:
        if not self.stack:
            self._append_once(
                self.outside_errors, "fragment contains content outside the root element"
            )

    def handle_decl(self, decl: str) -> None:
        if not self.stack:
            self._append_once(
                self.outside_errors, "fragment contains content outside the root element"
            )

    def handle_pi(self, data: str) -> None:
        if not self.stack:
            self._append_once(
                self.outside_errors, "fragment contains content outside the root element"
            )


def validate_fragment(fragment: str, expected: SlideSpecRow) -> list[str]:
    inspector = _FragmentInspector()
    inspector.feed(fragment)
    inspector.close()
    if inspector.stack:
        inspector._append_once(
            inspector.markup_errors, "fragment contains unclosed or mismatched markup"
        )

    errors: list[str] = list(inspector.outside_errors)
    if (
        inspector.root_count != 1
        or inspector.root_tag != "section"
        or "slide" not in inspector.root_classes
    ):
        errors.append("fragment must contain exactly one top-level section.slide")
    if inspector.root_id != expected.slide_id:
        errors.append(f"fragment id must be {expected.slide_id!r}")
    expected_title = decoded_title(expected)
    if inspector.root_title != expected_title:
        errors.append(f"data-nav-title must equal decoded Title {expected_title!r}")
    errors.extend(inspector.forbidden_tag_errors)
    errors.extend(inspector.forbidden_control_errors)
    if inspector.direct_notes != 1:
        errors.append("fragment must contain exactly one direct aside.notes")
    final_tag, final_classes = (
        inspector.direct_children[-1]
        if inspector.direct_children
        else ("", frozenset())
    )
    if final_tag != "aside" or "notes" not in final_classes:
        errors.append("aside.notes must be the final direct child element")
    errors.extend(inspector.markup_errors)
    return list(dict.fromkeys(errors))
