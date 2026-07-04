#!/usr/bin/env python3
"""Tests for validate_deck.py slide-map header parsing (validate(), ~line 305).

Regression coverage for a bug found by Codex review: spec_generator.py and
references/slide-spec-template.md emit a 9-column slide-map header
("| # | Act | Type | ... |"), but the old header-detection matched only the
legacy 5/7-column layout ("| # | Type | ... |"). Against a new-format spec,
zero map rows parsed and a real deck/spec slide-count mismatch silently
degraded from a FAIL to a "no slide map rows parsed" WARN.
"""
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


class SlideMapHeaderParsingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
