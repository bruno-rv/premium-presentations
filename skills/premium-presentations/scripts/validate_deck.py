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
from slide_html import SlideHtmlError, parse_slide_spans
from slide_spec import SlideSpecError, parse_slide_map

# Class tokens that count as a visual anchor on a content slide. Mirrors the
# component vocabulary in references/components.md.
COMPONENT_MARKERS = (
    "journey-stage",
    "compare-split",
    "timeline-grid",
    "stage-card",
    "glass-card",
    "code-window",
    "bar-chart",
    "setup-flow",
    "stats-row",
    "checklist-grid",
    "why-panel",
    "live-flow",
    "pipeline-vertical",
    "terminal-window",
    "content-grid",
    "split",
    "kpi-row",
    "aside-card",
    "data-table",
    "mermaid",
    "dp-layout",
    "dp-component",
    "dp-viz",
    "dp-layout--decision-matrix",
    "dp-layout--evidence-wall",
    "dp-layout--executive-summary",
    "dp-layout--process-ladder",
    "dp-component--checklist",
    "dp-component--stats",
    "dp-component--compare",
    "dp-viz--line",
    "dp-viz--scatter",
    "dp-viz--waterfall",
    "dp-viz--funnel",
    "dp-viz--heatmap",
    "dp-viz--sankey",
    "dp-viz--kpi-trend",
)

# Slide-type modifiers that are exempt from the bare-slide rule.
EXEMPT_SLIDE_TYPES = ("slide--title", "slide--quote", "slide--divider", "slide--diagram")

SLIDE_OPEN_RE = re.compile(
    r'<section\s+[^>]*class=["\'][^"\']*\bslide\b[^"\']*["\'][^>]*>', re.I
)
CLASS_ATTR_RE = re.compile(r'class=["\']([^"\']+)["\']', re.I)


def _class_tokens(chunk: str) -> set[str]:
    tokens: set[str] = set()
    for value in CLASS_ATTR_RE.findall(chunk):
        tokens.update(value.split())
    return tokens


def validate_deck_variety(text: str) -> tuple[list[str], int]:
    """Density/variety lint: bare slides, monotone runs, low pattern variety.

    Returns (messages, distinct_pattern_count).
    """
    messages: list[str] = []
    opens = list(SLIDE_OPEN_RE.finditer(text))
    if not opens:
        return messages, 0

    deck_markers: set[str] = set()
    bare: list[int] = []
    for idx, match in enumerate(opens):
        end = opens[idx + 1].start() if idx + 1 < len(opens) else len(text)
        chunk = text[match.start():end]
        tokens = _class_tokens(chunk)
        markers = {m for m in COMPONENT_MARKERS if m in tokens}
        deck_markers.update(markers)
        slide_tokens = _class_tokens(match.group(0))
        if any(t in slide_tokens for t in EXEMPT_SLIDE_TYPES):
            continue
        has_raw_visual = re.search(r"<svg\b|<table\b|<pre\b", chunk, re.I)
        if not markers and not has_raw_visual:
            bare.append(idx + 1)
            messages.append(
                f"bare slide {idx + 1}: heading+text only — add a visual anchor "
                "(see references/components.md)"
            )

    # Runs of >2 consecutive bare slides read as a wall of boxes.
    run: list[int] = []
    for n in bare + [-1]:
        if run and n != run[-1] + 1:
            if len(run) > 2:
                messages.append(
                    f"slides {run[0]}–{run[-1]}: {len(run)} consecutive bare slides — "
                    "vary layouts (journey, compare, flow, pipeline, diagram)"
                )
            run = []
        run.append(n)

    if len(opens) >= 8 and len(deck_markers) < 4:
        messages.append(
            f"low visual variety: {len(deck_markers)} distinct component pattern(s) "
            f"across {len(opens)} slides (target ≥4)"
        )

    return messages, len(deck_markers)


def load_bundle(html_path: Path, text: str) -> str:
    parts = [text]
    for href in re.findall(
        r'<link[^>]+rel=["\']stylesheet["\'][^>]+href=["\']([^"\']+)["\']',
        text,
        re.I,
    ):
        css_path = (html_path.parent / href).resolve()
        if css_path.is_file():
            parts.append(css_path.read_text(encoding="utf-8", errors="replace"))
    for src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text, re.I):
        js_path = (html_path.parent / src).resolve()
        if js_path.is_file():
            parts.append(js_path.read_text(encoding="utf-8", errors="replace"))
    bundle = "\n".join(parts)
    return augment_bundle_for_diagrams(text, bundle, html_path)


