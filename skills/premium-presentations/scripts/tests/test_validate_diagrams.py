#!/usr/bin/env python3
"""Regression tests for inline script structure validation."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_diagrams import validate_inline_scripts  # noqa: E402


class InlineScriptValidationTests(unittest.TestCase):
    def test_balanced_inline_scripts_pass(self) -> None:
        errors, warnings = validate_inline_scripts(
            "<script>window.ok = true;</script><script src=\"runtime.js\"></script>"
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_script_like_open_tag_inside_js_string_and_html_comment_passes(self) -> None:
        html = (
            '<!-- documentation: <script></script> -->'
            '<script>const example = "<script>"; window.ok = example;</script>'
        )
        errors, _ = validate_inline_scripts(html)
        self.assertEqual(errors, [])

    def test_literal_early_close_leaves_extra_closing_tag_and_fails(self) -> None:
        html = '<script>const payload = "</script>"; window.broken = true;</script>'
        errors, _ = validate_inline_scripts(html)
        self.assertTrue(errors)
        self.assertIn("script", errors[0].lower())

    def test_balanced_script_tag_string_cannot_hide_early_close(self) -> None:
        html = (
            '<script>const payload = "<script></script>"; '
            'window.broken = true;</script>'
        )
        errors, _ = validate_inline_scripts(html)
        self.assertTrue(errors)
        self.assertIn("unexpected", errors[0].lower())

    def test_unclosed_script_fails(self) -> None:
        errors, _ = validate_inline_scripts("<script>window.neverClosed = true;")
        self.assertTrue(errors)
        self.assertIn("unclosed", errors[0].lower())


if __name__ == "__main__":
    unittest.main()
