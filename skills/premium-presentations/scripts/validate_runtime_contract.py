#!/usr/bin/env python3
"""Validate Premium Presentations template and deck runtime parity."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (
    FLOW_JS,
    GLOSSARY_JS,
    JOURNEY_JS,
    RED_CSS,
    RED_JS,
    REQUIRED_CSS,
    REQUIRED_JS,
    ROOT,
    discover_themes,
)

LINK_RE = re.compile(r"<link\b[^>]*>", re.I)
SCRIPT_RE = re.compile(r"<script\b[^>]*>", re.I)
HREF_RE = re.compile(r"\bhref=[\"']([^\"']+)[\"']", re.I)
SRC_RE = re.compile(r"\bsrc=[\"']([^\"']+)[\"']", re.I)


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def marker_present(html: str, name: str) -> bool:
    pattern = r"/\*\s*---\s*" + re.escape(name) + r"(?:\s+regenerated)?\s*---\s*\*/"
    return bool(re.search(pattern, html, re.I))


def linked_modules(html: str, kind: str, names: tuple[str, ...]) -> set[str]:
    present: set[str] = set()
    if kind == "css":
        for tag in LINK_RE.findall(html):
            if "stylesheet" not in tag.lower():
                continue
            match = HREF_RE.search(tag)
            if not match:
                continue
            href = match.group(1)
            present.update(name for name in names if name in href)
    else:
        for tag in SCRIPT_RE.findall(html):
            match = SRC_RE.search(tag)
            if not match:
                continue
            src = match.group(1)
            present.update(name for name in names if name in src)
    return present


def modules_present(html: str, kind: str, names: tuple[str, ...]) -> set[str]:
    present = linked_modules(html, kind, names)
    present.update(name for name in names if marker_present(html, name))
    return present


def needs_red_runtime(path: Path, html: str) -> bool:
    name = path.name
    root_match = re.search(r"<html\b[^>]*>", html, re.I)
    root_tag = root_match.group(0) if root_match else ""
    return (
        name.startswith("red-")
        or name == "preview-red.html"
        or 'data-theme="red"' in root_tag
        or "data-theme='red'" in root_tag
        or "data-red-" in root_tag
        or marker_present(html, "premium-red-brand.css")
        or marker_present(html, "premium-red-chrome.js")
    )


def needs_journey_runtime(html: str) -> bool:
    return bool(re.search(r"\bclass\s*=\s*[\"'][^\"']*\bjourney-stage\b", html, re.I))


def needs_flow_runtime(html: str) -> bool:
    return bool(re.search(r"\bclass\s*=\s*[\"'][^\"']*\blive-flow\b", html, re.I))


def needs_glossary_runtime(html: str) -> bool:
    return bool(
        re.search(r"\bclass\s*=\s*[\"'][^\"']*\bterm-link\b", html, re.I)
        or re.search(r'\bid\s*=\s*["\']glossary["\']', html, re.I)
    )


def check_file(path: Path, errors: list[str]) -> None:
    html = path.read_text(encoding="utf-8")
    css_required = REQUIRED_CSS + (RED_CSS if needs_red_runtime(path, html) else ())
    js_required = (
        REQUIRED_JS
        + (RED_JS if needs_red_runtime(path, html) else ())
        + (JOURNEY_JS if needs_journey_runtime(html) else ())
        + (FLOW_JS if needs_flow_runtime(html) else ())
        + (GLOSSARY_JS if needs_glossary_runtime(html) else ())
    )

    css_present = modules_present(html, "css", css_required)
    js_present = modules_present(html, "js", js_required)

    missing_css = [name for name in css_required if name not in css_present]
    missing_js = [name for name in js_required if name not in js_present]

    if missing_css:
        errors.append(f"{rel(path)} missing CSS: {', '.join(missing_css)}")
    if missing_js:
        errors.append(f"{rel(path)} missing JS: {', '.join(missing_js)}")


def main() -> int:
    errors: list[str] = []
    themes = discover_themes()
    if not themes:
        errors.append("assets/shared/premium-themes.css declares no html[data-theme=...] selectors")

    premium_base = ROOT / "assets" / "templates" / "premium-base.html"
    for theme in themes:
        template = ROOT / "assets" / "templates" / f"{theme}-base.html"
        check_file(template if template.is_file() else premium_base, errors)

    template_paths = sorted((ROOT / "assets" / "templates").glob("*-base.html"))
    template_paths.extend(sorted((ROOT / "assets" / "templates").glob("preview-*.html")))
    for path in template_paths:
        check_file(path, errors)

    deck_paths = sorted((ROOT / "assets" / "decks").glob("*/*-slides*.html"))
    deck_paths += sorted((ROOT / "assets" / "examples").glob("*/*-slides*.html"))
    for path in deck_paths:
        check_file(path, errors)

    if errors:
        print("Runtime contract FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    checked_templates = len(set(template_paths))
    print(
        "Runtime contract OK: "
        f"{len(themes)} themes, {checked_templates} templates/previews, "
        f"{len(deck_paths)} deck HTML files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
