#!/usr/bin/env python3
"""
Convert a bundled deck HTML back to linked form (so bundle_deck.py will re-process it),
add new module <link>/<script src> tags, write to a temp file, then re-bundle in place.

Usage:
  python3 scripts/_rebundle_helper.py assets/decks/<name>/<name>-slides.html
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Modules to convert back to <link rel="stylesheet" href="../../shared/X.css">.
CSS_MODULES = [
    "premium-themes.css",
    "premium-deck.css",
    "premium-components.css",
    "premium-diagrams.css",
    "premium-annotations.css",
    "premium-extras.css",
    "premium-red-brand.css",
]

# Modules to convert back to <script src="../../shared/X.js" defer></script>.
JS_MODULES = [
    "premium-controller.js",
    "premium-controls.js",
    "premium-annotations.js",
    "premium-red-chrome.js",
    "premium-mermaid.js",
    "premium-journey.js",
    "premium-timer.js",
    "premium-tts.js",
    "premium-search.js",
    "premium-clicker.js",
    "premium-og-cover.js",
    "premium-presenter.js",
    "slide-engine.js",
]

# New modules to insert as <script src> tags before slide-engine.js
NEW_JS_MODULES = [
    "premium-timer.js",
    "premium-tts.js",
    "premium-search.js",
    "premium-clicker.js",
    "premium-og-cover.js",
    "premium-presenter.js",
]


def find_matching_close(text: str, start: int, open_tag: str, close_tag: str) -> int:
    """Find the index AFTER the matching </tag> for the <tag> opened at start.
    Tracks nesting by counting open/close tags. Returns -1 if not found.
    """
    depth = 0
    i = start
    open_re = re.compile(re.escape(open_tag), re.I)
    close_re = re.compile(re.escape(close_tag), re.I)
    while i < len(text):
        # find next open or close
        m_open = open_re.search(text, i)
        m_close = close_re.search(text, i)
        if not m_close:
            return -1
        if m_open and m_open.start() < m_close.start():
            depth += 1
            i = m_open.end()
        else:
            depth -= 1
            i = m_close.end()
            if depth == 0:
                return i
    return -1


def unbundle_css_block(html: str, name: str) -> str:
    """Find ALL <style>\\n/* --- name --- [regenerated] */\\n...content...</style> and replace each with <link>."""
    # Marker is `/* --- name --- */` or the legacy `/* --- name --- regenerated */` variant.
    marker_plain = f"/* --- {name} --- */"
    marker_legacy = f"/* --- {name} --- regenerated */"
    replacement = f'<link rel="stylesheet" href="../../shared/{name}">'
    out = html
    while True:
        idx_plain = out.find(marker_plain)
        idx_legacy = out.find(marker_legacy)
        candidates = [i for i in (idx_plain, idx_legacy) if i != -1]
        if not candidates:
            return out
        idx = min(candidates)
        style_open_idx = out.rfind("<style>", 0, idx)
        if style_open_idx == -1:
            print(f"  WARN: found marker for {name} but no <style> opener before it", file=sys.stderr)
            return out
        style_end = find_matching_close(out, style_open_idx, "<style>", "</style>")
        if style_end == -1:
            print(f"  WARN: no matching </style> for {name}", file=sys.stderr)
            return out
        out = out[:style_open_idx] + replacement + out[style_end:]


def unbundle_js_block(html: str, name: str) -> str:
    """Find ALL <script>\\n/* --- name --- [regenerated] */\\n...content...</script> and replace each with <script src>."""
    marker_plain = f"/* --- {name} --- */"
    marker_legacy = f"/* --- {name} --- regenerated */"
    replacement = f'<script src="../../shared/{name}" defer></script>'
    out = html
    while True:
        idx_plain = out.find(marker_plain)
        idx_legacy = out.find(marker_legacy)
        candidates = [i for i in (idx_plain, idx_legacy) if i != -1]
        if not candidates:
            return out
        idx = min(candidates)
        script_open_idx = out.rfind("<script>", 0, idx)
        if script_open_idx == -1:
            print(f"  WARN: found marker for {name} but no <script> opener before it", file=sys.stderr)
            return out
        script_end = find_matching_close(out, script_open_idx, "<script>", "</script>")
        if script_end == -1:
            print(f"  WARN: no matching </script> for {name}", file=sys.stderr)
            return out
        out = out[:script_open_idx] + replacement + out[script_end:]


def strip_mermaid_inlined_block(html: str) -> str:
    """Remove ALL inlined `premium-mermaid (inlined)` body blocks from the HTML.
    DO NOT strip the mermaid bootstrap — `wants_premium_mermaid` uses the presence
    of `initPremiumMermaid` in the HTML to decide whether to re-include mermaid.
    The bundler will re-create one inlined body and one bootstrap on re-bundle.
    """
    marker = "/* --- premium-mermaid (inlined) --- */"
    out = html
    while marker in out:
        idx = out.find(marker)
        script_open_idx = out.rfind("<script>", 0, idx)
        if script_open_idx == -1:
            print("  WARN: found premium-mermaid (inlined) marker but no <script> opener", file=sys.stderr)
            return out
        script_end = find_matching_close(out, script_open_idx, "<script>", "</script>")
        if script_end == -1:
            print("  WARN: no matching </script> for premium-mermaid (inlined) block", file=sys.stderr)
            return out
        end = script_end
        while end < len(out) and out[end] in " \t\r\n":
            end += 1
        out = out[:script_open_idx] + out[end:]
    return out


def add_new_js_modules(html: str) -> str:
    """Insert NEW_JS_MODULES <script src> tags immediately before the slide-engine.js line."""
    modules = [
        module
        for module in ("premium-controller.js", *NEW_JS_MODULES)
        if module not in html
    ]
    if not modules:
        return html  # already added

    # Find the existing <script src="../../shared/slide-engine.js" defer></script>
    # (added by our unbundling) and insert new tags before it.
    pattern = r'<script\s+src=["\']\.\./\.\./shared/slide-engine\.js["\'][^>]*></script>'
    new_tags = "\n".join(
        f'<script src="../../shared/{m}" defer></script>' for m in modules
    )

    # If slide-engine.js link exists, insert before it
    if re.search(pattern, html, re.I):
        html = re.sub(pattern, new_tags + "\n" + r"\g<0>", html, count=1, flags=re.I)
        return html

    # Otherwise, insert before </head>'s closing region — actually, scripts
    # should be in <body>. Try to find a logical insertion point: after the
    # last existing <script src=...defer></script> in the body.
    body_scripts = list(
        re.finditer(
            r'<script\s+src=["\']\.\./\.\./shared/[^"\']+\.js["\'][^>]*></script>',
            html,
            re.I,
        )
    )
    if body_scripts:
        last = body_scripts[-1]
        html = html[: last.end()] + "\n" + new_tags + html[last.end() :]
        return html

    print("  WARN: could not find slide-engine.js or any body script to insert before", file=sys.stderr)
    return html


def has_mermaid_markup(html: str) -> bool:
    """Check whether the deck has Mermaid diagram markup (class containing 'mermaid')."""
    return bool(re.search(r'class=["\'][^"\']*\bmermaid\b', html, re.I))


def add_mermaid_module_if_needed(html: str) -> str:
    """If the deck has Mermaid markup but no working mermaid setup (no inlined body
    and no <script type='module'> for it), add a <script type='module'> so the
    bundler knows to inline the Mermaid module on re-bundle.
    """
    if "initPremiumMermaid" in html:
        return html  # already has mermaid setup
    if "premium-mermaid.js" in html:
        return html
    if "premium-mermaid (inlined)" in html:
        return html
    if not has_mermaid_markup(html):
        return html

    module_script = """<script type="module">
  import { initPremiumMermaid } from '../../shared/premium-mermaid.js';
  import { initPremiumJourney } from '../../shared/premium-journey.js';

  document.addEventListener('DOMContentLoaded', () => {
    initPremiumJourney();
    initPremiumMermaid()
      .then(() => { new SlideEngine(); })
      .catch((err) => {
        console.error('[Premium Presentations] Mermaid init failed', err);
        new SlideEngine();
      });
  });
