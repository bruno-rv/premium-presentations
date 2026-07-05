#!/usr/bin/env python3
"""Render slide 1 of a deck as a 1200x630 PNG for OG / Twitter cards.

Usage: ./scripts/og_cover.py <deck.html>

Playwright Chromium only — no system-Chrome / .app probing. Replaces
og-cover.sh (removed; had no programmatic callers and shipped the exact
system-Chrome probing this script exists to eliminate).
"""
from __future__ import annotations

import sys
from pathlib import Path


def og_cover(html_path: Path) -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright missing — pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    out = html_path.with_name("og-cover.png")  # bundle_deck.py:418 rewrite target
    url = html_path.resolve().as_uri()  # NORMAL mode, no ?print-pdf
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 630})
            page.goto(url, wait_until="networkidle", timeout=60_000)
            if page.locator(".mermaid-wrap").count():
                page.wait_for_function(
                    "[...document.querySelectorAll('.mermaid-wrap')]"
                    ".every(el => el.querySelector('svg'))",
                    timeout=15_000,
                )
            page.screenshot(
                path=str(out), clip={"x": 0, "y": 0, "width": 1200, "height": 630}
            )
        finally:
            browser.close()
    print(f"Cover written: {out} (1200x630)")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: og_cover.py <deck.html>", file=sys.stderr)
        return 1
    html_path = Path(argv[0])
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1
    return og_cover(html_path)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
