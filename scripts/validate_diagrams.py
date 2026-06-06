#!/usr/bin/env python3
"""Diagram slide validation — structure, engine CSS/JS, anti-patterns."""

from __future__ import annotations

import re
from pathlib import Path

# Legacy rules that caused clipped diagrams in production
CLIP_HEIGHT_PATTERNS = (
    r"max-height:\s*52vh",
    r"max-height:\s*55vh",
    r"max-height:\s*62vh",
)

REQUIRED_DIAGRAM_CSS_MARKERS = (
    ".diagram-stage",
    "flex: 1 1 0",
    ".mermaid-wrap",
    ".diagram-viewport",
    ".diagram-zoom-pane",
)

REQUIRED_MERMAID_JS_MARKERS = (
    "fitOneMermaidWrap",
    "refineOneMermaidWrap",
    "fitMermaidDiagrams",
    "bindMermaidFit",
    "bindDiagramZoom",
    "prepareDiagramZoomDOM",
    "measureSvg",
    "isDiagramClipped",
)


def find_repo_shared(start: Path) -> Path | None:
    p = start.resolve().parent
    for _ in range(8):
        shared = p / "shared"
        if (shared / "premium-diagrams.css").is_file():
            return shared
        if p.parent == p:
            break
        p = p.parent
    return None


def augment_bundle_for_diagrams(html: str, bundle: str, html_path: Path) -> str:
    if not re.search(r"<pre\s+class=[\"']mermaid[\"']", html, re.I):
        return bundle
    if "fitOneMermaidWrap" in bundle:
        return bundle
    shared = find_repo_shared(html_path)
    if not shared:
        return bundle
    extra = ""
    for name in ("premium-diagrams.css", "premium-mermaid.js"):
        path = shared / name
        if path.is_file():
            extra += path.read_text(encoding="utf-8", errors="replace") + "\n"
    return bundle + extra