</script>
"""
    # Insert just before </body>
    idx = html.lower().rfind("</body>")
    if idx == -1:
        return html + module_script
    return html[:idx] + module_script + html[idx:]


def dedupe_script_srcs(html: str) -> str:
    """Remove duplicate <script src="..."> tags. Keep only the first occurrence of each src.
    After unbundling multiple inlined copies of the same module, the de-bundled HTML
    may have duplicate <script src> tags. The bundler would then inline duplicates.
    """
    seen: set[str] = set()
    pattern = re.compile(
        r'<script\s+src=["\']([^"\']+)["\'][^>]*></script>',
        re.I,
    )

    def repl(m: re.Match[str]) -> str:
        src = m.group(1)
        if src in seen:
            return ""
        seen.add(src)
        return m.group(0)

    return pattern.sub(repl, html)


def add_premium_extras_css(html: str) -> str:
    """Insert <link rel="stylesheet" href="../../shared/premium-extras.css"> after the last
    existing CSS module. The new module has no bundled marker to find, so we add the <link>
    directly. We try, in order:
      1. After the last <link rel="stylesheet" href="../../shared/X.css"> (if de-bundled).
      2. After the last inlined /* --- premium-annotations.css --- */ block (still bundled).
    """
    if "../../shared/premium-extras.css" in html:
        return html  # already present (link or filename)
    if "/* --- premium-extras.css --- */" in html:
        return html  # already inlined

    insertion = '<link rel="stylesheet" href="../../shared/premium-extras.css">'

    # Option 1: existing <link>
    pattern = r'(<link\s+rel=["\']stylesheet["\']\s+href=["\']\.\./\.\./shared/[a-zA-Z0-9_.-]+\.css["\']\s*>)'
    matches = list(re.finditer(pattern, html, re.I))
    if matches:
        last = matches[-1]
        return html[: last.end()] + "\n" + insertion + html[last.end() :]

    # Option 2: inlined /* --- premium-annotations.css --- */ marker.
    # Insert the <link> right BEFORE the <style> block that contains the marker.
    marker = "/* --- premium-annotations.css --- */"
    idx = html.find(marker)
    if idx != -1:
        style_open_idx = html.rfind("<style>", 0, idx)
        if style_open_idx != -1:
            return html[:style_open_idx] + insertion + "\n" + html[style_open_idx:]

    print("  WARN: could not find anchor to insert premium-extras.css <link>", file=sys.stderr)
    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-bundle a deck with new modules")
    parser.add_argument("deck", type=Path, help="Path to the deck HTML to re-bundle")
    args = parser.parse_args()

    deck_path = args.deck.resolve()
    if not deck_path.is_file():
        print(f"Not found: {deck_path}", file=sys.stderr)
        return 1

    html = deck_path.read_text(encoding="utf-8")
    original_len = len(html)

    # Step 0: strip any inlined premium-mermaid (inlined) body + mermaid bootstrap blocks.
    # The bundler re-creates them from the source module; this avoids duplication
    # from decks that have been re-bundled multiple times.
    html = strip_mermaid_inlined_block(html)

    # Step 1: convert bundled CSS blocks back to <link> tags
    for name in CSS_MODULES:
        html = unbundle_css_block(html, name)

    # Step 2: convert bundled JS blocks back to <script src> tags
    for name in JS_MODULES:
        html = unbundle_js_block(html, name)

    # Step 2b: add <link rel="stylesheet" href="../../shared/premium-extras.css">
    # (new module — no bundled marker to find)
    html = add_premium_extras_css(html)

    # Step 3: add new module <script src> tags
    html = add_new_js_modules(html)

    # Step 3b: dedupe <script src> tags (unbundling duplicate inlined blocks
    # creates duplicate <script src> tags, which would cause duplicate inlining).
    html = dedupe_script_srcs(html)

    # Step 3c: if the deck has mermaid markup but no mermaid setup, add a
    # <script type="module"> so the bundler knows to inline the mermaid module.
    html = add_mermaid_module_if_needed(html)

    # Step 4: write to temp file in the same directory (so ../.. paths resolve)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        dir=str(deck_path.parent),
        delete=False,
    ) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(html)

    # Step 5: re-bundle in place
    print(f"De-bundled: {deck_path} ({original_len} → {len(html)} bytes)")
    print(f"  → temp: {tmp_path}")
    bundle_script = ROOT / "scripts" / "bundle-deck.sh"
    result = subprocess.run(
        [str(bundle_script), str(tmp_path), "-o", str(deck_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("Bundle FAILED:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        return 1

    print(result.stdout.strip() or "Bundled.")
    print(result.stderr.strip(), file=sys.stderr)

    # Cleanup temp
    tmp_path.unlink(missing_ok=True)

    # Verify the new modules are in the final deck
    final = deck_path.read_text(encoding="utf-8")
    for mod in ["premium-extras", "premium-controller", "premium-timer", "premium-tts", "premium-search",
                "premium-clicker", "premium-og-cover", "premium-presenter"]:
        if mod not in final:
            print(f"  MISSING: {mod}", file=sys.stderr)
            tmp_path.unlink(missing_ok=True)
            return 1
    print("  All new modules present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
