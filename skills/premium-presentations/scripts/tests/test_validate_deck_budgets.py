#!/usr/bin/env python3
"""Tests for validate_deck.py's Slide Budget HTML-side checks (PLAN.md
Workstream A step 3): unconditional grammar/completeness/orphan/duplicate/id
checks, and spec<->HTML parity when a spec is supplied. Zero false positives
on budgetless decks."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_deck.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_deck", VALIDATOR_PATH)
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


def _make_deck_html(sections: list[str]) -> str:
    slides = "".join(sections)
    return (
        f'<!doctype html><html lang="en"><head>'
        f'<style>{SHARED_CSS_MARKERS}</style>'
        f'</head><body>'
        f'<div id="deck">{slides}</div>'
        f'<script>{SHARED_JS_MARKERS}\nnew SlideEngine();</script>'
        f'</body></html>'
    )


def _slide(slide_id: str = "", budget: str | None = None, extra: str = "") -> str:
    id_attr = f' id="{slide_id}"' if slide_id else ""
    budget_attr = f' data-budget="{budget}"' if budget is not None else ""
    return (
        f'<section class="slide"{id_attr}{budget_attr}><h1>Slide</h1>{extra}'
        '<aside class="notes">Notes.</aside></section>'
    )


def run_validate(html: str, spec_text: str = "") -> tuple[int, str]:
    validator = load_validator()
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "deck.html"
        html_path.write_text(html, encoding="utf-8")
        spec_path = ""
        if spec_text:
            spec_file = Path(tmp) / "spec.md"
            spec_file.write_text(spec_text, encoding="utf-8")
            spec_path = str(spec_file)
        buf = StringIO()
        with patch("builtins.print", side_effect=lambda *a, **kw: buf.write(" ".join(str(x) for x in a) + "\n")):
            rc = validator.validate(html_path, spec_path)
        return rc, buf.getvalue()


BUDGETED_SPEC = """## Slide Map

| # | ID | Budget (mm:ss) | Budget (ms) |
|---|----|-----------------|-------------|
| 1 | intro | 00:50 | 50000 |
| 2 | proof | 01:10 | 70000 |
"""

BUDGETLESS_SPEC = """## Slide Map

| # | ID | Budget (mm:ss) | Budget (ms) |
|---|----|-----------------|-------------|
| 1 | intro |  |  |
| 2 | proof |  |  |
"""


class BudgetlessZeroFalsePositiveTests(unittest.TestCase):
    def test_no_data_budget_anywhere_passes_clean(self) -> None:
        html = _make_deck_html([_slide("intro"), _slide("proof")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("data-budget", out)

    def test_budgetless_spec_with_budgetless_html_passes(self) -> None:
        html = _make_deck_html([_slide("intro"), _slide("proof")])
        rc, out = run_validate(html, BUDGETLESS_SPEC)
        self.assertEqual(rc, 0, out)


class BudgetGrammarAndCompletenessTests(unittest.TestCase):
    def test_valid_complete_budgets_pass(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 0, out)

    def test_invalid_grammar_value_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "abc"), _slide("proof", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("invalid data-budget", out)

    def test_sub_min_value_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "999"), _slide("proof", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)

    def test_over_cap_value_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "7200001"), _slide("proof", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)

    def test_incomplete_coverage_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("attribute completeness", out)

    def test_missing_id_with_budget_present_fails(self) -> None:
        html = _make_deck_html([_slide("", "50000"), _slide("proof", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("no id attribute", out)

    def test_duplicate_ids_with_budget_present_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("intro", "70000")])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        # duplicate slide id is also caught earlier as an invalid slide structure
        self.assertIn("FAIL", out)


class DuplicateAndOrphanAttributeTests(unittest.TestCase):
    def test_duplicate_data_budget_attribute_on_one_slide_fails(self) -> None:
        html = _make_deck_html([
            '<section class="slide" id="intro" data-budget="50000" data-budget="60000">'
            '<h1>Slide</h1><aside class="notes">Notes.</aside></section>',
            _slide("proof", "70000"),
        ])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("duplicate attribute", out)

    def test_orphan_data_budget_outside_slide_section_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof", "70000")])
        html = html.replace("</body>", '<div data-budget="99999"></div></body>')
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("outside any slide section", out)

    def test_orphan_data_budget_nested_inside_slide_body_fails(self) -> None:
        html = _make_deck_html([
            _slide("intro", "50000", extra='<div data-budget="1234">nested</div>'),
            _slide("proof", "70000"),
        ])
        rc, out = run_validate(html)
        self.assertEqual(rc, 1, out)
        self.assertIn("outside any slide section", out)


class SpecHtmlBudgetParityTests(unittest.TestCase):
    def test_matching_spec_and_html_budgets_pass(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof", "70000")])
        rc, out = run_validate(html, BUDGETED_SPEC)
        self.assertEqual(rc, 0, out)

    def test_mismatched_html_budget_value_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "51000"), _slide("proof", "70000")])
        rc, out = run_validate(html, BUDGETED_SPEC)
        self.assertEqual(rc, 1, out)
        self.assertIn("data-budget mismatch", out)

    def test_spec_budgeted_html_missing_attribute_fails(self) -> None:
        html = _make_deck_html([_slide("intro"), _slide("proof", "70000")])
        rc, out = run_validate(html, BUDGETED_SPEC)
        self.assertEqual(rc, 1, out)
        # missing-coverage HTML-side check fires first; parity message also present
        self.assertIn("FAIL", out)

    def test_spec_budgetless_but_html_carries_budget_fails(self) -> None:
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof", "70000")])
        rc, out = run_validate(html, BUDGETLESS_SPEC)
        self.assertEqual(rc, 1, out)
        self.assertIn("spec is budgetless but HTML carries data-budget", out)

    def test_legacy_spec_without_id_column_skips_parity(self) -> None:
        legacy_spec = """## Slide Map

| # | Type | Title |
|---|------|-------|
| 1 | Title | Intro |
| 2 | Content | Proof |
"""
        html = _make_deck_html([_slide("intro", "50000"), _slide("proof", "70000")])
        rc, out = run_validate(html, legacy_spec)
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
