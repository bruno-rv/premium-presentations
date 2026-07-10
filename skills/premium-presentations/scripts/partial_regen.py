#!/usr/bin/env python3
"""Plan stable-ID slide regeneration without mutating deck or spec files."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat as stat_module
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, NoReturn, Sequence

from slide_html import (
    SlideHtmlError,
    SlideSpan,
    assign_slide_ids,
    parse_json_script_span,
    parse_slide_spans,
)
from slide_spec import (
    ID_RE,
    SlideSpec,
    SlideSpecError,
    SlideSpecRow,
    canonical_fields,
    canonical_row,
    decoded_title,
    diff_rows,
    parse_slide_map,
    rewrite_slide_map_ids,
)


STATE_ID = "premium-regen-state"
STATE_KEYS = frozenset(
    {"version", "deck", "spec", "order", "envelopeHash", "slides"}
)
SLIDE_STATE_KEYS = frozenset({"row", "rowHash", "sectionHash"})
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

PLAN_REASONS = {
    "no_changes": ("no_changes", "none"),
    "changes": ("changes_planned", "spec_rows_changed"),
    "count": ("full_regeneration_required", "slide_count_changed"),
    "set": ("full_regeneration_required", "identity_set_changed"),
    "order": ("full_regeneration_required", "identity_order_changed"),
    "envelope": ("full_regeneration_required", "global_envelope_changed"),
    "drift": ("baseline_drift", "section_hash_changed"),
    "missing_id": ("full_regeneration_required", "missing_identity"),
    "duplicate_id": ("full_regeneration_required", "duplicate_identity"),
    "invalid_id": ("full_regeneration_required", "invalid_identity"),
}


class RegenInputError(ValueError):
    """Raised when a read-only regeneration input is unsafe or malformed."""


@dataclass(frozen=True)
class PlanResult:
    status: str
    reason_code: str
    changed: Mapping[str, tuple[str, ...]]
    messages: tuple[str, ...]


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _immutable_changed(
    changed: Mapping[str, tuple[str, ...]] | None = None,
) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType(dict(changed or {}))


def _result(
    reason: str,
    *,
    changed: Mapping[str, tuple[str, ...]] | None = None,
    messages: Sequence[str] = (),
) -> PlanResult:
    status, reason_code = PLAN_REASONS[reason]
    return PlanResult(
        status=status,
        reason_code=reason_code,
        changed=_immutable_changed(changed),
        messages=tuple(messages),
    )


def render_state(state: Mapping[str, object]) -> str:
    order = list(state["order"])
    source_slides = state["slides"]
    normalized = {
        "version": state["version"],
        "deck": state["deck"],
        "spec": state["spec"],
        "order": order,
        "envelopeHash": state["envelopeHash"],
        "slides": {
            slide_id: {
                "row": dict(sorted(source_slides[slide_id]["row"].items())),
                "rowHash": source_slides[slide_id]["rowHash"],
                "sectionHash": source_slides[slide_id]["sectionHash"],
            }
            for slide_id in order
        },
    }
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    return f'<script type="application/json" id="{STATE_ID}">{payload}</script>'


def _validate_basename(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "/" in value
        or "\\" in value
        or Path(value).is_absolute()
        or Path(value).name != value
    ):
        raise RegenInputError(f"state {label} must be a basename")
    return value


def _validate_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise RegenInputError(f"state {label} must be a SHA-256 label")
    return value


def _normalized_field_name(value: str) -> str:
    return " ".join(value.casefold().split())


def load_state(html: str) -> Mapping[str, object]:
    try:
        span = parse_json_script_span(html, STATE_ID)
        state = json.loads(span.content)
    except (SlideHtmlError, json.JSONDecodeError) as exc:
        raise RegenInputError(f"invalid premium regeneration state: {exc}") from exc

    if not isinstance(state, dict):
        raise RegenInputError("premium regeneration state must be an object")
    if set(state) != STATE_KEYS:
        raise RegenInputError("premium regeneration state has unexpected keys")
    if type(state["version"]) is not int or state["version"] != 1:
        raise RegenInputError("unsupported premium regeneration state")

    _validate_basename(state["deck"], "deck")
    _validate_basename(state["spec"], "spec")
    _validate_hash(state["envelopeHash"], "envelopeHash")

    order = state["order"]
    slides = state["slides"]
    if not isinstance(order, list) or any(
        not isinstance(slide_id, str) or not ID_RE.fullmatch(slide_id)
        for slide_id in order
    ):
        raise RegenInputError("state order must contain valid slide IDs")
    if len(order) != len(set(order)):
        raise RegenInputError("state order contains duplicate slide IDs")
    if not isinstance(slides, dict) or tuple(slides) != tuple(order):
        raise RegenInputError("state slides must exactly match the ordered IDs")

    for slide_id in order:
        slide = slides[slide_id]
        if not isinstance(slide, dict) or set(slide) != SLIDE_STATE_KEYS:
            raise RegenInputError(f"state slide {slide_id!r} has unexpected keys")
        row = slide["row"]
        if (
            not isinstance(row, dict)
            or any(not isinstance(key, str) for key in row)
            or any(not isinstance(value, str) for value in row.values())
            or any(_normalized_field_name(key) in {"#", "id"} for key in row)
        ):
            raise RegenInputError(f"state slide {slide_id!r} has an invalid row")
        row_hash = _validate_hash(slide["rowHash"], f"slide {slide_id!r} rowHash")
        _validate_hash(slide["sectionHash"], f"slide {slide_id!r} sectionHash")
        if row_hash != _sha256(canonical_fields(row)):
            raise RegenInputError(f"state slide {slide_id!r} row hash does not match")

    return state


def envelope_hash(html: str) -> str:
    try:
        replacements = [
            (span.start, span.end, f"<!--premium-slide:{ordinal}-->")
            for ordinal, span in enumerate(parse_slide_spans(html), 1)
        ]
        state_span = parse_json_script_span(html, STATE_ID)
    except SlideHtmlError as exc:
        raise RegenInputError(str(exc)) from exc
    replacements.append(
        (state_span.start, state_span.end, "<!--premium-regen-state-->")
    )
    masked = html
    for start, end, sentinel in sorted(replacements, reverse=True):
        masked = masked[:start] + sentinel + masked[end:]
    return _sha256(masked.encode("utf-8"))


def validate_pair(deck: Path, spec: Path) -> tuple[Path, Path]:
    for label, path in (("deck", deck), ("spec", spec)):
        mode = path.lstat().st_mode
        if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
            raise RegenInputError(
                f"{label} must be a regular non-symlink file: {path}"
            )
    if deck.resolve() == spec.resolve():
        raise RegenInputError("deck and spec must be distinct files")
    if deck.resolve().parent != spec.resolve().parent:
        raise RegenInputError("deck and spec must be in the same resolved directory")
    return deck.resolve(), spec.resolve()


def _select_init_ids(
    rows: Sequence[SlideSpecRow], spans: Sequence[SlideSpan]
) -> tuple[str, ...]:
    if len(rows) != len(spans):
        raise RegenInputError("deck/spec slide count mismatch")
    chosen: list[str] = []
    for ordinal, (row, span) in enumerate(zip(rows, spans), 1):
        spec_id = row.slide_id
        deck_id = span.slide_id
        if spec_id and deck_id and spec_id != deck_id:
            raise RegenInputError(
                f"conflicting IDs at slide {ordinal}: {spec_id!r} != {deck_id!r}"
            )
        candidate = deck_id or spec_id or f"slide-{ordinal}"
        if not ID_RE.fullmatch(candidate):
            raise RegenInputError(
                f"invalid slide ID at slide {ordinal}: {candidate!r}"
            )
        chosen.append(candidate)
    if len(set(chosen)) != len(chosen):
        raise RegenInputError("initialization would create duplicate slide IDs")
    return tuple(chosen)


def _semantic_row(row: SlideSpecRow) -> dict[str, str]:
    return {
        key: value
        for key, value in row.fields.items()
        if _normalized_field_name(key) not in {"#", "id"}
    }


def _insert_state(html: str, block: str) -> str:
    body_end = html.rfind("</body>")
    if body_end < 0:
        raise RegenInputError("deck is missing </body>")
    return html[:body_end] + block + html[body_end:]


def _ensure_state_absent(html: str) -> None:
    try:
        parse_json_script_span(html, STATE_ID)
    except SlideHtmlError as exc:
        if "not found" in str(exc):
            return
        raise RegenInputError(str(exc)) from exc
    raise RegenInputError("deck already contains premium regeneration state; use plan")


def _build_init_candidates(deck: Path, spec: Path) -> tuple[str, str, PlanResult]:
    deck, spec = validate_pair(Path(deck), Path(spec))
    deck_text = deck.read_text(encoding="utf-8")
    spec_text = spec.read_text(encoding="utf-8")
    _ensure_state_absent(deck_text)

    try:
        parsed_spec = parse_slide_map(spec_text)
        spans = parse_slide_spans(deck_text)
        ids = _select_init_ids(parsed_spec.rows, spans)
        for ordinal, (row, span) in enumerate(zip(parsed_spec.rows, spans), 1):
            if span.title != decoded_title(row):
                raise RegenInputError(
                    f"deck/spec title mismatch at slide {ordinal}: "
                    f"{span.title!r} != {decoded_title(row)!r}"
                )

        candidate_spec = rewrite_slide_map_ids(spec_text, ids)
        id_spec = parse_slide_map(candidate_spec, require_ids=True)
        deck_with_ids = assign_slide_ids(deck_text, ids)
        id_spans = parse_slide_spans(deck_with_ids)
    except (SlideSpecError, SlideHtmlError) as exc:
        raise RegenInputError(str(exc)) from exc

    slide_state = {
        row.slide_id: {
            "row": _semantic_row(row),
            "rowHash": _sha256(canonical_row(row)),
            "sectionHash": _sha256(span.raw.encode("utf-8")),
        }
        for row, span in zip(id_spec.rows, id_spans)
    }
    state: dict[str, object] = {
        "version": 1,
        "deck": deck.name,
        "spec": spec.name,
        "order": list(ids),
        "envelopeHash": "sha256:" + "0" * 64,
        "slides": slide_state,
    }
    provisional = _insert_state(deck_with_ids, render_state(state))
    state["envelopeHash"] = envelope_hash(provisional)
    provisional_span = parse_json_script_span(provisional, STATE_ID)
    final_block = render_state(state)
    candidate_deck = (
        provisional[: provisional_span.start]
        + final_block
        + provisional[provisional_span.end :]
    )

    result = PlanResult(
        status="initialization_preview",
        reason_code="identity_and_state_would_be_initialized",
        changed=_immutable_changed({slide_id: () for slide_id in ids}),
        messages=(
            "Read-only initialization preview; deck and spec were not modified.",
            "Proposed slide IDs: " + ", ".join(ids),
        ),
    )
    return candidate_deck, candidate_spec, result


def preview_init(deck: Path, spec: Path) -> PlanResult:
    _, _, result = _build_init_candidates(deck, spec)
    return result


def _baseline_spec(state: Mapping[str, object]) -> SlideSpec:
    order = state["order"]
    slides = state["slides"]
    semantic_headers: list[str] = []
    for slide_id in order:
        for header in slides[slide_id]["row"]:
            if header not in semantic_headers:
                semantic_headers.append(header)
    headers = ("#", "ID", *semantic_headers)
    rows = tuple(
        SlideSpecRow(
            slide_id=slide_id,
            ordinal=ordinal,
            fields=MappingProxyType(
                {
                    "#": str(ordinal),
                    "ID": slide_id,
                    **slides[slide_id]["row"],
                }
            ),
            line_no=0,
            raw_line="",
        )
        for ordinal, slide_id in enumerate(order, 1)
    )
    return SlideSpec(headers=headers, rows=rows, header_line_no=0, separator_line_no=0)


def _identity_result(reason: str, message: str) -> PlanResult:
    return _result(reason, messages=(message,))


def _check_unresolved_transaction(deck: Path) -> None:
    """Task 4 extends this read-only seam with durable journal detection."""


def plan_pair(
    deck: Path, spec: Path, *, check_transactions: bool = True
) -> PlanResult:
    deck_path = Path(deck)
    if check_transactions:
        _check_unresolved_transaction(deck_path)
    deck_path, spec_path = validate_pair(deck_path, Path(spec))
    deck_text = deck_path.read_text(encoding="utf-8")
    spec_text = spec_path.read_text(encoding="utf-8")
    state = load_state(deck_text)

    if state["deck"] != deck_path.name or state["spec"] != spec_path.name:
        raise RegenInputError("embedded state does not match deck/spec basenames")

    try:
        edited_spec = parse_slide_map(spec_text, require_ids=True)
    except SlideSpecError as exc:
        if exc.code in {"missing_id", "duplicate_id", "invalid_id"}:
            return _identity_result(exc.code, str(exc))
        raise RegenInputError(str(exc)) from exc

    expected_ids = tuple(state["order"])
    spec_ids = tuple(row.slide_id for row in edited_spec.rows)
    if len(spec_ids) != len(expected_ids):
        return _identity_result("count", "Slide count changed from embedded state.")
    if set(spec_ids) != set(expected_ids):
        return _identity_result("set", "Spec slide identity set changed.")
    if spec_ids != expected_ids:
        return _identity_result("order", "Spec slide identity order changed.")

    try:
        spans = parse_slide_spans(deck_text)
    except SlideHtmlError as exc:
        if str(exc).startswith("duplicate slide ID"):
            return _identity_result("duplicate_id", str(exc))
        raise RegenInputError(str(exc)) from exc
    deck_ids = tuple(span.slide_id for span in spans)
    if any(not slide_id for slide_id in deck_ids):
        return _identity_result("missing_id", "Deck contains a slide without an ID.")
    if any(not ID_RE.fullmatch(slide_id) for slide_id in deck_ids):
        return _identity_result("invalid_id", "Deck contains an invalid slide ID.")
    if len(deck_ids) != len(expected_ids):
        return _identity_result("count", "Deck slide count changed from embedded state.")
    if set(deck_ids) != set(expected_ids):
        return _identity_result("set", "Deck slide identity set changed.")
    if deck_ids != expected_ids:
        return _identity_result("order", "Deck slide identity order changed.")

    if envelope_hash(deck_text) != state["envelopeHash"]:
        return _identity_result(
            "envelope", "Deck markup outside authored slides changed."
        )

    for span in spans:
        expected_hash = state["slides"][span.slide_id]["sectionHash"]
        if _sha256(span.raw.encode("utf-8")) != expected_hash:
            return _identity_result(
                "drift", f"Slide {span.slide_id!r} changed outside this workflow."
            )

    difference = diff_rows(_baseline_spec(state), edited_spec)
    if difference.structural_reasons:
        reason_by_code = {
            "slide_count_changed": "count",
            "identity_set_changed": "set",
            "identity_order_changed": "order",
        }
        return _identity_result(
            reason_by_code[difference.structural_reasons[0]],
            difference.structural_reasons[0].replace("_", " ").capitalize() + ".",
        )
    if not difference.changes:
        return _result("no_changes", messages=("No spec row changes detected.",))

    changed = {
        change.slide_id: change.fields for change in difference.changes
    }
    return _result(
        "changes",
        changed=changed,
        messages=(
            "Claude Code or Codex should generate one fragment per changed ID.",
            "Use the apply argument shape --fragment ID=FILE for every changed ID.",
        ),
    )


class RegenArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise RegenInputError(message)


def _parser() -> RegenArgumentParser:
    parser = RegenArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="preview initialization")
    init_parser.add_argument("--deck", type=Path, required=True)
    init_parser.add_argument("--spec", type=Path, required=True)

    plan_parser = commands.add_parser("plan", help="plan changed slide fragments")
    plan_parser.add_argument("--deck", type=Path, required=True)
    plan_parser.add_argument("--spec", type=Path, required=True)
    plan_parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _exit_for(result: PlanResult) -> int:
    if result.status == "full_regeneration_required":
        return 2
    if result.status == "baseline_drift":
        return 3
    return 0


def _print_json(result: PlanResult) -> None:
    payload = {
        "status": result.status,
        "reasonCode": result.reason_code,
        "changed": {key: list(value) for key, value in result.changed.items()},
        "messages": list(result.messages),
    }
    print(json.dumps(payload, sort_keys=False, separators=(",", ":")))


def _print_human(result: PlanResult) -> None:
    print(f"{result.status}: {result.reason_code}")
    for slide_id, fields in result.changed.items():
        detail = ", ".join(fields) if fields else "assign stable identity"
        print(f"- {slide_id}: {detail}")
    for message in result.messages:
        print(message)


def _error_result(message: str) -> PlanResult:
    return PlanResult(
        status="error",
        reason_code="invalid_input",
        changed=_immutable_changed(),
        messages=(message,),
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    json_requested = bool(
        arguments and arguments[0] == "plan" and "--json" in arguments
    )
    try:
        options = _parser().parse_args(arguments)
        if options.command == "init":
            result = preview_init(options.deck, options.spec)
        else:
            result = plan_pair(options.deck, options.spec)
    except SystemExit as exc:
        return int(exc.code)
    except (RegenInputError, OSError, UnicodeError) as exc:
        result = _error_result(str(exc))
        if json_requested:
            _print_json(result)
        else:
            _print_human(result)
        return 1

    if getattr(options, "as_json", False):
        _print_json(result)
    else:
        _print_human(result)
    return _exit_for(result)


if __name__ == "__main__":
    raise SystemExit(main())
