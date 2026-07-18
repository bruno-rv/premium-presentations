#!/usr/bin/env python3
"""Tests for deck_doctor.py — healthy deck exits 0, broken deck exits 1."""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import deck_doctor  # noqa: E402
import validate_layout  # noqa: E402
from _common import REQUIRED_CSS, REQUIRED_JS  # noqa: E402


def _make_deck_html(slide_count: int) -> str:
    """Minimal bundled-deck fixture satisfying every validator's happy path."""
    css_markers = "\n".join(f"/* --- {name} --- */" for name in REQUIRED_CSS)
    js_markers = "\n".join(f"/* --- {name} --- */" for name in REQUIRED_JS)
    slides = "".join(
        f'<section class="slide slide--title"><h1>Slide {i}</h1>'
        '<aside class="notes">Notes.</aside></section>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<!doctype html><html lang="en"><head><style>\n'
        f"{css_markers}\n"
        "@media (prefers-reduced-motion: reduce) {}\n"
        ".deck { scroll-snap-type: y mandatory; }\n"
        ".premium-bg-3d {}\n"
        "</style></head><body>"
        f'<div id="deck">{slides}</div>'
        f"<script>\n{js_markers}\n"
        "window.PremiumPresentations = {};\n"
        "new SlideEngine();\n"
        "</script></body></html>"
    )


SPEC_2_ROWS = """## Slide Map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | III | closing | End | ... | ... | ... | ... | ... |
"""

SPEC_5_ROWS = """## Slide Map

| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|--------------|-----------------|-----------|-----------------|-----------------|
| 1 | I | title | Intro | ... | ... | ... | ... | ... |
| 2 | I | content | A | ... | ... | ... | ... | ... |
| 3 | II | content | B | ... | ... | ... | ... | ... |
| 4 | II | content | C | ... | ... | ... | ... | ... |
| 5 | III | closing | End | ... | ... | ... | ... | ... |
"""


def run_doctor(html: str, spec_text: str) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "deck.html"
        spec_path = Path(tmp) / "spec.md"
        html_path.write_text(html, encoding="utf-8")
        spec_path.write_text(spec_text, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = deck_doctor.main([str(html_path), str(spec_path)])
        return rc, buf.getvalue()


class DeckDoctorTests(unittest.TestCase):
    def test_healthy_deck_exits_zero_with_healthy_verdict(self) -> None:
        rc, out = run_doctor(_make_deck_html(2), SPEC_2_ROWS)
        self.assertEqual(rc, 0, f"Expected healthy exit 0:\n{out}")
        self.assertIn("DECK HEALTHY", out)
        self.assertIn("[✓] validate_deck", out)
        self.assertIn("[✓] validate_runtime_contract", out)

    def test_spec_mismatch_exits_one_with_issue_verdict(self) -> None:
        rc, out = run_doctor(_make_deck_html(2), SPEC_5_ROWS)
        self.assertEqual(rc, 1, f"Expected exit 1 for spec mismatch:\n{out}")
        self.assertNotIn("DECK HEALTHY", out)
        self.assertIn("[✗] validate_deck", out)
        self.assertIn("issue(s)", out)

    def test_nonexistent_spec_path_exits_one_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "deck.html"
            html_path.write_text(_make_deck_html(2), encoding="utf-8")
            bogus_spec = Path(tmp) / "typo-spec.md"
            buf = io.StringIO()
            with contextlib.redirect_stderr(buf):
                rc = deck_doctor.main([str(html_path), str(bogus_spec)])
            err = buf.getvalue()
        self.assertEqual(rc, 1, f"Expected exit 1 for missing spec:\n{err}")
        self.assertIn("Spec not found", err)
        self.assertIn(str(bogus_spec), err)

    def test_relative_media_reference_fails_portability_gate(self) -> None:
        html = _make_deck_html(2).replace(
            "</body>", '<img src="images/missing.webp" alt="">\n</body>'
        )
        rc, out = run_doctor(html, SPEC_2_ROWS)
        self.assertEqual(rc, 1)
        self.assertIn("[✗] validate_portability", out)
        self.assertIn("images/missing.webp", out)

    def test_layout_validation_runs_once_and_rejects_layout_errors(self) -> None:
        sweeps = 0

        def playwright_sweep(*_args: object) -> tuple[list[str], list[str]]:
            nonlocal sweeps
            sweeps += 1
            return ["layout sweep failed"], []

        with mock.patch.object(
            validate_layout, "_playwright_check", side_effect=playwright_sweep
        ):
            rc, out = run_doctor(_make_deck_html(2), SPEC_2_ROWS)

        self.assertEqual(sweeps, 1)
        self.assertEqual(rc, 1)
        self.assertIn("[✗] validate_deck", out)
        self.assertIn("layout sweep failed", out)


if __name__ == "__main__":
    unittest.main()
