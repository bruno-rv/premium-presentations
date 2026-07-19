#!/usr/bin/env python3
"""Tests for the Slide Budget grammar/serializer (slide_spec.py) and the
three-state Slide Map column rule.

Grammar vectors are shared with the JS counterpart in premium-presenter.js
via budget-vectors.json (scripts/tests/) — both implementations must agree
on every vector; see PLAN.md Workstream A canonical rules.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from slide_spec import (
    BUDGET_MS_MAX,
    BUDGET_MS_MIN,
    BudgetColumns,
    SlideSpecError,
    format_budget_mmss,
    parse_budget_columns,
    parse_slide_map,
    validate_budget_mmss,
    validate_budget_ms,
)

VECTORS = json.loads(
    (Path(__file__).resolve().parent / "budget-vectors.json").read_text(encoding="utf-8")
)


def _row(ordinal: int, slide_id: str, mmss: str, ms: str) -> str:
    return f"| {ordinal} | {slide_id} | {mmss} | {ms} |"


def _spec(rows: list[str]) -> str:
    header = "| # | ID | Budget (mm:ss) | Budget (ms) |\n|---|----|-----------------|-------------|"
    return "## Slide Map\n\n" + header + "\n" + "\n".join(rows)


class BudgetGrammarVectorTests(unittest.TestCase):
    def test_ms_valid_vectors_parse_to_expected_int(self) -> None:
        for case in VECTORS["msValid"]:
            with self.subTest(value=case["value"]):
                self.assertEqual(validate_budget_ms(case["value"]), case["ms"])

    def test_ms_invalid_vectors_are_rejected(self) -> None:
        for case in VECTORS["msInvalid"]:
            with self.subTest(value=case["value"], reason=case["reason"]):
                with self.assertRaises(SlideSpecError):
                    validate_budget_ms(case["value"])

    def test_mmss_from_ms_matches_vectors(self) -> None:
        for case in VECTORS["mmssFromMs"]:
            with self.subTest(ms=case["ms"]):
                self.assertEqual(format_budget_mmss(case["ms"]), case["mmss"])

    def test_mmss_valid_vectors_accept(self) -> None:
        for case in VECTORS["mmssValid"]:
            with self.subTest(mmss=case["mmss"]):
                validate_budget_mmss(case["mmss"], case["ms"])  # must not raise

    def test_mmss_invalid_vectors_are_rejected(self) -> None:
        for case in VECTORS["mmssInvalid"]:
            with self.subTest(mmss=case["mmss"], reason=case["reason"]):
                with self.assertRaises(SlideSpecError) as raised:
                    validate_budget_mmss(case["mmss"], 50000)
                self.assertEqual(raised.exception.code, "invalid_budget_mmss")

    def test_mmss_ms_mismatch_vectors_are_rejected(self) -> None:
        for case in VECTORS["mmssMsMismatch"]:
            with self.subTest(mmss=case["mmss"], ms=case["ms"]):
                with self.assertRaises(SlideSpecError) as raised:
                    validate_budget_mmss(case["mmss"], case["ms"])
                self.assertEqual(raised.exception.code, "budget_mismatch")

    def test_bounds_constants_match_plan(self) -> None:
        self.assertEqual(BUDGET_MS_MIN, 1000)
        self.assertEqual(BUDGET_MS_MAX, 7_200_000)


class ThreeStateColumnTests(unittest.TestCase):
    def test_headers_absent_is_budgetless(self) -> None:
        spec = parse_slide_map(
            "## Slide Map\n\n| # | ID | Title |\n|---|----|-------|\n| 1 | intro | Opening |"
        )
        result = parse_budget_columns(spec)
        self.assertEqual(result, BudgetColumns(state="budgetless", budgets=()))

    def test_headers_present_all_empty_is_budgetless(self) -> None:
        spec = parse_slide_map(_spec([_row(1, "intro", "", ""), _row(2, "proof", "", "")]))
        result = parse_budget_columns(spec)
        self.assertEqual(result.state, "budgetless")
        self.assertEqual(result.budgets, ())

    def test_headers_present_all_populated_is_budgeted(self) -> None:
        spec = parse_slide_map(
            _spec([_row(1, "intro", "00:50", "50000"), _row(2, "proof", "01:10", "70000")])
        )
        result = parse_budget_columns(spec)
        self.assertEqual(result.state, "budgeted")
        self.assertEqual([b.slide_id for b in result.budgets], ["intro", "proof"])
        self.assertEqual([b.ms for b in result.budgets], [50000, 70000])

    def test_only_mm_ss_header_present_is_validation_failure(self) -> None:
        text = _spec([_row(1, "intro", "00:50", "50000")]).replace(
            "| # | ID | Budget (mm:ss) | Budget (ms) |\n|---|----|-----------------|-------------|",
            "| # | ID | Budget (mm:ss) |\n|---|----|-----------------|",
        ).replace("| 1 | intro | 00:50 | 50000 |", "| 1 | intro | 00:50 |")
        spec = parse_slide_map(text)
        with self.assertRaises(SlideSpecError) as raised:
            parse_budget_columns(spec)
        self.assertEqual(raised.exception.code, "budget_header_mismatch")

    def test_partial_row_is_validation_failure(self) -> None:
        spec = parse_slide_map(
            _spec([_row(1, "intro", "00:50", "50000"), _row(2, "proof", "", "70000")])
        )
        with self.assertRaises(SlideSpecError) as raised:
            parse_budget_columns(spec)
        self.assertEqual(raised.exception.code, "budget_row_partial")

    def test_mixed_populated_and_empty_rows_is_validation_failure(self) -> None:
        spec = parse_slide_map(
            _spec([_row(1, "intro", "00:50", "50000"), _row(2, "proof", "", "")])
        )
        with self.assertRaises(SlideSpecError) as raised:
            parse_budget_columns(spec)
        self.assertEqual(raised.exception.code, "budget_row_mixed")

    def test_invalid_value_in_a_populated_row_is_validation_failure(self) -> None:
        spec = parse_slide_map(
            _spec([_row(1, "intro", "00:50", "999"), _row(2, "proof", "01:10", "70000")])
        )
        with self.assertRaises(SlideSpecError) as raised:
            parse_budget_columns(spec)
        self.assertEqual(raised.exception.code, "invalid_budget_ms")

    def test_mmss_ms_disagreement_in_a_populated_row_is_validation_failure(self) -> None:
        spec = parse_slide_map(
            _spec([_row(1, "intro", "00:51", "50000"), _row(2, "proof", "01:10", "70000")])
        )
        with self.assertRaises(SlideSpecError) as raised:
            parse_budget_columns(spec)
        self.assertEqual(raised.exception.code, "budget_mismatch")


if __name__ == "__main__":
    unittest.main()
