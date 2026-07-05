#!/usr/bin/env python3
"""Export a bundled deck to PDF via the runtime's own ?print-pdf layout.

Usage: ./scripts/export_pdf.py <deck.html> [-o out.pdf]
One slide -> one 16:9 landscape page, selectable text, backgrounds printed.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

# Dep-free page-count regex: counts individual /Type /Page objects (the
# negative lookahead excludes the /Type /Pages tree-root dict). Empirically
# verified against real Chromium page.pdf() output (Skia/PDF m149): matches
# pdfinfo's page count exactly. The alternative — reading /Count off the
# /Type /Pages root — is NOT used here: it returned a wrong count (8 instead
# of 14) on the same PDF because Chromium compresses the page tree into an
# object stream, leaving the root's /Count field unreadable by plain regex.
_PAGE_OBJECT_RE = re.compile(rb"/Type\s*/Page(?!s)\b")


def count_pdf_pages(pdf_bytes: bytes) -> int | None:
    """Best-effort, dep-free PDF page count. Returns None if undetermined."""
    count = len(_PAGE_OBJECT_RE.findall(pdf_bytes))
    if count:
        return count
    return None


def count_pdf_pages_pdfinfo(pdf_path: Path) -> int | None:
    """Optional fallback via poppler's pdfinfo — never a hard dependency."""
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo:
        return None
    try:
        out = subprocess.run(
            [pdfinfo, str(pdf_path)], capture_output=True, text=True, timeout=30
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"^Pages:\s+(\d+)", out, re.M)
    return int(m.group(1)) if m else None


def reconcile_page_count(expected: int, actual: int | None) -> str | None:
    """Compare the DOM slide count against the generated PDF's page count.

    Returns an error message if the PDF is untrustworthy (page count
    undetermined or mismatched), or None when it checks out.
    """
    if actual is None:
        return f"expected {expected} page(s), got: undetermined page count"
    if actual != expected:
        return f"expected {expected} page(s), got {actual}"
    return None


def export_pdf(html_path: Path, out_path: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright missing — pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    url = html_path.resolve().as_uri() + "?print-pdf=1"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            # ADR-c trap 2: stop the runtime's terminal window.print() from firing
            # afterprint (which strips body.print-pdf). The stub doubles as the
            # "settling complete" signal — the runtime calls print() only after
            # fonts+images+mermaid+double-rAF have all resolved.
            page.add_init_script("window.print = () => { window.__pdfReady = true; };")
            page.goto(url, wait_until="networkidle", timeout=60_000)
            page.wait_for_function("window.__pdfReady === true", timeout=30_000)
            # Supplementary deterministic gate (AT-002): every mermaid-wrap has
            # rendered an <svg>. NOTE: premium-mermaid.js REPLACES the source
            # <pre class="mermaid"> element with the rendered <svg> — the <pre>
            # does not survive rendering and never contains the <svg> as a
            # child. A selector of ".mermaid-wrap pre.mermaid" (matching zero
            # elements pre- and post-render) would make this wait vacuously
            # true without ever confirming the diagram rendered. Checking the
            # wrapper (which survives) for a descendant <svg> is the correct,
            # empirically-verified gate; it is still vacuously (and correctly)
            # true for decks with no Mermaid diagrams at all.
            page.wait_for_function(
                "[...document.querySelectorAll('.mermaid-wrap')]"
                ".every(el => el.querySelector('svg'))",
                timeout=30_000,
            )
            # Expected page count from the settled DOM — one <section class="slide">
            # per printed page (same selector validate_layout.py uses to walk slides).
            expected = page.evaluate("document.querySelectorAll('section.slide').length")
            # ADR-d: the @page rule (13.333in x 7.5in = 1280x720) is authoritative.
            page.pdf(path=str(out_path), prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()

    pdf_bytes = out_path.read_bytes()
    pages = count_pdf_pages(pdf_bytes)
    if pages is None:
        pages = count_pdf_pages_pdfinfo(out_path)

    mismatch = reconcile_page_count(expected, pages)
    if mismatch:
        print(f"PDF page count check failed for {out_path}: {mismatch}", file=sys.stderr)
        return 1

    print(f"PDF written: {out_path}, {pages} page(s)")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: export_pdf.py <deck.html> [-o out.pdf]", file=sys.stderr)
        return 1
    html_path = Path(argv[0])
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1
    out = (
        Path(argv[2])
        if len(argv) > 2 and argv[1] == "-o"
        else html_path.with_name(html_path.stem.replace("-slides", "") + ".pdf")
    )
    return export_pdf(html_path, out)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
