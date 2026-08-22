#!/usr/bin/env python3
"""Regression tests for deck-level layout guidance."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_deck.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_deck", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompareSplitDensityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def test_default_compare_split_does_not_warn_for_sparse_content(self) -> None:
        html = (
            '<section class="slide">'
            '<div class="compare-split"><div class="compare-panel">A</div>'
            '<div class="compare-panel">B</div></div>'
            '</section>'
        )
        self.assertEqual([], self.validator.validate_compare_split_density(html))

    def test_explicit_full_height_sparse_compare_warns(self) -> None:
        html = (
            '<section class="slide">'
            '<div class="compare-split compare-split--fill">'
            '<div class="compare-panel">A</div><div class="compare-panel">B</div>'
            '</div></section>'
        )
        messages = self.validator.validate_compare_split_density(html)
        self.assertEqual(1, len(messages))
        self.assertIn("explicit full-height", messages[0])

    def test_explicit_full_height_with_list_is_allowed(self) -> None:
        html = (
            '<section class="slide">'
            '<div class="compare-split" style="flex:1">'
            '<div class="compare-panel"><ul><li>A</li></ul></div>'
            '<div class="compare-panel"><ul><li>B</li></ul></div>'
            '</div></section>'
        )
        self.assertEqual([], self.validator.validate_compare_split_density(html))

    def test_unrelated_slide_list_does_not_satisfy_full_height_compare(self) -> None:
        html = (
            '<section class="slide">'
            '<ul><li>Unrelated slide content</li></ul>'
            '<div class="compare-split compare-split--fill">'
            '<div class="compare-panel">A</div><div class="compare-panel">B</div>'
            '</div></section>'
        )
        messages = self.validator.validate_compare_split_density(html)
        self.assertEqual(1, len(messages))
        self.assertIn("in every panel", messages[0])

    def test_each_full_height_panel_needs_concrete_list_content(self) -> None:
        html = (
            '<section class="slide">'
            '<div class="compare-split compare-split--fill">'
            '<div class="compare-panel"><ul><li>A</li></ul></div>'
            '<div class="compare-panel">B</div>'
            '</div></section>'
        )
        messages = self.validator.validate_compare_split_density(html)
        self.assertEqual(1, len(messages))

    def test_all_full_height_compare_splits_are_checked(self) -> None:
        html = (
            '<section class="slide">'
            '<div class="compare-split compare-split--fill">'
            '<div class="compare-panel">A</div><div class="compare-panel">B</div>'
            '</div>'
            '<div class="compare-split compare-split--fill">'
            '<div class="compare-panel">C</div><div class="compare-panel">D</div>'
            '</div></section>'
        )
        messages = self.validator.validate_compare_split_density(html)
        self.assertEqual(2, len(messages))


if __name__ == "__main__":
    unittest.main()
