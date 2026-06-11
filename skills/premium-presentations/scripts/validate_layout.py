#!/usr/bin/env python3
"""Layout validation — divider ghost numbers clipped, component overlap."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import discover_themes
from _common import find_repo_shared as _find_repo_shared

CLIP_TOLERANCE_PX = 6
OVERLAP_RATIO_WARN = 0.12

REQUIRED_DIVIDER_CSS_MARKERS = (
    "--divider-nav-inset",
    "--divider-pad-inline",
    "--divider-pad-block",
    ".slide--divider .slide__number",
    "right: var(--divider-nav-inset)",
    "bottom: var(--divider-pad-block)",
)

# Patterns that tend to clip ghost numerals (horizontal rail, vertical descenders, tight metrics)
DIVIDER_NUMBER_ANTIPATTERNS = (
    r"\.slide--divider\s+\.slide__number\s*\{[^}]*left:\s*50%",
    r"\.slide--divider\s+\.slide__number\s*\{[^}]*font-size:\s*min\([^)]*22vw",
    r"\.slide--divider\s+\.slide__number\s*\{[^}]*line-height:\s*0\.",
    r"\.slide--divider\s+\.slide__number\s*\{[^}]*translateY\s*\(\s*-5[0-9]%",
    r"\.slide--divider\s+\.slide__number\s*\{[^}]*top:\s*50%",
)

def _css_rule_block(css: str, selector: str) -> str | None:
    """Return declaration block for a simple selector (no nested braces)."""
    m = re.search(
        re.escape(selector) + r"\s*\{",
        css,
        re.I,
    )
    if not m:
        return None
    start = m.end()
    depth = 1
    i = start
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[start : i - 1] if depth == 0 else None


def _divider_number_max_width_issue(block: str) -> bool:
    for m in re.finditer(r"max-width\s*:\s*([^;]+)", block, re.I):
        val = m.group(1).strip().lower()
        if val != "none":
            return True
    return False


OVERLAP_SELECTORS = (
    ".slide__display",
    ".slide__heading",
    ".slide__body",
    ".slide__diagram-header",
    ".mermaid-wrap",
    ".diagram-zoom-toolbar",
    ".focus-frame",
    ".compare-split",
    ".stats-row",
    ".journey-stage",
    ".stage-card",
    ".red-brand-bar",
)


def find_repo_shared(start: Path) -> Path | None:
    return _find_repo_shared(start, sentinel="premium-components.css")


def validate_shared_divider_css(shared_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    css_path = shared_dir / "premium-components.css"
    if not css_path.is_file():
        errors.append(f"Missing {css_path}")
        return errors, warnings

    css = css_path.read_text(encoding="utf-8", errors="replace")

    for marker in REQUIRED_DIVIDER_CSS_MARKERS:
        if marker not in css:
            errors.append(f"premium-components.css missing divider layout marker: {marker}")

    for pat in DIVIDER_NUMBER_ANTIPATTERNS:
        if re.search(pat, css, re.I | re.S):
            errors.append(
                f"premium-components.css divider ghost number antipattern ({pat}) — risk of clipped act numbers"
            )

    number_block = _css_rule_block(css, ".slide--divider .slide__number")
    if number_block and _divider_number_max_width_issue(number_block):
        warnings.append(
            "divider .slide__number uses max-width — prefer left/right inset band centering"
        )

    return errors, warnings


def validate_deck_divider_markup(html: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    dividers = list(
        re.finditer(
            r'<section\s+class="[^"]*\bslide--divider\b[^"]*"[^>]*>',
            html,
            re.I,
        )
    )
    if not dividers:
        return errors, warnings

    for i, match in enumerate(dividers, start=1):
        start = match.start()
        end = html.find("</section>", start)
        if end == -1:
            continue
        chunk = html[start:end]
        if "slide__number" not in chunk:
            errors.append(f"Act divider slide #{i}: missing .slide__number ghost numeral")

    return errors, warnings


def _playwright_check(html_path: Path) -> tuple[list[str], list[str]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], [
            "Layout pixel checks skipped — pip install playwright && playwright install chromium"
        ]

    errors: list[str] = []
    warnings: list[str] = []
    url = html_path.resolve().as_uri()
    themes = discover_themes()

    overlap_js = """
    (selectors) => {
      const tol = %d;
      const ratioMin = %s;
      const issues = [];
      const slide = document.querySelector('.slide.visible') || document.querySelector('.slide');
      if (!slide) return issues;

      const nodes = [];
      for (const sel of selectors) {
        slide.querySelectorAll(sel).forEach((el) => {
          if (el.closest('.slide__number')) return;
          const st = getComputedStyle(el);
          if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return;
          const r = el.getBoundingClientRect();
          if (r.width < 8 || r.height < 8) return;
          nodes.push({ el, r, sel });
        });
      }

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i].r;
          const b = nodes[j].r;
          const x0 = Math.max(a.left, b.left);
          const y0 = Math.max(a.top, b.top);
          const x1 = Math.min(a.right, b.right);
          const y1 = Math.min(a.bottom, b.bottom);
          if (x1 <= x0 || y1 <= y0) continue;
          const inter = (x1 - x0) * (y1 - y0);
          const minArea = Math.min(a.width * a.height, b.width * b.height);
          if (minArea <= 0) continue;
          if (inter / minArea < ratioMin) continue;
          if (nodes[i].el.contains(nodes[j].el) || nodes[j].el.contains(nodes[i].el)) continue;
          issues.push({
            a: nodes[i].sel,
            b: nodes[j].sel,
            ratio: Math.round((inter / minArea) * 100),
          });
        }
      }
      return issues;
    }
    """ % (CLIP_TOLERANCE_PX, OVERLAP_RATIO_WARN)

    clip_js = """
    () => {
      const tol = %d;
      const issues = [];
      document.querySelectorAll('section.slide--divider').forEach((slide, idx) => {
        const num = slide.querySelector('.slide__number');
        if (!num) {
          issues.push({ slide: idx + 1, problem: 'missing .slide__number' });
          return;
        }
        const sr = slide.getBoundingClientRect();
        const nr = num.getBoundingClientRect();
        if (nr.width < 2 || nr.height < 2) {
          issues.push({ slide: idx + 1, problem: 'ghost number not laid out' });
          return;
        }
        const sides = [];
        if (nr.left < sr.left - tol) sides.push('left');
        if (nr.right > sr.right + tol) sides.push('right');
        if (nr.top < sr.top - tol) sides.push('top');
        if (nr.bottom > sr.bottom + tol) sides.push('bottom');
        if (num.scrollHeight > num.clientHeight + tol) sides.push('overflow-y');
        if (num.scrollWidth > num.clientWidth + tol) sides.push('overflow-x');
        let textClip = '';
        try {
          const range = document.createRange();
          range.selectNodeContents(num);
          const tr = range.getBoundingClientRect();
          if (tr.width > 2 && tr.height > 2) {
            if (tr.left < sr.left - tol) sides.push('glyph-left');
            if (tr.right > sr.right + tol) sides.push('glyph-right');
            if (tr.top < sr.top - tol) sides.push('glyph-top');
            if (tr.bottom > sr.bottom + tol) sides.push('glyph-bottom');
          }
        } catch (_e) {
          textClip = '';
        }
        if (sides.length) {
          const uniq = [...new Set(sides)];
          issues.push({
            slide: idx + 1,
            problem: 'ghost number clipped: ' + uniq.join(', '),
            navTitle: slide.getAttribute('data-nav-title') || '',
          });
        }
      });
      return issues;
    }
    """ % (CLIP_TOLERANCE_PX)

    viewports = [(1280, 720), (1440, 900), (1920, 1080)]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)

            for theme in themes:
                page.evaluate(
                    "(t) => { document.documentElement.dataset.theme = t; }",
                    theme,
                )
                page.wait_for_timeout(150)

                for vw, vh in viewports:
                    page.set_viewport_size({"width": vw, "height": vh})
                    page.wait_for_timeout(100)

                    dividers = page.locator("section.slide--divider")
                    count = dividers.count()
                    for idx in range(count):
                        dividers.nth(idx).scroll_into_view_if_needed()
                        page.wait_for_timeout(200)
                        clips = page.evaluate(clip_js)
                        for c in clips:
                            title = c.get("navTitle") or f"divider #{c.get('slide')}"
                            msg = f"[{theme} {vw}x{vh}] {title}: {c.get('problem')}"
                            errors.append(msg)

                    slides = page.locator("section.slide")
                    sc = slides.count()
                    for idx in range(sc):
                        slides.nth(idx).scroll_into_view_if_needed()
                        page.wait_for_timeout(120)
                        overlaps = page.evaluate(overlap_js, list(OVERLAP_SELECTORS))
                        for o in overlaps[:5]:
                            nav = slides.nth(idx).get_attribute("data-nav-title") or f"slide {idx + 1}"
                            warnings.append(
                                f"[{theme} {vw}x{vh}] {nav}: overlap {o['a']} ∩ {o['b']} (~{o['ratio']}%)"
                            )
        finally:
            browser.close()

    return errors, warnings


def validate_deck_layout(
    html: str, bundle: str, html_path: Path
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    e, w = validate_deck_divider_markup(html)
    errors.extend(e)
    warnings.extend(w)

    shared = find_repo_shared(html_path)
    if shared:
        e, w = validate_shared_divider_css(shared)
        errors.extend(e)
        warnings.extend(w)
    else:
        warnings.append("Could not locate shared/ for divider CSS rules check")

    if "slide--divider" in html or ".slide--divider" in bundle:
        for pat in DIVIDER_NUMBER_ANTIPATTERNS:
            if re.search(pat, bundle, re.I | re.S):
                errors.append(
                    f"Bundle contains divider ghost number antipattern — act numerals may clip"
                )
                break

    try:
        px_errs, px_warns = _playwright_check(html_path)
        errors.extend(px_errs)
        warnings.extend(px_warns)
    except Exception as exc:
        warnings.append(f"Layout pixel checks failed: {exc}")

    return errors, warnings
