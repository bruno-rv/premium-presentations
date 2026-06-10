#!/usr/bin/env python3
"""Validate a Premium Presentations HTML deck (+ optional spec)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_diagrams import (
    augment_bundle_for_diagrams,
    validate_deck_diagrams,
    validate_inline_scripts,
)
from validate_layout import validate_deck_layout


def load_bundle(html_path: Path, text: str) -> str:
    bundle = text
    for href in re.findall(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']',
        text,
        re.I,
    ):
        css_path = (html_path.parent / href).resolve()
        if css_path.is_file():
            bundle += "\n" + css_path.read_text(encoding="utf-8", errors="replace")
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.I):
        js_path = (html_path.parent / src).resolve()
        if js_path.is_file():
            bundle += "\n" + js_path.read_text(encoding="utf-8", errors="replace")
    return augment_bundle_for_diagrams(text, bundle, html_path)


def validate(html_path: Path, spec_path: str = "") -> int:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    bundle = load_bundle(html_path, text)
    errors: list[str] = []
    warnings: list[str] = []

    def err(msg: str) -> None:
        errors.append(msg)

    def warn(msg: str) -> None:
        warnings.append(msg)

    if not text.lstrip().lower().startswith("<!doctype html"):
        err("Missing <!DOCTYPE html>")

    if not re.search(r"<html[^>]*\blang=", text, re.I):
        err("Missing lang on <html>")

    if 'id="deck"' not in text and "id='deck'" not in text:
        err('Missing <div id="deck">')

    slides = len(re.findall(r'<section\s+class="[^"]*\bslide\b', text, re.I))
    if slides == 0:
        err('No <section class="... slide ..."> found')
    elif slides < 2:
        warn(f"Only {slides} slide(s) — decks usually have 2+")

    if "prefers-reduced-motion" not in bundle:
        err("Missing prefers-reduced-motion (in HTML or linked shared CSS)")

    has_engine = "SlideEngine" in bundle or "slide-engine.js" in text
    if not has_engine:
        err("Missing SlideEngine (inline or shared/slide-engine.js)")

    if "scroll-snap" not in bundle:
        warn("No scroll-snap CSS (in HTML or linked shared CSS)")

    if "premium-themes.css" not in text and "data-theme=" not in text:
        warn("No premium-themes.css / data-theme — theme switching may be unavailable")

    standalone = "../../shared/" not in text and "/* --- premium-themes.css --- */" in bundle

    if not standalone:
        if "premium-controls.js" not in text:
            warn("No premium-controls.js — theme / 3D controls not wired (or not bundled)")
        if "premium-annotations.js" not in text:
            warn("No premium-annotations.js — marker / laser not wired (or not bundled)")
    else:
        if "PremiumPresentations" not in bundle and "premium-controls" not in bundle.lower():
            warn("Standalone deck may be missing inlined controls JS")
        if "SlideEngine" not in bundle:
            err("Standalone deck missing SlideEngine")

    if "premium-bg-3d" not in bundle:
        warn("No 3D background styles (premium-themes.css may be missing)")

    if re.search(r"\bReveal\.js\b|reveal\.js", text, re.I):
        err("External Reveal.js reference found — use Premium SlideEngine only")

    if ".observe &&" in text or "observe(s)\n    );" in text:
        err("Suspicious IntersectionObserver code (possible duplicate/broken observe)")

    s_errs, s_warns = validate_inline_scripts(text)
    errors.extend(s_errs)
    warnings.extend(s_warns)

    d_errs, d_warns, mermaid_count = validate_deck_diagrams(text, bundle, html_path)
    errors.extend(d_errs)
    warnings.extend(d_warns)

    l_errs, l_warns = validate_deck_layout(text, bundle, html_path)
    errors.extend(l_errs)
    warnings.extend(l_warns)

    if standalone and "PremiumPresentations" not in bundle:
        errors.append(
            "Standalone deck missing PremiumPresentations — controls script likely truncated; re-bundle"
        )

    expected = None
    if spec_path and Path(spec_path).is_file():
        spec = Path(spec_path).read_text(encoding="utf-8", errors="replace")
        in_map = False
        map_rows = []
        for line in spec.splitlines():
            if "| # | Type |" in line or "| # | Type | Title |" in line:
                in_map = True
                continue
            if in_map and line.startswith("|") and re.match(r"^\|\s*\d+\s*\|", line):
                map_rows.append(line)
            elif in_map and line.startswith("## ") and "Slide Map" not in line:
                break
        if map_rows:
            expected = len(map_rows)
            if expected != slides:
                err(f"Slide count mismatch: HTML has {slides}, spec slide map has {expected}")
        else:
            warn("Spec provided but no slide map rows parsed")

    print(f"Validating: {html_path}")
    print(f"  Slides found: {slides}")
    if mermaid_count:
        print(f"  Mermaid diagrams: {mermaid_count}")
    if expected is not None:
        print(f"  Spec expects: {expected}")

    for w in warnings:
        print(f"  WARN: {w}")
    for e in errors:
        print(f"  FAIL: {e}")

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) — INVALID")
        return 1
    print(f"\nOK — {len(warnings)} warning(s)")
    return 0


def main() -> int:
    html = sys.argv[1] if len(sys.argv) > 1 else ""
    spec = sys.argv[2] if len(sys.argv) > 2 else ""
    if not html or not Path(html).is_file():
        print("Usage: validate_deck.py <deck.html> [slide-spec.md]", file=sys.stderr)
        return 1
    return validate(Path(html), spec)


if __name__ == "__main__":
    sys.exit(main())
