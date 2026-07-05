#!/usr/bin/env python3
"""Tests for og_cover.py.

The grep guard (AT-003: single browser path) runs unconditionally. The real
render test is skipped when Playwright/Chromium is absent.
"""
from __future__ import annotations

import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import og_cover  # noqa: E402

DECK = (
    ROOT / "assets" / "examples" / "rag-vector-graph" / "rag-vector-graph-slides.html"
)

SYSTEM_CHROME_RE = re.compile(
    r"google-chrome|Google Chrome\.app|/Applications/.*Chrome", re.I
)

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Read width/height from the IHDR chunk — no Pillow dependency."""
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    width, height = struct.unpack(">II", png_bytes[16:24])
    return width, height


class SingleBrowserPathGuardTests(unittest.TestCase):
    def test_no_system_chrome_probing_anywhere_in_scripts(self) -> None:
        offenders = []
        for path in sorted(SCRIPTS.rglob("*")):
            if path.is_dir() or "tests" in path.parts:
                continue
            if path.suffix not in (".py", ".sh", ".js"):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if SYSTEM_CHROME_RE.search(text):
                offenders.append(str(path))
        self.assertEqual(
            offenders, [], f"Found system-Chrome probing in: {offenders}"
        )

    def test_og_cover_sh_deleted(self) -> None:
        self.assertFalse((SCRIPTS / "og-cover.sh").exists())


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed — skipping og_cover render test")
class OgCoverRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        if not DECK.is_file():
            self.skipTest(f"Example deck not found: {DECK}")

    def test_cover_png_is_1200x630(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            deck_copy = Path(tmp) / DECK.name
            deck_copy.write_text(DECK.read_text(encoding="utf-8"), encoding="utf-8")
            rc = og_cover.og_cover(deck_copy)
            self.assertEqual(rc, 0)
            out = deck_copy.with_name("og-cover.png")
            self.assertTrue(out.is_file())
            self.assertEqual(_png_dimensions(out.read_bytes()), (1200, 630))


if __name__ == "__main__":
    unittest.main()
