#!/usr/bin/env python3
"""Plan stable-ID slide regeneration without mutating deck or spec files."""

from __future__ import annotations

import argparse
import contextlib
import datetime as datetime_module
import hashlib
import io
import json
import os
import re
import stat as stat_module
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, NoReturn, Sequence

from slide_html import (
    SlideHtmlError,
    SlideSpan,
    assign_slide_ids,
    fragment_class_tokens,
    parse_json_script_span,
    parse_slide_spans,
    splice_sections,
    validate_fragment,
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
import deck_doctor
import validate_runtime_contract


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
    "invalid_id_column": (
        "full_regeneration_required",
        "invalid_identity_column",
    ),
}


class RegenInputError(ValueError):
    """Raised when a read-only regeneration input is unsafe or malformed."""


class RegenValidationError(RegenInputError):
    """Raised when a staged or committed deck fails validation."""


class FullRegenerationRequired(RegenInputError):
    """Raised when a partial edit would require new bundled capabilities."""


CAPABILITY_MARKERS = {
    "journey": "premium-journey.js",
    "flow": "premium-flow.js",
    "glossary": "premium-glossary.js",
    "mermaid": "premium-mermaid",
    "theme_homage": "theme-visuals-embed",
}


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
        or value in {".", ".."}
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


def _fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value: Mapping[str, object]) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _backup_root(deck: Path, *, create: bool = False) -> Path:
    parent = deck.resolve().parent
    partial = parent / ".partial-regen"
    root = partial / "backups"
    for path, label in ((partial, "transaction directory"), (root, "backup root")):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            if not create:
                continue
            path.mkdir(mode=0o700)
            _fsync_directory(path.parent)
            continue
        if stat_module.S_ISLNK(mode) or not stat_module.S_ISDIR(mode):
            raise RegenInputError(f"{label} is unsafe")
    return root


