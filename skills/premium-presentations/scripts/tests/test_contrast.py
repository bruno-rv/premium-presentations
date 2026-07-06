#!/usr/bin/env python3
"""Tests for validate_contrast.py — AT2/AT3: built-ins pass, low-contrast fails."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from validate_contrast import (  # noqa: E402
    check_palette,
    contrast_ratio,
    scan_themes_css,
)
from _common import THEMES_CSS  # noqa: E402


class ContrastRatioTests(unittest.TestCase):
    # Literal expected ratios per ADR-b (empirically computed against the real
    # repo hexes) — no HEAD-relative baseline; a built-in edit that drops
    # below threshold fails this test deterministically.
    def test_editorial_ratios(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#eaedf2", "#08080a"), 17.05, places=2)
        self.assertAlmostEqual(contrast_ratio("#eaedf2", "#111114"), 16.06, places=2)
        self.assertAlmostEqual(contrast_ratio("#6e7a8c", "#08080a"), 4.60, places=2)
        self.assertAlmostEqual(contrast_ratio("#4a9eff", "#08080a"), 7.27, places=2)

    def test_warm_ratios(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#f1e8d8", "#14110d"), 15.48, places=2)
        self.assertAlmostEqual(contrast_ratio("#a89986", "#14110d"), 6.78, places=2)
        self.assertAlmostEqual(contrast_ratio("#e8a25c", "#14110d"), 8.74, places=2)

    def test_red_ratios(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#1a1a1a", "#ffffff"), 17.40, places=2)
        self.assertAlmostEqual(contrast_ratio("#5c6370", "#ffffff"), 6.05, places=2)
        self.assertAlmostEqual(contrast_ratio("#FF0230", "#ffffff"), 3.96, places=2)

    def test_cupertino_ratios(self) -> None:
        self.assertAlmostEqual(contrast_ratio("#1d1d1f", "#fbfbfd"), 16.28, places=2)
        self.assertAlmostEqual(contrast_ratio("#6e6e73", "#fbfbfd"), 4.91, places=2)
        self.assertAlmostEqual(contrast_ratio("#0066cc", "#fbfbfd"), 5.39, places=2)


class CheckPaletteTests(unittest.TestCase):
    def test_ata3_low_contrast_rejected(self) -> None:
        # AT3: light-grey text on white = 1.61:1 -> fails pair 1, named + ratio.
        errors = check_palette({"text": "#cccccc", "bg": "#ffffff", "surface": "#ffffff",
                                  "text-dim": "#cccccc", "accent": "#cccccc"})
        self.assertTrue(errors)
        joined = "\n".join(errors)
        self.assertIn("--text on --bg", joined)
        self.assertIn("1.61", joined)

    def test_missing_token_is_fail_closed(self) -> None:
        errors = check_palette({"bg": "#ffffff"})
        self.assertTrue(errors)
        self.assertTrue(any("missing or non-hex" in e for e in errors))

    def test_aa_passing_palette_clears_gate(self) -> None:
        errors = check_palette({
            "text": "#1a1a1a", "bg": "#ffffff", "surface": "#f5f5f7",
            "text-dim": "#5c6370", "accent": "#0066cc",
        })
        self.assertEqual([], errors)


class ScanThemesCssTests(unittest.TestCase):
    def test_builtin_themes_pass_repo_wide_gate(self) -> None:
        # Regression guard: the 4 shipped themes must never fail this gate.
        errors = scan_themes_css(THEMES_CSS)
        self.assertEqual([], errors, f"Built-in themes must pass: {errors}")

    def test_scan_ignores_component_override_blocks(self) -> None:
        # html[data-theme="x"] .component { ... } blocks (e.g. .slide,
        # .compare-panel--up) must not be mistaken for theme token blocks.
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            css_path.write_text(
                'html[data-theme="ok"] {\n'
                "  --text: #1a1a1a;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #f5f5f7;\n"
                "  --text-dim: #5c6370;\n"
                "  --accent: #0066cc;\n"
                "}\n"
                'html[data-theme="ok"] .slide {\n'
                "  background: linear-gradient(180deg, #fff 0%, var(--bg) 100%);\n"
                "}\n"
                'html[data-theme="ok"] .compare-panel--up {\n'
                "  border-color: color-mix(in srgb, var(--accent) 24%, var(--border));\n"
                "}\n",
                encoding="utf-8",
            )
            errors = scan_themes_css(css_path)
        self.assertEqual([], errors)

    def test_scan_reports_low_contrast_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            css_path.write_text(
                'html[data-theme="bad"] {\n'
                "  --text: #cccccc;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #ffffff;\n"
                "  --text-dim: #cccccc;\n"
                "  --accent: #cccccc;\n"
                "}\n",
                encoding="utf-8",
            )
            errors = scan_themes_css(css_path)
        self.assertTrue(errors)
        self.assertTrue(any('data-theme="bad"' in e for e in errors))

    def test_later_duplicate_failing_block_fails_gate_naming_duplicate(self) -> None:
        # CSS cascade applies the LAST block for a given theme name. A
        # passing block followed by a failing block with the SAME name must
        # fail the gate — both because the (now active) failing block is
        # validated, and because the duplicate name itself is an error.
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            css_path.write_text(
                'html[data-theme="dup"] {\n'
                "  --text: #1a1a1a;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #f5f5f7;\n"
                "  --text-dim: #5c6370;\n"
                "  --accent: #0066cc;\n"
                "}\n"
                'html[data-theme="dup"] {\n'
                "  --text: #cccccc;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #ffffff;\n"
                "  --text-dim: #cccccc;\n"
                "  --accent: #cccccc;\n"
                "}\n",
                encoding="utf-8",
            )
            errors = scan_themes_css(css_path)
        self.assertTrue(errors, "duplicate theme with a failing block must fail the gate")
        joined = "\n".join(errors)
        self.assertIn('data-theme="dup"', joined)
        self.assertTrue(
            any("duplicate" in e.lower() or "declared" in e.lower() for e in errors),
            f"expected a duplicate-naming error, got: {errors}",
        )

    def test_scan_reports_unquoted_low_contrast_block(self) -> None:
        # Codex round-2 finding 2: html[data-theme=brand] (no quotes) is
        # valid CSS but was invisible to _THEME_BLOCK_RE, which only matched
        # quoted selectors — a low-contrast unquoted block passed silently.
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            css_path.write_text(
                "html[data-theme=bad-unquoted] {\n"
                "  --text: #cccccc;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #ffffff;\n"
                "  --text-dim: #cccccc;\n"
                "  --accent: #cccccc;\n"
                "}\n",
                encoding="utf-8",
            )
            errors = scan_themes_css(css_path)
        self.assertTrue(errors, "unquoted low-contrast block must not be invisible to the gate")
        self.assertTrue(any('data-theme="bad-unquoted"' in e for e in errors))

    def test_quoted_and_unquoted_duplicate_pair_fails_gate(self) -> None:
        # Same theme name declared once quoted and once unquoted must still
        # be caught as a duplicate — CSS treats both selectors identically.
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            css_path.write_text(
                'html[data-theme="dup-mixed"] {\n'
                "  --text: #1a1a1a;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #f5f5f7;\n"
                "  --text-dim: #5c6370;\n"
                "  --accent: #0066cc;\n"
                "}\n"
                "html[data-theme=dup-mixed] {\n"
                "  --text: #1a1a1a;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #f5f5f7;\n"
                "  --text-dim: #5c6370;\n"
                "  --accent: #0066cc;\n"
                "}\n",
                encoding="utf-8",
            )
            errors = scan_themes_css(css_path)
        self.assertTrue(errors, "a quoted+unquoted duplicate pair must fail the gate")
        joined = "\n".join(errors)
        self.assertIn('data-theme="dup-mixed"', joined)
        self.assertTrue(
            any("duplicate" in e.lower() or "declared" in e.lower() for e in errors),
            f"expected a duplicate-naming error, got: {errors}",
        )

    def test_duplicate_passing_blocks_still_fail_gate(self) -> None:
        # Even if both blocks individually pass contrast, a duplicate theme
        # name is fail-closed on its own — the file must declare each theme
        # id exactly once.
        with tempfile.TemporaryDirectory() as tmp:
            css_path = Path(tmp) / "themes.css"
            block = (
                'html[data-theme="dup-ok"] {\n'
                "  --text: #1a1a1a;\n"
                "  --bg: #ffffff;\n"
                "  --surface: #f5f5f7;\n"
                "  --text-dim: #5c6370;\n"
                "  --accent: #0066cc;\n"
                "}\n"
            )
            css_path.write_text(block + block, encoding="utf-8")
            errors = scan_themes_css(css_path)
        self.assertTrue(errors, "duplicate theme name must fail even if both blocks pass")
        self.assertTrue(any('data-theme="dup-ok"' in e for e in errors))


if __name__ == "__main__":
    unittest.main()
