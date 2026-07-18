#!/usr/bin/env python3
"""Reject bundled-deck references that still require external files or a network."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_FETCH_ATTRS = {
    "audio": ("src",),
    "embed": ("src",),
    "iframe": ("src",),
    "feimage": ("href", "xlink:href"),
    "image": ("href", "xlink:href"),
    "img": ("src", "srcset"),
    "input": ("src",),
    "object": ("data",),
    "script": ("src",),
    "source": ("src", "srcset"),
    "track": ("src",),
    "use": ("href", "xlink:href"),
    "video": ("src", "poster"),
}
_FETCHING_LINK_RELS = {
    "stylesheet",
    "icon",
    "preload",
    "modulepreload",
    "prefetch",
    "preconnect",
    "dns-prefetch",
    "manifest",
}
_LEGACY_BACKGROUND_TAGS = {"body", "table", "td", "th"}
_SVG_URL_ATTRS = {
    "clip-path",
    "cursor",
    "fill",
    "filter",
    "marker-end",
    "marker-mid",
    "marker-start",
    "mask",
    "stroke",
}
_CSS_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
_CSS_IMPORT_STRING_RE = re.compile(
    r"@import\s+(?!url\s*\()(['\"])(.*?)\1", re.I | re.S
)
_CSS_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
_MAX_SRCDOC_DEPTH = 20


def _is_embedded(reference: str) -> bool:
    value = reference.strip()
    return bool(value) and (value.startswith("#") or value.lower().startswith("data:"))


def _srcset_references(value: str) -> list[str]:
    """Return candidate URLs while preserving commas inside data URLs."""
    references: list[str] = []
    cursor = 0
    length = len(value)
    while cursor < length:
        while cursor < length and (value[cursor].isspace() or value[cursor] == ","):
            cursor += 1
        if cursor >= length:
            break
        is_data = value[cursor : cursor + 5].lower() == "data:"
        start = cursor
        while cursor < length and not value[cursor].isspace() and (
            is_data or value[cursor] != ","
        ):
            cursor += 1
        reference = value[start:cursor]
        references.append(reference.rstrip(","))
        if reference.endswith(","):
            continue
        while cursor < length and value[cursor] != ",":
            cursor += 1
        if cursor < length:
            cursor += 1
    return references


class _PortabilityParser(HTMLParser):
    def __init__(self, depth: int) -> None:
        super().__init__(convert_charrefs=True)
        self.errors: list[str] = []
        self._in_style = False
        self._depth = depth

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        values = {name.lower(): value or "" for name, value in attrs}
        line, _ = self.getpos()

        fetch_attrs = _FETCH_ATTRS.get(tag, ())
        if tag == "link":
            rels = set(values.get("rel", "").lower().split())
            if rels & _FETCHING_LINK_RELS:
                fetch_attrs = ("href",)
        if tag in _LEGACY_BACKGROUND_TAGS and "background" in values:
            fetch_attrs = (*fetch_attrs, "background")

        for attr in fetch_attrs:
            if attr not in values:
                continue
            references = (
                _srcset_references(values[attr]) if attr == "srcset" else [values[attr]]
            )
            if not references:
                references = [""]
            for reference in references:
                self._check(reference, f"<{tag}> {attr}", line)

        if "style" in values:
            self._check_css(values["style"], f"<{tag}> style", line)
        for attr in _SVG_URL_ATTRS:
            if attr in values:
                self._check_css(values[attr], f"<{tag}> {attr}", line)
        if tag == "iframe" and "srcdoc" in values:
            if self._depth >= _MAX_SRCDOC_DEPTH:
                self.errors.append(
                    f"line {line}: <iframe> srcdoc exceeds {_MAX_SRCDOC_DEPTH} nested levels"
                )
            else:
                nested_errors = validate_portability(
                    values["srcdoc"], _depth=self._depth + 1
                )
                self.errors.extend(
                    f"line {line}: <iframe> srcdoc: {error}" for error in nested_errors
                )
        if tag == "style":
            self._in_style = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            line, _ = self.getpos()
            self._check_css(data, "<style> url()", line)

    def _check_css(self, css: str, context: str, line: int) -> None:
        uncommented = _CSS_COMMENT_RE.sub("", css)
        for match in _CSS_URL_RE.finditer(uncommented):
            self._check(match.group(2), context, line)
        for match in _CSS_IMPORT_STRING_RE.finditer(uncommented):
            self._check(match.group(2), context + " @import", line)

    def _check(self, reference: str, context: str, line: int) -> None:
        if not _is_embedded(reference):
            self.errors.append(
                f"line {line}: {context} references non-embedded asset {reference!r}"
            )


def validate_portability(html: str, *, _depth: int = 0) -> list[str]:
    """Return portability errors for fetchable references not embedded as data URIs."""
    parser = _PortabilityParser(_depth)
    parser.feed(html)
    parser.close()
    return parser.errors
