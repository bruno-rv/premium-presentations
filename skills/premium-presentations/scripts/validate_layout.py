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

READINESS_JS = """
async (theme) => {
  document.documentElement.dataset.theme = theme;
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );
}
"""

LAYOUT_SNAPSHOT_JS = """
async (config) => {
  if (document.fonts && document.fonts.ready) await document.fonts.ready;
  await new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  );

  let measurementStyle = document.getElementById('premium-layout-validation-style');
  if (!measurementStyle) {
    measurementStyle = document.createElement('style');
    measurementStyle.id = 'premium-layout-validation-style';
    measurementStyle.textContent = `
      section.slide[data-layout-validation] {
        opacity: 1 !important;
        transform: none !important;
        transition: none !important;
      }
      section.slide[data-layout-validation] * {
        animation: none !important;
        transition: none !important;
      }
      section.slide[data-layout-validation] .reveal {
        opacity: 1 !important;
        transform: none !important;
      }
    `;
    document.head.appendChild(measurementStyle);
  }

  const measureSlide = (slide, measure) => {
    const hadMarker = slide.hasAttribute('data-layout-validation');
    const markerValue = slide.getAttribute('data-layout-validation');
    const wasVisible = slide.classList.contains('visible');
    slide.setAttribute('data-layout-validation', '');
    slide.classList.add('visible');
    void slide.offsetHeight;
    try {
      return measure();
    } finally {
      if (!wasVisible) slide.classList.remove('visible');
      if (hadMarker) slide.setAttribute('data-layout-validation', markerValue || '');
      else slide.removeAttribute('data-layout-validation');
    }
  };

  const dividerIssues = [];
  document.querySelectorAll('section.slide--divider').forEach((slide, idx) => {
    measureSlide(slide, () => {
      const num = slide.querySelector('.slide__number');
      if (!num) {
        dividerIssues.push({ slide: idx + 1, problem: 'missing .slide__number' });
        return;
      }
      const sr = slide.getBoundingClientRect();
      const nr = num.getBoundingClientRect();
      if (nr.width < 2 || nr.height < 2) {
        dividerIssues.push({ slide: idx + 1, problem: 'ghost number not laid out' });
        return;
      }
      const sides = [];
      if (nr.left < sr.left - config.tolerance) sides.push('left');
      if (nr.right > sr.right + config.tolerance) sides.push('right');
      if (nr.top < sr.top - config.tolerance) sides.push('top');
      if (nr.bottom > sr.bottom + config.tolerance) sides.push('bottom');
      if (num.scrollHeight > num.clientHeight + config.tolerance) sides.push('overflow-y');
      if (num.scrollWidth > num.clientWidth + config.tolerance) sides.push('overflow-x');
      try {
        const range = document.createRange();
        range.selectNodeContents(num);
        const tr = range.getBoundingClientRect();
        if (tr.width > 2 && tr.height > 2) {
          if (tr.left < sr.left - config.tolerance) sides.push('glyph-left');
          if (tr.right > sr.right + config.tolerance) sides.push('glyph-right');
          if (tr.top < sr.top - config.tolerance) sides.push('glyph-top');
          if (tr.bottom > sr.bottom + config.tolerance) sides.push('glyph-bottom');
        }
      } catch (_e) {}
      if (sides.length) {
        dividerIssues.push({
          slide: idx + 1,
          problem: 'ghost number clipped: ' + [...new Set(sides)].join(', '),
          navTitle: slide.getAttribute('data-nav-title') || '',
        });
      }
    });
  });

  const slideOverlaps = [];
  document.querySelectorAll('section.slide').forEach((slide, idx) => {
    const issues = measureSlide(slide, () => {
      const nodes = [];
      for (const sel of config.selectors) {
        slide.querySelectorAll(sel).forEach((el) => {
          if (el.closest('.slide__number')) return;
          const st = getComputedStyle(el);
          if (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0') return;
          const r = el.getBoundingClientRect();
          if (r.width < 8 || r.height < 8) return;
          nodes.push({ el, r, sel });
        });
      }

      const found = [];
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
          if (minArea <= 0 || inter / minArea < config.ratioMin) continue;
          if (nodes[i].el.contains(nodes[j].el) || nodes[j].el.contains(nodes[i].el)) continue;
          found.push({
            a: nodes[i].sel,
            b: nodes[j].sel,
            ratio: Math.round((inter / minArea) * 100),
          });
        }
      }
      return found;
    });
    slideOverlaps.push({
      slide: idx + 1,
      navTitle: slide.getAttribute('data-nav-title') || '',
      issues,
    });
  });

  return { dividerIssues, slideOverlaps };
}
"""


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

    viewports = [(1280, 720), (1440, 900), (1920, 1080)]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)

            for theme in themes:
                page.evaluate(READINESS_JS, theme)

                for vw, vh in viewports:
                    page.set_viewport_size({"width": vw, "height": vh})
                    snapshot = page.evaluate(
                        LAYOUT_SNAPSHOT_JS,
                        {
                            "selectors": list(OVERLAP_SELECTORS),
                            "tolerance": CLIP_TOLERANCE_PX,
                            "ratioMin": OVERLAP_RATIO_WARN,
                        },
                    )

                    for c in snapshot["dividerIssues"]:
                        title = c.get("navTitle") or f"divider #{c.get('slide')}"
                        msg = f"[{theme} {vw}x{vh}] {title}: {c.get('problem')}"
                        errors.append(msg)

                    for slide in snapshot["slideOverlaps"]:
                        nav = slide.get("navTitle") or f"slide {slide['slide']}"
                        for o in slide["issues"][:5]:
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