def _write_exclusive(path: Path, data: bytes, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _create_backup(deck: Path, operation: str, targets: Sequence[Path]) -> Path:
    root = _backup_root(deck, create=True)
    stem = datetime_module.datetime.now(datetime_module.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    for suffix in range(1000):
        backup = root / (stem if suffix == 0 else f"{stem}-{suffix}")
        try:
            backup.mkdir(mode=0o700)
            _fsync_directory(root)
            break
        except FileExistsError:
            continue
    else:
        raise RegenInputError("could not allocate unique backup directory")
    entries: list[dict[str, str]] = []
    for target in targets:
        mode = target.lstat().st_mode
        if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
            raise RegenInputError(f"target must be a regular non-symlink file: {target}")
        payload = target.read_bytes()
        _write_exclusive(backup / target.name, payload, stat_module.S_IMODE(mode))
        entries.append({"backup": target.name, "sha256": _sha256(payload), "target": target.name})
    _atomic_json(backup / "metadata.json", {"version": 1, "operation": operation, "status": "prepared", "targets": entries})
    _fsync_directory(backup)
    return backup


def _replace_file(source: Path, target: Path) -> None:
    os.replace(source, target)
    _fsync_directory(target.parent)


def _stage_bytes(target: Path, data: bytes) -> Path:
    fd, raw = tempfile.mkstemp(prefix=f".{target.name}.partial-regen-", dir=target.parent)
    staged = Path(raw)
    try:
        os.fchmod(fd, stat_module.S_IMODE(target.lstat().st_mode))
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        return staged
    except BaseException:
        os.close(fd)
        staged.unlink(missing_ok=True)
        raise


def _metadata(backup: Path) -> dict[str, object]:
    path = backup / "metadata.json"
    if path.is_symlink() or not path.is_file():
        raise RegenInputError("backup metadata is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegenInputError("backup metadata is invalid") from exc
    if not isinstance(value, dict) or value.get("version") != 1 or value.get("operation") not in {"init", "apply"} or value.get("status") not in {"prepared", "committed", "rolled_back"}:
        raise RegenInputError("backup metadata has an invalid schema")
    targets = value.get("targets")
    if not isinstance(targets, list) or not targets:
        raise RegenInputError("backup metadata has invalid targets")
    for item in targets:
        if not isinstance(item, dict) or set(item) != {"backup", "sha256", "target"}:
            raise RegenInputError("backup metadata has invalid target entry")
        if (
            item["backup"] != item["target"]
            or not _is_backup_basename(item["target"])
            or not HASH_RE.fullmatch(item["sha256"])
        ):
            raise RegenInputError("backup metadata target is unsafe")
    return value


def _is_backup_basename(value: object) -> bool:
    return (
        isinstance(value, str)
        and value not in {".", ".."}
        and Path(value).name == value
        and not Path(value).is_absolute()
        and "/" not in value
        and "\\" not in value
    )


def _metadata_targets(
    deck: Path,
    metadata: Mapping[str, object],
    *,
    spec_basename: str | None = None,
) -> list[tuple[Path, Mapping[str, str]]]:
    entries = metadata["targets"]
    names = {item["target"] for item in entries}
    if metadata["operation"] == "apply":
        expected = {deck.name}
    else:
        if spec_basename is None:
            raise RegenInputError("initialization backup requires a trusted spec basename")
        expected = {deck.name, spec_basename}
        if len(names) != 2:
            raise RegenInputError("initialization backup target set is unexpected")
    if names != expected:
        raise RegenInputError("backup target set is unexpected")
    return [(deck.parent / item["target"], item) for item in entries]


def _rollback_recovery_targets(
    metadata: object, targets: Sequence[tuple[Path, Mapping[str, str]]]
) -> list[tuple[Path, Mapping[str, str]]]:
    if (
        not isinstance(metadata, dict)
        or set(metadata) != {"version", "operation", "status", "targets"}
        or metadata.get("version") != 1
        or metadata.get("operation") != "rollback"
        or metadata.get("status") != "prepared"
        or not isinstance(metadata.get("targets"), list)
    ):
        raise RegenInputError("rollback recovery metadata is invalid")
    trusted_targets = {item["target"]: target for target, item in targets}
    entries = metadata["targets"]
    if len(entries) != len(trusted_targets):
        raise RegenInputError("rollback recovery metadata is invalid")
    validated: list[Mapping[str, str]] = []
    for item in entries:
        if (
            not isinstance(item, dict)
            or set(item) != {"backup", "sha256", "target"}
            or not _is_backup_basename(item["backup"])
            or not _is_backup_basename(item["target"])
            or not isinstance(item["sha256"], str)
            or not HASH_RE.fullmatch(item["sha256"])
        ):
            raise RegenInputError("rollback recovery metadata is invalid")
        validated.append(item)
    if {item["target"] for item in validated} != set(trusted_targets):
        raise RegenInputError("rollback recovery metadata is invalid")
    return [(trusted_targets[item["target"]], item) for item in validated]


def _set_backup_status(backup: Path, metadata: dict[str, object], status: str) -> None:
    updated = dict(metadata)
    updated["status"] = status
    _atomic_json(backup / "metadata.json", updated)


def _prepared_backups(deck: Path) -> list[Path]:
    root = _backup_root(deck)
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise RegenInputError("backup root is unsafe")
    prepared: list[Path] = []
    for candidate in root.iterdir():
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        for name in ("metadata.json", "rollback-metadata.json"):
            metadata = candidate / name
            if metadata.is_file() and not metadata.is_symlink():
                try:
                    if json.loads(metadata.read_text(encoding="utf-8")).get("status") == "prepared":
                        prepared.append(candidate)
                        break
                except (OSError, json.JSONDecodeError):
                    prepared.append(candidate)
                    break
    return prepared


def _check_unresolved_transaction(deck: Path) -> None:
    prepared = _prepared_backups(deck)
    if prepared:
        raise RegenInputError("unresolved transaction; run rollback with backup: " + ", ".join(str(path) for path in prepared))


def _run_deck_doctor(deck: Path, spec: Path) -> None:
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        result = deck_doctor.main([str(deck), str(spec)])
    if result != 0:
        raise RegenValidationError(output.getvalue().strip() or "Deck Doctor rejected staged deck")


def _validate_committed_pair(deck: Path, spec: Path) -> None:
    validate_pair(deck, spec)
    _run_deck_doctor(deck, spec)
    result = plan_pair(deck, spec, check_transactions=False)
    if result.status != "no_changes":
        raise RegenValidationError(f"committed pair did not establish a clean baseline: {result.reason_code}")


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
        if exc.code in {
            "missing_id",
            "duplicate_id",
            "invalid_id",
            "invalid_id_column",
        }:
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


def _init_apply(deck: Path, spec: Path) -> PlanResult:
    deck, spec = validate_pair(deck, spec)
    _check_unresolved_transaction(deck)
    candidate_deck, candidate_spec, preview = _build_init_candidates(deck, spec)
    staged_deck = _stage_bytes(deck, candidate_deck.encode("utf-8"))
    staged_spec = _stage_bytes(spec, candidate_spec.encode("utf-8"))
    backup: Path | None = None
    metadata: dict[str, object] | None = None
    try:
        _run_deck_doctor(staged_deck, staged_spec)
        backup = _create_backup(deck, "init", (deck, spec))
        metadata = _metadata(backup)
        _replace_file(staged_deck, deck)
        _replace_file(staged_spec, spec)
        _validate_committed_pair(deck, spec)
        _set_backup_status(backup, metadata, "committed")
        return PlanResult("initialized", "initialized_and_committed", preview.changed, ("Initialization committed.",))
    except BaseException:
        if backup is not None and metadata is not None:
            try:
                _restore_backup(
                    deck, backup, metadata, validate=False, spec_basename=spec.name
                )
                _set_backup_status(backup, metadata, "rolled_back")
            except BaseException:
                pass
        raise
    finally:
        staged_deck.unlink(missing_ok=True)
        staged_spec.unlink(missing_ok=True)


def _fragment_capabilities(fragment: str) -> set[str]:
    found: set[str] = set()
    classes = fragment_class_tokens(fragment)
    if "journey-stage" in classes: found.add("journey")
    if "live-flow" in classes: found.add("flow")
    if "term-link" in classes: found.add("glossary")
    if "mermaid" in classes: found.add("mermaid")
    if {"slide--title", "slide--divider"} & classes: found.add("theme_homage")
    return found


def _deck_capabilities(html: str) -> set[str]:
    return {name for name, marker in CAPABILITY_MARKERS.items() if validate_runtime_contract.marker_present(html, marker) or marker in html}


def _glossary_keys(html: str) -> set[str]:
    try:
        span = parse_json_script_span(html, "glossary")
        value = json.loads(span.content)
    except (SlideHtmlError, json.JSONDecodeError):
        return set()
    return set(value) if isinstance(value, dict) and all(isinstance(key, str) for key in value) else set()


def _parse_fragments(values: Sequence[str]) -> dict[str, str]:
    fragments: dict[str, str] = {}
    for value in values:
        slide_id, separator, filename = value.partition("=")
        if not separator or not slide_id or not ID_RE.fullmatch(slide_id) or slide_id in fragments:
            raise RegenInputError("each --fragment must be a unique ID=FILE")
        path = Path(filename)
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise RegenInputError(f"fragment is unavailable: {path}") from exc
        if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
            raise RegenInputError(f"fragment must be a regular non-symlink file: {path}")
        fragments[slide_id] = path.read_text(encoding="utf-8")
    return fragments


def _apply(deck: Path, spec: Path, fragment_values: Sequence[str]) -> PlanResult:
    deck, spec = validate_pair(deck, spec)
    plan = plan_pair(deck, spec)
    if plan.status != "changes_planned":
        raise RegenInputError("apply requires a plan with changed rows")
    fragments = _parse_fragments(fragment_values)
    if set(fragments) != set(plan.changed):
        raise RegenInputError("fragment IDs must exactly match planned changed IDs")
    deck_text = deck.read_text(encoding="utf-8")
    spec_text = spec.read_text(encoding="utf-8")
    state = load_state(deck_text)
    edited = parse_slide_map(spec_text, require_ids=True)
    rows = {row.slide_id: row for row in edited.rows}
    glossary = _glossary_keys(deck_text)
    for slide_id, fragment in fragments.items():
        errors = validate_fragment(fragment, rows[slide_id])
        if errors:
            raise RegenInputError("invalid fragment for " + slide_id + ": " + "; ".join(errors))
        capabilities = _fragment_capabilities(fragment) - _deck_capabilities(deck_text)
        if capabilities:
            raise FullRegenerationRequired("new_runtime_capability: " + ", ".join(sorted(capabilities)))
        fragment_keys = set(re.findall(r'\bdata-term\s*=\s*["\']([^"\']+)["\']', fragment, re.I))
        if fragment_keys - glossary:
            raise FullRegenerationRequired("new_glossary_key: " + ", ".join(sorted(fragment_keys - glossary)))
    candidate = splice_sections(deck_text, fragments)
    candidate_state = dict(state)
    candidate_slides = {slide_id: dict(value) for slide_id, value in state["slides"].items()}
    for span in parse_slide_spans(candidate):
        if span.slide_id in fragments:
            candidate_slides[span.slide_id]["row"] = _semantic_row(rows[span.slide_id])
            candidate_slides[span.slide_id]["rowHash"] = _sha256(canonical_row(rows[span.slide_id]))
            candidate_slides[span.slide_id]["sectionHash"] = _sha256(span.raw.encode("utf-8"))
    candidate_state["slides"] = candidate_slides
    state_span = parse_json_script_span(candidate, STATE_ID)
    candidate = candidate[:state_span.start] + render_state(candidate_state) + candidate[state_span.end:]
    if envelope_hash(candidate) != state["envelopeHash"]:
        raise RegenValidationError("candidate changed the deck envelope")
    staged = _stage_bytes(deck, candidate.encode("utf-8"))
    backup: Path | None = None
    metadata: dict[str, object] | None = None
    try:
        _run_deck_doctor(staged, spec)
        backup = _create_backup(deck, "apply", (deck,))
        metadata = _metadata(backup)
        _replace_file(staged, deck)
        _validate_committed_pair(deck, spec)
        _set_backup_status(backup, metadata, "committed")
        return PlanResult("applied", "fragments_committed", plan.changed, ("Fragments committed.",))
    except BaseException:
        if backup is not None and metadata is not None:
            try:
                _restore_backup(deck, backup, metadata, validate=False)
                _set_backup_status(backup, metadata, "rolled_back")
            except BaseException:
                pass
        raise
    finally:
        staged.unlink(missing_ok=True)


def _safe_backup_directory(deck: Path, requested: Path) -> Path:
    mode = deck.lstat().st_mode
    if stat_module.S_ISLNK(mode) or not stat_module.S_ISREG(mode):
        raise RegenInputError("deck must be a regular non-symlink file")
    if ".." in requested.parts:
        raise RegenInputError("backup path must not contain traversal")
    root = _backup_root(deck)
    lexical_root = Path(os.path.abspath(deck.parent / ".partial-regen" / "backups"))
    candidate = Path(os.path.abspath(requested))
    try:
        candidate.relative_to(lexical_root)
    except ValueError as exc:
        raise RegenInputError("backup must be beneath the deck backup root") from exc
    cursor = lexical_root
    for part in candidate.relative_to(cursor).parts:
        cursor /= part
        mode = cursor.lstat().st_mode
        if stat_module.S_ISLNK(mode):
            raise RegenInputError("backup path must not contain symlinks")
    resolved = candidate.resolve()
    if not candidate.is_dir() or resolved != root / candidate.relative_to(lexical_root):
        raise RegenInputError("backup directory is unsafe")
    return resolved


def _restore_backup(
    deck: Path,
    backup: Path,
    metadata: dict[str, object],
    *,
    validate: bool,
    spec_basename: str | None = None,
) -> None:
    staged: list[tuple[Path, Path]] = []
    try:
        for target, item in _metadata_targets(deck, metadata, spec_basename=spec_basename):
            payload_path = backup / item["backup"]
            if payload_path.is_symlink() or not payload_path.is_file():
                raise RegenInputError("backup payload is unsafe")
            payload = payload_path.read_bytes()
            if _sha256(payload) != item["sha256"]:
                raise RegenInputError("backup payload hash mismatch")
            staged.append((_stage_bytes(target, payload), target))
        for source, target in reversed(staged):
            _replace_file(source, target)
        if validate:
            for target, item in _metadata_targets(deck, metadata, spec_basename=spec_basename):
                if _sha256(target.read_bytes()) != item["sha256"]:
                    raise RegenValidationError("restored target hash mismatch")
    finally:
        for source, _ in staged:
            source.unlink(missing_ok=True)


def _rollback(deck: Path, requested: Path) -> PlanResult:
    backup = _safe_backup_directory(deck, requested)
    prepared = _prepared_backups(deck)
    if prepared and (len(prepared) != 1 or prepared[0] != backup):
        raise RegenInputError("rollback must use the unresolved prepared backup")
    metadata = _metadata(backup)
    spec_basename: str | None = None
    if metadata["operation"] == "init":
        state = load_state(deck.read_text(encoding="utf-8"))
        if state["deck"] != deck.name:
            raise RegenInputError("embedded state does not match rollback deck")
        spec_basename = _validate_basename(state["spec"], "spec")
    targets = _metadata_targets(deck, metadata, spec_basename=spec_basename)
    rollback_path = backup / "rollback-metadata.json"
    if rollback_path.exists():
        if rollback_path.is_symlink():
            raise RegenInputError("rollback metadata is unsafe")
        try:
            previous = json.loads(rollback_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegenInputError("rollback metadata is invalid") from exc
        if not isinstance(previous, dict):
            raise RegenInputError("rollback metadata is invalid")
        if previous.get("status") == "prepared":
            recovery: list[tuple[Path, Path]] = []
            try:
                recovery_targets = _rollback_recovery_targets(previous, targets)
                for target, item in recovery_targets:
                    payload_path = backup / item["backup"]
                    if payload_path.is_symlink() or not payload_path.is_file():
                        raise RegenInputError("rollback recovery payload is unsafe")
                    payload = payload_path.read_bytes()
                    if _sha256(payload) != item["sha256"]:
                        raise RegenInputError("rollback recovery payload hash mismatch")
                    recovery.append((_stage_bytes(target, payload), target))
                for source, target in reversed(recovery):
                    _replace_file(source, target)
                _atomic_json(rollback_path, {**previous, "status": "rolled_back"})
            finally:
                for source, _ in recovery:
                    source.unlink(missing_ok=True)
    staged_originals: list[tuple[Path, Path]] = []
    journal_targets: list[dict[str, str]] = []
    rollback_metadata: dict[str, object] = {}
    try:
        for target, item in targets:
            payload = target.read_bytes()
            stamp = datetime_module.datetime.now(datetime_module.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
            name = f"rollback-{stamp}-{item['target']}"
            _write_exclusive(backup / name, payload, stat_module.S_IMODE(target.lstat().st_mode))
            journal_targets.append({"backup": name, "sha256": _sha256(payload), "target": item["target"]})
            staged_originals.append((_stage_bytes(target, payload), target))
        rollback_metadata = {"version": 1, "operation": "rollback", "status": "prepared", "targets": journal_targets}
        _atomic_json(rollback_path, rollback_metadata)
        _restore_backup(
            deck, backup, metadata, validate=True, spec_basename=spec_basename
        )
        _atomic_json(rollback_path, {**rollback_metadata, "status": "committed"})
    except BaseException:
        if rollback_metadata and rollback_path.exists():
            try:
                for source, target in reversed(staged_originals):
                    _replace_file(source, target)
                hashes = {item["target"]: item["sha256"] for item in journal_targets}
                for _, target in staged_originals:
                    if _sha256(target.read_bytes()) != hashes[target.name]:
                        raise RegenValidationError("rollback recovery hash mismatch")
                _atomic_json(rollback_path, {**rollback_metadata, "status": "rolled_back"})
            except BaseException:
                pass
        raise
    finally:
        for source, _ in staged_originals:
            source.unlink(missing_ok=True)
    return PlanResult("rolled_back", "backup_restored", _immutable_changed(), ("Backup restored.",))


class RegenArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise RegenInputError(message)


def _parser() -> RegenArgumentParser:
    parser = RegenArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="preview or apply initialization")
    init_parser.add_argument("--deck", type=Path, required=True)
    init_parser.add_argument("--spec", type=Path, required=True)
    init_parser.add_argument("--apply", action="store_true")

    plan_parser = commands.add_parser("plan", help="plan changed slide fragments")
    plan_parser.add_argument("--deck", type=Path, required=True)
    plan_parser.add_argument("--spec", type=Path, required=True)
    plan_parser.add_argument("--json", action="store_true", dest="as_json")

    apply_parser = commands.add_parser("apply", help="apply planned slide fragments")
    apply_parser.add_argument("--deck", type=Path, required=True)
    apply_parser.add_argument("--spec", type=Path, required=True)
    apply_parser.add_argument("--fragment", action="append", required=True)

    rollback_parser = commands.add_parser("rollback", help="restore a transaction backup")
    rollback_parser.add_argument("--deck", type=Path, required=True)
    rollback_parser.add_argument("--backup", type=Path, required=True)
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
            result = _init_apply(options.deck, options.spec) if options.apply else preview_init(options.deck, options.spec)
        elif options.command == "plan":
            result = plan_pair(options.deck, options.spec)
        elif options.command == "apply":
            result = _apply(options.deck, options.spec, options.fragment)
        else:
            result = _rollback(options.deck, options.backup)
    except SystemExit as exc:
        return int(exc.code)
    except FullRegenerationRequired as exc:
        code = "new_glossary_key" if str(exc).startswith("new_glossary_key:") else "new_runtime_capability"
        result = PlanResult("full_regeneration_required", code, _immutable_changed(), (str(exc),))
        _print_human(result)
        return 2
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
