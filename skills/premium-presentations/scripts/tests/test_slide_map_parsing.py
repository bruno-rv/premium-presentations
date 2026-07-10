#!/usr/bin/env python3
"""Tests for validate_deck.py slide-map header parsing (validate(), ~line 305).

Regression coverage for a bug found by Codex review: spec_generator.py and
references/slide-spec-template.md emit a 9-column slide-map header
("| # | Act | Type | ... |"), but the old header-detection matched only the
legacy 5/7-column layout ("| # | Type | ... |"). Against a new-format spec,
zero map rows parsed and a real deck/spec slide-count mismatch silently
degraded from a FAIL to a "no slide map rows parsed" WARN.

Also covers Codex round-3 findings on the "## Slide Map" section gate: a
"###"+ subheading nested inside the section must not reset it, and the
heading match must be case-insensitive so "## slide map" stays gated instead
of falling back to the ungated legacy path.

Also covers a Codex round-4 finding: the heading match was an unbounded
prefix, so "## Slide Mapping Notes" wrongly matched as a "## Slide Map"
section. Fixed by requiring a `\\b` boundary after "Map" (end of heading,
whitespace, or punctuation), so "## Slide Map (draft)" still matches but
"## Slide Mapping Notes" does not.
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from slide_spec import SlideSpecError

ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_deck.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_deck", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED_CSS_MARKERS = """
prefers-reduced-motion: reduce {}
.premium-controller {}
"""

SHARED_JS_MARKERS = "\n".join(
    f"/* --- {name} --- */"
    for name in [
        "premium-controller.js", "premium-controls.js", "premium-annotations.js",
        "premium-timer.js", "premium-tts.js", "premium-search.js", "premium-clicker.js",
        "premium-og-cover.js", "premium-slide-content.js", "premium-presenter.js",
        "slide-engine.js",
    ]
)


def _make_deck_html(slide_count: int) -> str:
    """Build a minimal valid deck HTML fixture with the given slide count."""
    slides = "".join(
        f'<section class="slide"><h1>Slide {i}</h1><aside class="notes">Notes.</aside></section>'
        for i in range(1, slide_count + 1)
    )
    return (
        f'<!doctype html><html lang="en"><head>'
        f'<style>{SHARED_CSS_MARKERS}</style>'
        f'</head><body>'
        f'<div id="deck">{slides}</div>'
        f'<script>{SHARED_JS_MARKERS}\nnew SlideEngine();</script>'
        f'</body></html>'
    )


def run_validate(html: str, spec_text: str) -> tuple[int, str]:
    """Write html + spec to temp files, run validate(), return (exit_code, output)."""
    validator = load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "deck.html"
        spec_path = Path(tmp) / "spec.md"
        html_path.write_text(html, encoding="utf-8")
        spec_path.write_text(spec_text, encoding="utf-8")
        buf = StringIO()
        with patch("builtins.print", side_effect=lambda *a, **kw: buf.write(" ".join(str(x) for x in a) + "\n")):
            rc = validator.validate(html_path, str(spec_path))
        return rc, buf.getvalue()


NEW_FORMAT_5_ROWS = """## Slide Map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | I | content | A | ... | ... | ... | ... | ... |
| 3 | II | content | B | ... | ... | ... | ... | ... |
| 4 | II | content | C | ... | ... | ... | ... | ... |
| 5 | III | closing | End | ... | ... | ... | ... | ... |

## Next section
"""


EARLY_HASH_TABLE_THEN_SLIDE_MAP = """## Evidence Data

| # | Fact |
|---|------|
| 1 | Some fact |
| 2 | Another fact |
| 3 | Third fact |

## Slide Map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | III | closing | End | ... | ... | ... | ... | ... |

## Next section
"""


SUBHEADING_INSIDE_SLIDE_MAP = """## Slide Map

### Act 1

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |

### Act 2

| 2 | III | closing | End | ... | ... | ... | ... | ... |

## Next section
"""


EARLY_HASH_TABLE_THEN_LOWERCASE_SLIDE_MAP = """## Evidence Data

| # | Fact |
|---|------|
| 1 | Some fact |
| 2 | Another fact |
| 3 | Third fact |

## slide map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | III | closing | End | ... | ... | ... | ... | ... |

## Next section
"""


SLIDE_MAPPING_NOTES_ONLY = """## Slide Mapping Notes

