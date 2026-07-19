#!/usr/bin/env python3
"""Parse and compare Slide Map tables in presentation specifications."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence


ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
SLIDE_MAP_HEADING_RE = re.compile(r"^##(?!#)\s*Slide Map\b", re.IGNORECASE)
H2_RE = re.compile(r"^##(?!#)")
SEPARATOR_RE = re.compile(r":?-{3,}:?\Z")

# Slide Budget grammar (Tier 2). Budget (ms) is authoritative: a decimal
# integer, no sign/whitespace, min 1,000 (sub-second budgets rejected), max
# 7,200,000 (2h/slide), and within JS safe-integer range. Budget (mm:ss) is a
# derived display that must equal floor(ms/1000) zero-padded. Both bounds are
# enforced identically by the JS counterpart in premium-presenter.js against
# the same shared JSON vectors (scripts/tests/budget-vectors.json).
BUDGET_MS_MIN = 1_000
BUDGET_MS_MAX = 7_200_000
BUDGET_MS_SAFE_MAX = 2**53 - 1  # Number.MAX_SAFE_INTEGER
BUDGET_MS_RE = re.compile(r"[0-9]+\Z")
BUDGET_MMSS_RE = re.compile(r"[0-9]{2,}:[0-5][0-9]\Z")
BUDGET_MMSS_HEADER = "budget (mm:ss)"
BUDGET_MS_HEADER = "budget (ms)"


class SlideSpecError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SlideSpecRow:
    slide_id: str
    ordinal: int
    fields: Mapping[str, str]
    line_no: int
    raw_line: str


@dataclass(frozen=True)
class SlideSpec:
    headers: tuple[str, ...]
    rows: tuple[SlideSpecRow, ...]
    header_line_no: int
    separator_line_no: int


@dataclass(frozen=True)
class RowChange:
    slide_id: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class SpecDiff:
    changes: tuple[RowChange, ...]
    structural_reasons: tuple[str, ...]


@dataclass(frozen=True)
class _TableLocation:
    header_index: int
    separator_index: int
    row_indices: tuple[int, ...]
    section_end: int


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _line_body(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith(("\n", "\r")):
        return line[:-1]
    return line


def _pipe_boundaries(line: str) -> list[int]:
    boundaries: list[int] = []
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            boundaries.append(index)
    return boundaries


def _split_pipe_row(line: str) -> list[str]:
    boundaries = _pipe_boundaries(line)
    if (
        len(boundaries) < 2
        or line[: boundaries[0]].strip()
        or line[boundaries[-1] + 1 :].strip()
    ):
        raise SlideSpecError(
            "malformed_row",
            "Slide Map rows must start and end with an unescaped pipe",
        )
    cells: list[str] = []
    for start, end in zip(boundaries, boundaries[1:]):
        raw = line[start + 1 : end].strip()
        cells.append(re.sub(r"\\([\\|])", r"\1", raw))
    return cells


def _is_pipe_row(line: str) -> bool:
    boundaries = _pipe_boundaries(line)
    return bool(
        len(boundaries) >= 2
        and not line[: boundaries[0]].strip()
        and not line[boundaries[-1] + 1 :].strip()
    )


def _looks_like_table_row(line: str) -> bool:
    return bool(line.lstrip().startswith("|") or re.match(r"^\s*\d+\s*\|", line))


def _find_header(lines: list[str], start: int, end: int) -> int | None:
    found: int | None = None
    for index in range(start, end):
        body = _line_body(lines[index])
        if not _is_pipe_row(body):
            continue
        cells = _split_pipe_row(body)
        if cells and _normalized(cells[0]) == "#":
            found = index
    return found


def _locate_table(lines: list[str]) -> _TableLocation:
    heading_indices = [
        index
        for index, line in enumerate(lines)
        if SLIDE_MAP_HEADING_RE.match(_line_body(line))
    ]

    if heading_indices:
        heading_index = heading_indices[-1]
        start = heading_index + 1
        end = len(lines)
        for index in range(start, len(lines)):
            if H2_RE.match(_line_body(lines[index])):
                end = index
                break
        header_index = _find_header(lines, start, end)
        if header_index is None:
            if any(
                _looks_like_table_row(_line_body(lines[index]))
                and not _is_pipe_row(_line_body(lines[index]))
                for index in range(start, end)
            ):
                raise SlideSpecError(
                    "malformed_row",
                    "Slide Map contains a malformed pipe table row",
                )
            if any(_is_pipe_row(_line_body(lines[index])) for index in range(start, end)):
                raise SlideSpecError(
                    "missing_header",
                    "Slide Map table is missing a leading # column",
                )
            raise SlideSpecError("no_slide_map", "no Slide Map table found")
        section_end = end
    else:
        header_index = _find_header(lines, 0, len(lines))
        if header_index is None:
            raise SlideSpecError("no_slide_map", "no Slide Map table found")
        section_end = len(lines)
        for index in range(header_index + 1, len(lines)):
            body = _line_body(lines[index])
            if not body.strip() or _is_pipe_row(body) or _looks_like_table_row(body):
                continue
            section_end = index
            break

    separator_index = header_index + 1
    if separator_index >= section_end:
        raise SlideSpecError(
            "malformed_row",
            "Slide Map header is missing its separator row",
        )

    separator = _line_body(lines[separator_index])
    if not _is_pipe_row(separator):
        raise SlideSpecError(
            "malformed_row",
            "Slide Map header must be followed by a separator row",
        )

    row_indices: list[int] = []
    for index in range(separator_index + 1, section_end):
        body = _line_body(lines[index])
        if not _is_pipe_row(body):
            if _looks_like_table_row(body):
                raise SlideSpecError(
                    "malformed_row",
                    f"Slide Map row on line {index + 1} is not a valid pipe table row",
                )
            continue
        cells = _split_pipe_row(body)
        if not cells or not cells[0].strip().isdigit():
            raise SlideSpecError(
                "malformed_row",
                f"Slide Map row on line {index + 1} has a non-numeric ordinal",
            )
        row_indices.append(index)

    if not row_indices:
        raise SlideSpecError("malformed_row", "Slide Map table has no data rows")

    return _TableLocation(
        header_index=header_index,
        separator_index=separator_index,
        row_indices=tuple(row_indices),
        section_end=section_end,
    )


def _parse_with_location(
    text: str, *, require_ids: bool = False
) -> tuple[SlideSpec, _TableLocation, list[str]]:
    lines = text.splitlines(keepends=True)
    location = _locate_table(lines)

    headers = tuple(_split_pipe_row(_line_body(lines[location.header_index])))
    normalized_headers = tuple(_normalized(header) for header in headers)
    if len(set(normalized_headers)) != len(normalized_headers):
        raise SlideSpecError(
            "duplicate_header",
            "Slide Map contains duplicate normalized headers",
        )
    if not normalized_headers or normalized_headers[0] != "#":
        raise SlideSpecError(
            "missing_header",
            "Slide Map table is missing a leading # column",
        )
    id_index = normalized_headers.index("id") if "id" in normalized_headers else None
    if id_index is not None and id_index != 1:
        raise SlideSpecError(
            "invalid_id_column",
            "Slide Map ID column must appear immediately after #",
        )

    separator = _split_pipe_row(_line_body(lines[location.separator_index]))
    if len(separator) != len(headers) or any(
        not SEPARATOR_RE.fullmatch(cell) for cell in separator
    ):
        raise SlideSpecError(
            "malformed_row",
            "Slide Map separator width or syntax does not match its header",
        )

    rows: list[SlideSpecRow] = []
    seen_ids: set[str] = set()
    for expected_ordinal, index in enumerate(location.row_indices, start=1):
        raw_line = _line_body(lines[index])
        cells = _split_pipe_row(raw_line)
        if len(cells) != len(headers):
            raise SlideSpecError(
                "malformed_row",
                f"Slide Map row on line {index + 1} has {len(cells)} cells; expected {len(headers)}",
            )
        try:
            ordinal = int(cells[0])
        except ValueError as exc:
            raise SlideSpecError(
                "malformed_row",
                f"Slide Map row on line {index + 1} has a non-numeric ordinal",
            ) from exc
        if ordinal != expected_ordinal:
            raise SlideSpecError(
                "malformed_row",
                f"Slide Map ordinals must be sequential from 1; found {ordinal} on line {index + 1}",
            )

        slide_id = cells[id_index] if id_index is not None else ""
        if not slide_id and require_ids:
            raise SlideSpecError(
                "missing_id",
                f"Slide Map row {ordinal} is missing an ID",
            )
        if slide_id and not ID_RE.fullmatch(slide_id):
            raise SlideSpecError(
                "invalid_id",
                f"Slide Map row {ordinal} has invalid ID {slide_id!r}",
            )
        if slide_id in seen_ids:
            raise SlideSpecError(
                "duplicate_id",
                f"Slide Map contains duplicate ID {slide_id!r}",
            )
        if slide_id:
            seen_ids.add(slide_id)

        fields = MappingProxyType(dict(zip(headers, cells)))
        rows.append(
            SlideSpecRow(
                slide_id=slide_id,
                ordinal=ordinal,
                fields=fields,
                line_no=index + 1,
                raw_line=raw_line,
            )
        )

    return (
        SlideSpec(
            headers=headers,
            rows=tuple(rows),
            header_line_no=location.header_index + 1,
            separator_line_no=location.separator_index + 1,
        ),
        location,
        lines,
    )


def parse_slide_map(text: str, *, require_ids: bool = False) -> SlideSpec:
    spec, _, _ = _parse_with_location(text, require_ids=require_ids)
    return spec


def format_budget_mmss(ms: int) -> str:
    """Format ms as the derived mm:ss display: floor(ms/1000), zero-padded."""
    total_seconds = ms // 1000
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def validate_budget_ms(value: str) -> int:
    """Validate a Budget (ms) cell: decimal integer, no sign/whitespace, in range."""
    if not isinstance(value, str) or not BUDGET_MS_RE.fullmatch(value):
        raise SlideSpecError(
            "invalid_budget_ms",
            f"Budget (ms) must be a decimal integer with no sign or whitespace: {value!r}",
        )
    ms = int(value)
    if not (-BUDGET_MS_SAFE_MAX <= ms <= BUDGET_MS_SAFE_MAX):
        raise SlideSpecError(
            "invalid_budget_ms",
            f"Budget (ms) {value!r} exceeds JS safe-integer range",
        )
    if not (BUDGET_MS_MIN <= ms <= BUDGET_MS_MAX):
        raise SlideSpecError(
            "invalid_budget_ms",
            f"Budget (ms) {ms} is out of range [{BUDGET_MS_MIN}, {BUDGET_MS_MAX}]",
        )
    return ms


def validate_budget_mmss(value: str, ms: int) -> None:
    """Validate a Budget (mm:ss) cell matches the grammar and equals floor(ms/1000)."""
    if not isinstance(value, str) or not BUDGET_MMSS_RE.fullmatch(value):
        raise SlideSpecError(
            "invalid_budget_mmss",
            r"Budget (mm:ss) must match ^\d{2,}:[0-5]\d$: " + repr(value),
        )
    expected = format_budget_mmss(ms)
    if value != expected:
        raise SlideSpecError(
            "budget_mismatch",
            f"Budget (mm:ss) {value!r} does not equal floor(ms/1000) for {ms} ms "
            f"({expected!r})",
        )


@dataclass(frozen=True)
class SlideBudget:
    slide_id: str
    ordinal: int
    ms: int


@dataclass(frozen=True)
class BudgetColumns:
    state: str  # "budgetless" | "budgeted"
    budgets: tuple[SlideBudget, ...]


def parse_budget_columns(spec: SlideSpec) -> BudgetColumns:
    """Three-state Slide Budget column rule (atomic header pair):

    (a) headers absent, or headers present with ALL budget cells empty ->
        budgetless (no gate, no runtime budgets);
    (b) headers present and EVERY row populated with valid values -> budgeted;
    (c) anything else (one header without the other, any populated subset,
        any invalid value) -> validation failure.
    """
    normalized_headers = [_normalized(header) for header in spec.headers]
    has_mmss = BUDGET_MMSS_HEADER in normalized_headers
    has_ms = BUDGET_MS_HEADER in normalized_headers
    if not has_mmss and not has_ms:
        return BudgetColumns(state="budgetless", budgets=())
    if has_mmss != has_ms:
        raise SlideSpecError(
            "budget_header_mismatch",
            "Budget (mm:ss) and Budget (ms) columns must both be present or both absent",
        )

    mmss_header = spec.headers[normalized_headers.index(BUDGET_MMSS_HEADER)]
    ms_header = spec.headers[normalized_headers.index(BUDGET_MS_HEADER)]

    populated: list[SlideSpecRow] = []
    empty: list[SlideSpecRow] = []
    for row in spec.rows:
        mmss_cell = row.fields[mmss_header].strip()
        ms_cell = row.fields[ms_header].strip()
        if not mmss_cell and not ms_cell:
            empty.append(row)
        elif mmss_cell and ms_cell:
            populated.append(row)
        else:
            raise SlideSpecError(
                "budget_row_partial",
                f"Slide Map row {row.ordinal} has only one of Budget (mm:ss)/"
                "Budget (ms) populated",
            )

    if populated and empty:
        raise SlideSpecError(
            "budget_row_mixed",
            "Slide Map budget columns must be all-populated or all-empty across "
            "every row",
        )
    if not populated:
        return BudgetColumns(state="budgetless", budgets=())

    budgets: list[SlideBudget] = []
    for row in spec.rows:
        ms = validate_budget_ms(row.fields[ms_header].strip())
        validate_budget_mmss(row.fields[mmss_header].strip(), ms)
        budgets.append(SlideBudget(slide_id=row.slide_id, ordinal=row.ordinal, ms=ms))
    return BudgetColumns(state="budgeted", budgets=tuple(budgets))


def canonical_fields(fields: Mapping[str, str]) -> bytes:
    semantic = {
        key: value
        for key, value in fields.items()
        if _normalized(key) not in {"#", "id"}
    }
    return json.dumps(
        semantic,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_row(row: SlideSpecRow) -> bytes:
    return canonical_fields(row.fields)


def decoded_title(row: SlideSpecRow) -> str:
    return html.unescape(row.fields.get("Title", ""))


def _semantic_by_normalized_name(row: SlideSpecRow) -> dict[str, str]:
    return {
        _normalized(key): value
        for key, value in row.fields.items()
        if _normalized(key) not in {"#", "id"}
    }


def diff_rows(baseline: SlideSpec, edited: SlideSpec) -> SpecDiff:
    baseline_ids = tuple(row.slide_id for row in baseline.rows)
    edited_ids = tuple(row.slide_id for row in edited.rows)
    structural_reasons: list[str] = []
    if len(baseline_ids) != len(edited_ids):
        structural_reasons.append("slide_count_changed")
    if set(baseline_ids) != set(edited_ids):
        structural_reasons.append("identity_set_changed")
    elif baseline_ids != edited_ids:
        structural_reasons.append("identity_order_changed")

    if structural_reasons:
        return SpecDiff(changes=(), structural_reasons=tuple(structural_reasons))

    baseline_by_id = {row.slide_id: row for row in baseline.rows}
    baseline_headers = [
        header for header in baseline.headers if _normalized(header) not in {"#", "id"}
    ]
    edited_headers = [
        header for header in edited.headers if _normalized(header) not in {"#", "id"}
    ]
    edited_header_names = {_normalized(header) for header in edited_headers}
    comparison_headers = edited_headers + [
        header
        for header in baseline_headers
        if _normalized(header) not in edited_header_names
    ]
    changes: list[RowChange] = []
    for edited_row in edited.rows:
        baseline_values = _semantic_by_normalized_name(baseline_by_id[edited_row.slide_id])
        edited_values = _semantic_by_normalized_name(edited_row)
        changed_fields = tuple(
            header
            for header in comparison_headers
            if baseline_values.get(_normalized(header)) != edited_values.get(_normalized(header))
        )
        if changed_fields:
            changes.append(RowChange(slide_id=edited_row.slide_id, fields=changed_fields))

    return SpecDiff(changes=tuple(changes), structural_reasons=())


def _insert_after_first_cell(line: str, value: str) -> str:
    boundaries = _pipe_boundaries(line)
    if len(boundaries) < 2:
        raise SlideSpecError(
            "malformed_row",
            "Cannot add ID column to malformed Slide Map row",
        )
    escaped = value.replace("\\", "\\\\").replace("|", "\\|")
    close = boundaries[1]
    return f"{line[:close + 1]} {escaped} |{line[close + 1:]}"


def _replace_cell(line: str, cell_index: int, value: str) -> str:
    boundaries = _pipe_boundaries(line)
    if cell_index + 1 >= len(boundaries):
        raise SlideSpecError(
            "malformed_row",
            "Cannot replace ID in malformed Slide Map row",
        )
    start = boundaries[cell_index]
    end = boundaries[cell_index + 1]
    return f"{line[:start + 1]} {value} {line[end:]}"


def _replace_line_body(line: str, body: str) -> str:
    return body + line[len(_line_body(line)) :]


def _validate_ids(ids: Sequence[str], expected_count: int) -> tuple[str, ...]:
    validated = tuple(ids)
    if len(validated) != expected_count:
        raise SlideSpecError(
            "id_count_mismatch",
            f"Expected {expected_count} slide IDs, received {len(validated)}",
        )
    for slide_id in validated:
        if not isinstance(slide_id, str) or not ID_RE.fullmatch(slide_id):
            raise SlideSpecError("invalid_id", f"Invalid slide ID {slide_id!r}")
    if len(set(validated)) != len(validated):
        raise SlideSpecError("duplicate_id", "Slide IDs must be unique")
    return validated


def rewrite_slide_map_ids(text: str, ids: Sequence[str]) -> str:
    spec, location, lines = _parse_with_location(text)
    validated_ids = _validate_ids(ids, len(spec.rows))
    normalized_headers = tuple(_normalized(header) for header in spec.headers)

    if "id" not in normalized_headers:
        header = _line_body(lines[location.header_index])
        lines[location.header_index] = _replace_line_body(
            lines[location.header_index], _insert_after_first_cell(header, "ID")
        )
        separator = _line_body(lines[location.separator_index])
        lines[location.separator_index] = _replace_line_body(
            lines[location.separator_index], _insert_after_first_cell(separator, "---")
        )
        for index, slide_id in zip(location.row_indices, validated_ids):
            row = _line_body(lines[index])
            lines[index] = _replace_line_body(
                lines[index], _insert_after_first_cell(row, slide_id)
            )
    else:
        id_index = normalized_headers.index("id")
        for index, slide_id in zip(location.row_indices, validated_ids):
            row = _line_body(lines[index])
            lines[index] = _replace_line_body(
                lines[index], _replace_cell(row, id_index, slide_id)
            )

    return "".join(lines)