def validate(html_path: Path, spec_path: str = "", strict_variety: bool = False) -> int:
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

    try:
        slides = len(parse_slide_spans(text))
    except SlideHtmlError as exc:
        err(f"Invalid slide structure: {exc}")
        slides = 0
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

    v_msgs, distinct_patterns = validate_deck_variety(text)
    if strict_variety:
        errors.extend(v_msgs)
    else:
        warnings.extend(v_msgs)

    slides_with_notes = len(re.findall(r'<aside\s[^>]*class=["\'][^"\']*\bnotes\b', text, re.I))
    if slides > 0 and slides_with_notes < slides:
        missing = slides - slides_with_notes
        warn(
            f"{missing} slide(s) missing <aside class=\"notes\"> — "
            "add speaker notes so the presenter popup has content "
            "(see references/examples.md)"
        )

    # Glossary consistency checks (warnings, never errors).
    # The dictionary itself is validated whenever present — even with zero
    # term-links — so a malformed dict never passes silently. The links↔dict
    # cross-checks stay conditional on term-links existing.
    term_keys_in_html = set(re.findall(r'data-term=["\']([^"\']+)["\']', text, re.I))
    glossary_match = re.search(
        r'<script\s[^>]*\btype=["\']application/json["\'][^>]*\bid=["\']glossary["\'][^>]*>'
        r'([\s\S]*?)</script>',
        text,
        re.I,
    ) or re.search(
        r'<script\s[^>]*\bid=["\']glossary["\'][^>]*\btype=["\']application/json["\'][^>]*>'
        r'([\s\S]*?)</script>',
        text,
        re.I,
    )
    if term_keys_in_html and not glossary_match:
        warn(
            f"{len(term_keys_in_html)} term-link(s) present but no "
            '<script type="application/json" id="glossary"> dictionary found — '
            "add the JSON data block (see references/components.md)"
        )
    if glossary_match:
        import json as _json
        raw = glossary_match.group(1).strip()
        try:
            parsed_dict = _json.loads(raw)
            if not isinstance(parsed_dict, dict):
                warn(
                    "glossary <script id=\"glossary\"> is valid JSON but not an object "
                    "(expected a key→{title,body} mapping)"
                )
            else:
                for entry_key, entry_val in parsed_dict.items():
                    if not isinstance(entry_val, dict):
                        warn(
                            f'glossary entry "{entry_key}" is not an object '
                            "(expected {{title, body}})"
                        )
                    elif not entry_val.get("title") or not entry_val.get("body"):
                        missing_fields = [
                            f for f in ("title", "body") if not entry_val.get(f)
                        ]
                        warn(
                            f'glossary entry "{entry_key}" missing field(s): '
                            + ", ".join(missing_fields)
                        )
                if term_keys_in_html:
                    missing_keys = term_keys_in_html - set(parsed_dict.keys())
                    if missing_keys:
                        warn(
                            f"{len(missing_keys)} term-link key(s) missing from glossary dictionary: "
                            + ", ".join(sorted(missing_keys))
                        )
        except _json.JSONDecodeError as exc:
            warn(
                f"glossary <script id=\"glossary\"> contains malformed JSON "
                f"({exc}) — term-links will not resolve"
            )

    if standalone and "PremiumPresentations" not in bundle:
        errors.append(
            "Standalone deck missing PremiumPresentations — controls script likely truncated; re-bundle"
        )

    expected = None
    if spec_path and Path(spec_path).is_file():
        spec = Path(spec_path).read_text(encoding="utf-8", errors="replace")
        try:
            parsed_spec = parse_slide_map(spec)
        except SlideSpecError as exc:
            if exc.code == "no_slide_map":
                warn("Spec provided but no slide map rows parsed")
            else:
                err(f"Invalid Slide Map: {exc}")
        else:
            expected = len(parsed_spec.rows)
            if expected != slides:
                err(f"Slide count mismatch: HTML has {slides}, spec slide map has {expected}")

    print(f"Validating: {html_path}")
    print(f"  Slides found: {slides}")
    print(f"  Visual patterns: {distinct_patterns} distinct")
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
    args = [a for a in sys.argv[1:] if a != "--strict-variety"]
    strict_variety = "--strict-variety" in sys.argv[1:]
    html = args[0] if args else ""
    spec = args[1] if len(args) > 1 else ""
    if not html or not Path(html).is_file():
        print(
            "Usage: validate_deck.py <deck.html> [slide-spec.md] [--strict-variety]",
            file=sys.stderr,
        )
        return 1
    return validate(Path(html), spec, strict_variety=strict_variety)


if __name__ == "__main__":
    sys.exit(main())