| # | Note |
|---|------|
| 1 | ... |
| 2 | ... |
| 3 | ... |
"""


REAL_SLIDE_MAP_THEN_MAPPING_NOTES = """## Slide Map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | I | content | A | ... | ... | ... | ... | ... |

## Slide Mapping Notes

| # | Note |
|---|------|
| 1 | ... |
| 2 | ... |
| 3 | ... |
"""


SLIDE_MAP_DRAFT_HEADING = """## Slide Map (draft)

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | III | closing | End | ... | ... | ... | ... | ... |

## Next section
"""


MALFORMED_SLIDE_MAP = """## Slide Map

| # | Type | Title | Key Content | Visual Pattern |
|---|------|-------|-------------|----------------|
| 1 | Title | Opening |
"""


UNTERMINATED_HEADER_SLIDE_MAP = """## Slide Map

| # | Type | Title
"""


NO_SLIDE_MAP = """## Lesson Plan

No tabular slide map has been written yet.
"""


class SlideMapHeaderParsingTests(unittest.TestCase):
    def test_slide_count_accepts_id_before_class(self) -> None:
        html = _make_deck_html(slide_count=1).replace(
            '<section class="slide">',
            '<section id="opening" class="slide">',
        )
        rc, out = run_validate(html, NO_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected attribute order to remain valid:\n{out}")
        self.assertIn("Slides found: 1", out)

    def test_new_9col_format_mismatch_fails(self) -> None:
        """New-format (9-col) spec claiming 5 slides vs. a 2-slide deck must FAIL,
        not silently degrade to a 'no slide map rows parsed' warning."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, NEW_FORMAT_5_ROWS)
        self.assertEqual(rc, 1, f"Expected non-zero exit for slide count mismatch:\n{out}")
        fail_lines = [l for l in out.splitlines() if "FAIL" in l and "Slide count mismatch" in l]
        self.assertGreater(len(fail_lines), 0, f"Expected a slide count mismatch FAIL:\n{out}")
        no_rows_warn = [l for l in out.splitlines() if "no slide map rows parsed" in l]
        self.assertEqual([], no_rows_warn, f"Slide map rows should have parsed:\n{out}")

    def test_earlier_hash_table_not_counted_as_slide_map(self) -> None:
        """An earlier table with a "| # |" header column (e.g. "| # | Fact |" in
        an Evidence Data section) must not flip in_map early — only the real
        "## Slide Map" section's rows should count toward the expected slide
        count. A 2-slide deck matching the real 2-row slide map must PASS."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, EARLY_HASH_TABLE_THEN_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected clean pass, not a false slide-count mismatch:\n{out}")
        mismatch_lines = [l for l in out.splitlines() if "Slide count mismatch" in l]
        self.assertEqual([], mismatch_lines, f"Earlier table rows must not be counted:\n{out}")
        self.assertIn("Spec expects: 2", out)

    def test_subheading_inside_slide_map_not_broken(self) -> None:
        """A "###" subheading nested inside "## Slide Map" (e.g. "### Act 1")
        must not reset in_slide_map_section — it's content within the
        section, not a sibling section. Both rows across both subheadings
        must still be counted."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, SUBHEADING_INSIDE_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected clean pass, not a false slide-count mismatch:\n{out}")
        no_rows_warn = [l for l in out.splitlines() if "no slide map rows parsed" in l]
        self.assertEqual([], no_rows_warn, f"Slide map rows should have parsed:\n{out}")
        self.assertIn("Spec expects: 2", out)

    def test_lowercase_slide_map_heading_honored(self) -> None:
        """A lowercase "## slide map" heading must still be recognized as the
        Slide Map heading (case-insensitive), keeping the gate active so an
        earlier unrelated "| # | Fact |" table isn't counted alongside it."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, EARLY_HASH_TABLE_THEN_LOWERCASE_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected clean pass, not a false slide-count mismatch:\n{out}")
        mismatch_lines = [l for l in out.splitlines() if "Slide count mismatch" in l]
        self.assertEqual([], mismatch_lines, f"Earlier table rows must not be counted:\n{out}")
        self.assertIn("Spec expects: 2", out)

    def test_slide_mapping_notes_heading_not_treated_as_slide_map_section(self) -> None:
        """"## Slide Mapping Notes" must not match the "## Slide Map" heading
        gate (Codex round-4: unbounded prefix match wrongly classified it as
        a slide-map section). This spec has no real "## Slide Map" heading
        anywhere, so has_slide_map_heading is correctly False and the
        pre-existing *ungated legacy fallback* (see validate_deck.py ~line
        304-306) takes over: any "| # |" table in the doc is still treated
        as the slide map, exactly as it would be for any other legacy spec
        that never adopted the "## Slide Map" heading convention. So the
        mismatch here (5 slides vs. 3 parsed rows) is the correct, intended
        fallback outcome — NOT evidence that "Mapping Notes" was
        misclassified as a Slide Map section. Contrast with
        test_slide_mapping_notes_after_real_slide_map_not_overwritten below,
        which is where the heading-boundary fix actually changes the
        outcome."""
        html = _make_deck_html(slide_count=5)
        rc, out = run_validate(html, SLIDE_MAPPING_NOTES_ONLY)
        self.assertEqual(rc, 1, f"Expected the ungated legacy fallback to still catch the table:\n{out}")
        self.assertIn("Spec expects: 3", out)
        fail_lines = [l for l in out.splitlines() if "FAIL" in l and "Slide count mismatch" in l]
        self.assertGreater(len(fail_lines), 0, f"Expected a slide count mismatch FAIL:\n{out}")

    def test_slide_mapping_notes_after_real_slide_map_not_overwritten(self) -> None:
        """A real "## Slide Map" section (2 rows, matching the 2-slide deck)
        followed by an unrelated "## Slide Mapping Notes" section (3 rows)
        must not let the "last heading wins" reset logic overwrite the real
        section's rows — that requires "Slide Mapping Notes" to NOT be
        classified as entering a Slide Map section. Before the round-4 fix,
        the unbounded prefix match misclassified "Slide Mapping Notes" as a
        second Slide Map section, so its rows replaced the real 2-row map
        and produced a false "HTML has 2, spec slide map has 3" mismatch."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, REAL_SLIDE_MAP_THEN_MAPPING_NOTES)
        self.assertEqual(rc, 0, f"Expected clean pass, not a false slide-count mismatch:\n{out}")
        mismatch_lines = [l for l in out.splitlines() if "Slide count mismatch" in l]
        self.assertEqual([], mismatch_lines, f"Mapping Notes rows must not overwrite the real slide map:\n{out}")
        self.assertIn("Spec expects: 2", out)

    def test_slide_map_draft_heading_still_matches(self) -> None:
        """Quick sanity check for the round-4 boundary fix: "## Slide Map
        (draft)" must still be recognized as a Slide Map heading — the
        word-boundary requirement after "Map" must not be so strict that it
        rejects trailing punctuation/parentheses."""
        html = _make_deck_html(slide_count=2)
        rc, out = run_validate(html, SLIDE_MAP_DRAFT_HEADING)
        self.assertEqual(rc, 0, f"Expected '## Slide Map (draft)' to still be recognized:\n{out}")
        self.assertIn("Spec expects: 2", out)

    def test_malformed_detected_slide_map_is_an_error(self) -> None:
        html = _make_deck_html(slide_count=1)
        rc, out = run_validate(html, MALFORMED_SLIDE_MAP)
        self.assertEqual(rc, 1, f"Expected malformed Slide Map to fail validation:\n{out}")
        self.assertIn("FAIL: Invalid Slide Map:", out)

    def test_unterminated_slide_map_header_is_an_error(self) -> None:
        html = _make_deck_html(slide_count=1)
        rc, out = run_validate(html, UNTERMINATED_HEADER_SLIDE_MAP)
        self.assertEqual(rc, 1, f"Expected malformed Slide Map header to fail:\n{out}")
        self.assertIn("FAIL: Invalid Slide Map:", out)
        self.assertNotIn("no slide map rows parsed", out)

    def test_absent_slide_map_remains_a_warning(self) -> None:
        html = _make_deck_html(slide_count=1)
        rc, out = run_validate(html, NO_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected absent Slide Map to remain non-fatal:\n{out}")
        self.assertIn("WARN: Spec provided but no slide map rows parsed", out)

    def test_absent_map_warning_uses_error_code_not_message(self) -> None:
        html = _make_deck_html(slide_count=1)
        changed_wording = SlideSpecError("no_slide_map", "wording changed")
        with patch("slide_spec.parse_slide_map", side_effect=changed_wording):
            rc, out = run_validate(html, NO_SLIDE_MAP)
        self.assertEqual(rc, 0, f"Expected no_slide_map code to remain a warning:\n{out}")
        self.assertIn("WARN: Spec provided but no slide map rows parsed", out)


if __name__ == "__main__":
    unittest.main()
