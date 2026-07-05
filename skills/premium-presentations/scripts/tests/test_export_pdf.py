#!/usr/bin/env python3
"""Tests for export_pdf.py.

Page-count regex unit tests run unconditionally (no browser). The real
export integration test is skipped when Playwright/Chromium is absent,
mirroring validate_layout._playwright_check's degrade-gracefully pattern.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import export_pdf  # noqa: E402

DECK = (
    ROOT / "assets" / "examples" / "rag-vector-graph" / "rag-vector-graph-slides.html"
)

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _authored_slide_count(html_path: Path) -> int:
    """Post-extension slide count from the deck itself — never hardcoded."""
    text = html_path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r'data-nav-title="', text))


def _pdf_has_selectable_text(pdf_bytes: bytes) -> bool:
    """Dep-free spot-check: decompress FlateDecode content streams and look
    for a text-showing operator (Tj/TJ). Confirms real vector text objects
    are present — an image-only (rasterized) PDF would have none."""
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        raw = m.group(1)
        try:
            decompressed = zlib.decompress(raw)
        except zlib.error:
            continue
        if re.search(rb"\bT[jJ]\b", decompressed):
            return True
    return False


class PageCountRegexTests(unittest.TestCase):
    """No browser required — exercises the dep-free counting logic directly."""

    def _fake_pdf(self, n_pages: int) -> bytes:
        objs = "".join(f"{i} 0 obj\n<< /Type /Page /Parent 1 0 R >>\nendobj\n" for i in range(2, 2 + n_pages))
        return f"%PDF-1.4\n1 0 obj\n<< /Type /Pages /Count {n_pages} >>\nendobj\n{objs}".encode()

    def test_counts_page_objects_not_pages_root(self) -> None:
        pdf = self._fake_pdf(5)
        self.assertEqual(export_pdf.count_pdf_pages(pdf), 5)

    def test_does_not_confuse_pages_root_with_page_objects(self) -> None:
        # A /Type /Pages root alone (0 leaf /Type /Page objects) must not
        # be miscounted as a single page via a loose regex.
        pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Pages /Count 3 >>\nendobj\n"
        self.assertIsNone(export_pdf.count_pdf_pages(pdf))

    def test_returns_none_when_no_page_objects_found(self) -> None:
        self.assertIsNone(export_pdf.count_pdf_pages(b"%PDF-1.4\nnothing here"))


class ReconcilePageCountTests(unittest.TestCase):
    """Pure comparison logic — no browser, no PDF bytes required."""

    def test_matching_counts_return_none(self) -> None:
        self.assertIsNone(export_pdf.reconcile_page_count(20, 20))

    def test_mismatched_counts_return_error_message(self) -> None:
        msg = export_pdf.reconcile_page_count(20, 14)
        self.assertIsNotNone(msg)
        self.assertIn("20", msg)
        self.assertIn("14", msg)

    def test_undetermined_actual_returns_error_message(self) -> None:
        msg = export_pdf.reconcile_page_count(20, None)
        self.assertIsNotNone(msg)
        self.assertIn("20", msg)
        self.assertIn("undetermined", msg)


@unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed — skipping export_pdf integration test")
class ExportPdfIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if not DECK.is_file():
            self.skipTest(f"Example deck not found: {DECK}")

    def test_page_count_matches_slide_count(self) -> None:
        expected = _authored_slide_count(DECK)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.pdf"
            rc = export_pdf.export_pdf(DECK, out)
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            pdf_bytes = out.read_bytes()
            self.assertGreater(len(pdf_bytes), 0)
            pages = export_pdf.count_pdf_pages(pdf_bytes)
            if pages is None:
                pages = export_pdf.count_pdf_pages_pdfinfo(out)
            self.assertEqual(pages, expected)

    def test_text_is_selectable_not_raster(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.pdf"
            export_pdf.export_pdf(DECK, out)
            self.assertTrue(_pdf_has_selectable_text(out.read_bytes()))


if __name__ == "__main__":
    unittest.main()