def validate_shared_diagram_engine(shared_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    css_path = shared_dir / "premium-diagrams.css"
    js_path = shared_dir / "premium-mermaid.js"

    if not css_path.is_file():
        errors.append(f"Missing {css_path}")
        return errors, warnings

    if not js_path.is_file():
        errors.append(f"Missing {js_path}")
        return errors, warnings

    css = css_path.read_text(encoding="utf-8", errors="replace")
    js = js_path.read_text(encoding="utf-8", errors="replace")

    for marker in REQUIRED_DIAGRAM_CSS_MARKERS:
        if marker not in css:
            errors.append(f"premium-diagrams.css missing required rule/marker: {marker}")

    for pat in CLIP_HEIGHT_PATTERNS:
        if re.search(pat, css):
            errors.append(f"premium-diagrams.css contains clipping pattern {pat}")

    if re.search(r"\.diagram-stage\s*\{[^}]*overflow:\s*auto", css, re.I | re.S):
        warnings.append("diagram-stage overflow:auto — prefer hidden + JS fit")

    for marker in REQUIRED_MERMAID_JS_MARKERS:
        if marker not in js:
            errors.append(f"premium-mermaid.js missing required function: {marker}")

    if "reportDiagramFit" not in js:
        errors.append("premium-mermaid.js missing reportDiagramFit clip detector")

    if re.search(r"useMaxWidth:\s*true", js) and "useMaxWidth: false" not in js:
        errors.append("premium-mermaid.js should set flowchart.useMaxWidth: false for fit logic")

    return errors, warnings


def validate_inline_scripts(html: str) -> tuple[list[str], list[str]]:
    """Detect `</script>` inside inline script bodies (breaks HTML parsing)."""
    errors: list[str] = []
    warnings: list[str] = []
    for match in re.finditer(
        r"<script\b([^>]*)>([\s\S]*?)</script>", html, re.I
    ):
        attrs, body = match.group(1), match.group(2)
        if re.search(r"\bsrc=", attrs, re.I):
            continue
        if re.search(r"</script>", body, re.I):
            errors.append(
                "Inline <script> contains literal </script> — breaks controls/shortcuts; re-bundle with bundle-deck.py"
            )
            break
    return errors, warnings


def validate_deck_diagrams(
    html: str, bundle: str, html_path: Path
) -> tuple[list[str], list[str], int]:
    """Returns (errors, warnings, mermaid_slide_count)."""
    errors: list[str] = []
    warnings: list[str] = []

    mermaid_count = len(re.findall(r"<pre\s+class=[\"']mermaid[\"']", html, re.I))
    if mermaid_count == 0:
        return errors, warnings, 0

    has_diagram_css = (
        "premium-diagrams.css" in html
        or "/* --- premium-diagrams.css --- */" in bundle
        or ".diagram-stage" in bundle
    )
    if not has_diagram_css:
        errors.append(
            "Mermaid slides require premium-diagrams.css (link or bundle)"
        )

    if "diagram-stage" not in html:
        errors.append(
            'Each Mermaid diagram must use <div class="diagram-stage"> wrapping '
            '<div class="mermaid-wrap">'
        )

    if html.count("diagram-stage") < mermaid_count:
        errors.append(
            f"Found {mermaid_count} mermaid diagram(s) but only "
            f"{html.count('diagram-stage')} diagram-stage wrapper(s)"
        )

    for i, match in enumerate(
        re.finditer(r"<pre\s+class=[\"']mermaid[\"']", html, re.I), start=1
    ):
        prefix = html[max(0, match.start() - 1500) : match.start()]
        if "diagram-stage" not in prefix:
            errors.append(f"Mermaid diagram #{i}: missing ancestor .diagram-stage")
        if "mermaid-wrap" not in prefix:
            errors.append(f"Mermaid diagram #{i}: missing wrapper .mermaid-wrap")

    diagram_sections = len(
        re.findall(r"<section\s+class=[\"'][^\"']*\bslide--diagram\b", html, re.I)
    )
    if diagram_sections < mermaid_count:
        warnings.append(
            f"{mermaid_count} mermaid diagram(s) but only {diagram_sections} "
            "slide--diagram section(s) — use slide--diagram on diagram slides"
        )

    if not re.search(r"slide__diagram-header", html):
        warnings.append("Diagram slides should use <header class=\"slide__diagram-header\">")

    for pat in CLIP_HEIGHT_PATTERNS:
        if re.search(pat, bundle):
            errors.append(
                f"Bundle/HTML contains clipping CSS ({pat}) — diagrams will be cut off"
            )

    if re.search(
        r"<div\s+class=[\"'][^\"']*mermaid-wrap[^\"']*[\"'][^>]*\sstyle=[\"'][^\"']*max-height",
        html,
        re.I,
    ):
        errors.append("Inline max-height on mermaid-wrap will clip diagram content")

    has_fit = "fitOneMermaidWrap" in bundle or "fitMermaidDiagrams" in bundle
    has_bind = "bindMermaidFit" in bundle
    has_init = "initPremiumMermaid" in bundle or "initPremiumMermaid" in html

    if not has_fit:
        errors.append(
            "Missing diagram auto-fit (fitMermaidDiagrams / premium-mermaid.js)"
        )
    if not has_bind:
        errors.append(
            "Missing bindMermaidFit — diagrams won't refit on resize or slide enter"
        )
    if not has_init and "../../shared/" in html:
        errors.append(
            "Linked deck with Mermaid must import initPremiumMermaid from premium-mermaid.js"
        )

    if "look: 'handDrawn'" not in bundle and "look: \"handDrawn\"" not in bundle:
        warnings.append("Mermaid handDrawn look not found in bundle — check premium-mermaid.js")

    shared = find_repo_shared(html_path)
    if shared:
        eng_errs, eng_warns = validate_shared_diagram_engine(shared)
        errors.extend(eng_errs)
        warnings.extend(eng_warns)

    return errors, warnings, mermaid_count
