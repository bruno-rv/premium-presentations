#!/usr/bin/env python3
"""Deck Doctor — chain all deck validators into one human-readable health report.

Usage:
  ./scripts/deck_doctor.py <deck.html> [slide-spec.md]

Exit 0 when the deck is healthy, 1 when any validator reports an issue.

Thin orchestration only: every check lives in the validator modules, imported
in-process (same pattern as bundle_deck.py importing validate_deck).
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import validate_deck
import validate_runtime_contract
from validate_diagrams import validate_deck_diagrams, validate_inline_scripts
from validate_layout import validate_deck_layout

# validate_deck.validate() always ends with one of these summary lines.
_SUMMARY_RE = re.compile(r"(\d+) error\(s\), (\d+) warning\(s\)")
_OK_RE = re.compile(r"OK — (\d+) warning\(s\)")


def _section(title: str, ok: bool, lines: list[str]) -> None:
    print(f"[{'✓' if ok else '✗'}] {title}")
    body = [line for line in lines if line.strip()]
    if body:
        for line in body:
            print(f"    {line.rstrip()}")
    else:
        print("    no findings")
    print()


def main(argv: list[str]) -> int:
    if not argv or len(argv) > 2:
        print("Usage: deck_doctor.py <deck.html> [slide-spec.md]", file=sys.stderr)
        return 1
    html_path = Path(argv[0])
    spec_path = argv[1] if len(argv) > 1 else ""
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1
    if spec_path and not Path(spec_path).is_file():
        print(f"Spec not found: {spec_path}", file=sys.stderr)
        return 1

    text = html_path.read_text(encoding="utf-8", errors="replace")
    bundle = validate_deck.load_bundle(html_path, text)

    print(f"Deck Doctor — {html_path.name}")
    print()

    # 1. validate_deck — CLI semantics (prints + returns code): capture output.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        deck_rc = validate_deck.validate(html_path, spec_path)
    deck_out = buf.getvalue()
    fail_match = _SUMMARY_RE.search(deck_out)
    ok_match = _OK_RE.search(deck_out)
    deck_errors = int(fail_match.group(1)) if fail_match else (1 if deck_rc else 0)
    deck_warnings = (
        int(fail_match.group(2))
        if fail_match
        else (int(ok_match.group(1)) if ok_match else 0)
    )
    _section(
        "validate_deck (structure, components, spec slide map)",
        deck_rc == 0,
        deck_out.splitlines(),
    )

    # 2. validate_layout — importable (errors, warnings) API.
    l_errs, l_warns = validate_deck_layout(text, bundle, html_path)
    _section(
        "validate_layout (divider ghost numbers, overlap)",
        not l_errs,
        [f"FAIL: {e}" for e in l_errs] + [f"WARN: {w}" for w in l_warns],
    )

    # 3. validate_diagrams — importable (errors, warnings) API.
    d_errs, d_warns, mermaid_count = validate_deck_diagrams(text, bundle, html_path)
    s_errs, s_warns = validate_inline_scripts(text)
    d_errs, d_warns = d_errs + s_errs, d_warns + s_warns
    d_lines = [f"Mermaid diagrams: {mermaid_count}"] if mermaid_count else []
    d_lines += [f"FAIL: {e}" for e in d_errs] + [f"WARN: {w}" for w in d_warns]
    _section("validate_diagrams (mermaid structure, engine)", not d_errs, d_lines)

    # 4. validate_runtime_contract — its main() is repo-wide (templates + every
    # deck under assets/), so the doctor scopes to this deck via check_file(),
    # which applies to bundled decks (module markers). Its rel() formatter is
    # ROOT-relative and breaks for decks outside the skill tree, so report
    # absolute paths instead.
    validate_runtime_contract.rel = str
    rt_errors: list[str] = []
    validate_runtime_contract.check_file(html_path, rt_errors)
    _section(
        "validate_runtime_contract (required CSS/JS modules)",
        not rt_errors,
        [f"FAIL: {e}" for e in rt_errors],
    )

    # Layout/diagram/inline findings are already counted inside validate_deck's
    # totals (validate() chains those same checkers), so the verdict sums only
    # validate_deck + runtime-contract to avoid double counting.
    issues = deck_errors + len(rt_errors)
    warnings = deck_warnings
    if issues:
        print(f"{issues} issue(s), {warnings} warning(s)")
        return 1
    print("DECK HEALTHY" + (f" — {warnings} warning(s)" if warnings else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
