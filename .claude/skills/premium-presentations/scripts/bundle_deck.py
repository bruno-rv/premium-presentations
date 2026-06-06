#!/usr/bin/env python3
"""
Bundle a Premium Presentations deck into one standalone HTML file.

Inlines local <link rel="stylesheet"> and <script src> assets from shared/.
Replaces Mermaid module imports with inlined premium-mermaid.js.

Usage:
  ./scripts/bundle_deck.py decks/my-talk/my-talk-slides.html
  ./scripts/bundle_deck.py decks/my-talk/my-talk-slides.html -o out.html --in-place
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "shared"

JS_ORDER = (
    "premium-controller.js",
    "premium-controls.js",
    "premium-annotations.js",
    "premium-red-chrome.js",
    "premium-journey.js",
    "premium-timer.js",
    "premium-tts.js",
    "premium-search.js",
    "premium-clicker.js",
    "premium-og-cover.js",
    "premium-presenter.js",
    "slide-engine.js",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_remote_url(href: str) -> bool:
    return bool(re.match(r"^https?://", href, re.I)) or href.startswith("//")


def resolve_asset(html_path: Path, href: str) -> Path | None:
    if is_remote_url(href):
        return None
    return (html_path.parent / href).resolve()


def strip_exports(js: str) -> str:
    js = re.sub(r"^export\s+(async\s+)?function\s+", r"\1function ", js, flags=re.M)
    js = re.sub(r"^export\s+", "", js, flags=re.M)
    return js


def escape_for_html_script(content: str) -> str:
    """Prevent `</script>` in JS/CSS comments from terminating the HTML script element."""
    return re.sub(r"</script>", r"<\\/script>", content, flags=re.I)


def strip_usage_docblock(content: str) -> str:
    """Remove leading /** ... */ blocks (often contain </script> in examples)."""
    return re.sub(r"^/\*\*[\s\S]*?\*/\s*\n", "", content, count=1)


def inline_stylesheets(html: str, html_path: Path) -> str:
    pattern = (
        r'<link\s+[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\']([^"\']+)["\']'
        r'[^>]*/?\s*>'
    )

    def repl(match: re.Match[str]) -> str:
        href = match.group(1)
        css_path = resolve_asset(html_path, href)
        if css_path is None:
            return match.group(0)
        if not css_path.is_file():
            raise FileNotFoundError(f"Stylesheet not found: {css_path}")
        css = escape_for_html_script(read_text(css_path))
        return f"<style>\n/* --- {css_path.name} --- */\n{css}\n</style>"

    return re.sub(pattern, repl, html, flags=re.I)


def collect_script_srcs(html: str, html_path: Path) -> list[tuple[str, Path]]:
    pattern = r'<script\s+[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</script>'
    found: list[tuple[str, Path]] = []
    for href in re.findall(pattern, html, flags=re.I):
        js_path = resolve_asset(html_path, href)
        if js_path is None:
            continue
        if not js_path.is_file():
            raise FileNotFoundError(f"Script not found: {js_path}")
        found.append((href, js_path))

    def sort_key(item: tuple[str, Path]) -> tuple[int, int]:
        name = item[1].name
        if name in JS_ORDER:
            return (0, JS_ORDER.index(name))
        return (1, 0)

    found.sort(key=sort_key)
    return found


def remove_local_script_tags(html: str) -> str:
    pattern = r'<script\s+[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</script>\s*'
    return re.sub(
        pattern,
        lambda m: "" if not is_remote_url(m.group(1)) else m.group(0),
        html,
        flags=re.I,
    )


def has_mermaid_markup(html: str) -> bool:
    return bool(re.search(r'class=["\'][^"\']*\bmermaid\b', html, re.I))


def wants_premium_mermaid(html: str) -> bool:
    return "premium-mermaid.js" in html or (
        has_mermaid_markup(html) and "initPremiumMermaid" in html
    )


def wants_premium_journey(html: str) -> bool:
    return "premium-journey.js" in html or "journey-stage" in html


def build_mermaid_module() -> str:
    mermaid_path = SHARED / "premium-mermaid.js"
    if not mermaid_path.is_file():
        raise FileNotFoundError(f"Missing {mermaid_path}")
    body = escape_for_html_script(
        strip_exports(strip_usage_docblock(read_text(mermaid_path)))
    )
    bootstrap = """
document.addEventListener('DOMContentLoaded', function () {
  if (typeof initPremiumJourney === 'function') {
    try { initPremiumJourney(); } catch (e) { console.error('[PremiumJourney] init failed', e); }
  }
  initPremiumMermaid()
    .then(function () { try { new SlideEngine(); } catch (e) { console.error('[SlideEngine] init failed', e); } })
    .catch(function (err) {
      console.error('[Premium Presentations] Mermaid init failed', err);
      try { new SlideEngine(); } catch (e) { console.error('[SlideEngine] init failed', e); }
    });
});
""".strip()
    return (
        f"<script>\n/* --- premium-mermaid (inlined) --- */\n{body}\n</script>\n"
        f"<script>\n{bootstrap}\n</script>"
    )


def replace_mermaid_module(html: str) -> str:
    pattern = r'<script\s+type=["\']module["\'][^>]*>[\s\S]*?</script>\s*'
    module = build_mermaid_module()

    if re.search(pattern, html, flags=re.I):
        return re.sub(pattern, module + "\n", html, count=1, flags=re.I)

    if has_mermaid_markup(html):
        return re.sub(r"</body>", module + "\n</body>", html, count=1, flags=re.I)

    return html


def remove_mermaid_module(html: str) -> str:
    pattern = r'<script\s+type=["\']module["\'][^>]*>[\s\S]*?</script>\s*'
    return re.sub(pattern, "", html, count=1, flags=re.I)


def build_classic_scripts(script_paths: list[Path]) -> str:
    chunks = []
    seen: set[Path] = set()
    for path in script_paths:
        if path in seen:
            continue
        seen.add(path)
        js = escape_for_html_script(strip_exports(strip_usage_docblock(read_text(path))))
        chunks.append(f"<script>\n/* --- {path.name} --- */\n{js}\n</script>")
    return "\n".join(chunks)


def strip_slideengine_bootstraps(html: str) -> str:
    html = re.sub(
        r"<script>\s*document\.addEventListener\(\s*['\"]DOMContentLoaded['\"]\s*,\s*"
        r"(?:async\s*)?\([^)]*\)\s*=>\s*\{[\s\S]*?new SlideEngine\(\)[\s\S]*?\}\s*\)\s*;\s*"
        r"</script>\s*",
        "",
        html,
        flags=re.I,
    )
    html = re.sub(
        r"<script>\s*document\.addEventListener\(\s*['\"]DOMContentLoaded['\"]\s*,\s*"
        r"function\s*\(\)\s*\{[\s\S]*?new SlideEngine\(\)[\s\S]*?\}\s*\)\s*;\s*"
        r"</script>\s*",
        "",
        html,
        flags=re.I,
    )
    return html


def strip_inlined_mermaid(html: str) -> str:
    """Remove Mermaid runtime blocks appended by previous bundle runs."""
    return re.sub(
        r"<script>\s*/\*\s*---\s*premium-mermaid\s+\(inlined\)\s*---\s*\*/[\s\S]*?</script>\s*",
        "",
        html,
        flags=re.I,
    )


def unstandalone_html(html: str) -> str:
    """Strip previously-inlined shared/ content and the standalone marker
    so bundle_html() re-reads shared/ source from disk.
    """
    # Remove the standalone marker comment so the new bundle re-adds it.
    html = re.sub(
        r"<!--\s*Premium Presentations\s*—\s*standalone bundle\.[^>]*-->\s*",
        "",
        html,
    )
    # Replace previously-inlined <style>/* --- foo.css --- */...</style> blocks
    # with the original <link rel="stylesheet" href="../../shared/foo.css"> tag.
    def _restore_style(match: re.Match) -> str:
        name = match.group(1)
        return (
            f'<link rel="stylesheet" href="../../shared/{name}">'
        )
    html = re.sub(
        r"<style>\s*/\*\s*---\s*([\w\-./]+\.css)(?:\s+\w+)?\s*---\s*\*/[\s\S]*?</style>",
        _restore_style,
        html,
    )
    # Replace previously-inlined <script>/* --- foo.js --- */...</script>
    # with the original <script src="../../shared/foo.js"></script> tag.
    def _restore_script(match: re.Match) -> str:
        name = match.group(1)
        return f'<script src="../../shared/{name}"></script>'
    html = re.sub(
        r"<script>\s*/\*\s*---\s*([\w\-./]+\.js)\s*---\s*\*/[\s\S]*?</script>",
        _restore_script,
        html,
    )
    html = strip_inlined_mermaid(html)
    return html


def bundle_html(html: str, html_path: Path) -> str:
    if "/* --- premium-themes.css --- */" in html and "../../shared/" not in html:
        return html  # already bundled

    use_mermaid = wants_premium_mermaid(html)

    html = inline_stylesheets(html, html_path)
    scripts = collect_script_srcs(html, html_path)
    html = remove_local_script_tags(html)
    html = remove_mermaid_module(html)

    script_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for _, p in scripts:
        if p not in seen_paths:
            seen_paths.add(p)
            script_paths.append(p)
    if wants_premium_journey(html):
        journey_path = SHARED / "premium-journey.js"
        if journey_path.is_file() and journey_path not in seen_paths:
            script_paths.append(journey_path)
    inline_js = build_classic_scripts(script_paths) if script_paths else ""

    footer_parts: list[str] = []
    if inline_js:
        footer_parts.append(inline_js)

    if use_mermaid:
        html = strip_slideengine_bootstraps(html)
        footer_parts.append(build_mermaid_module())
    elif "new SlideEngine" not in html:
        # SlideEngine MUST boot even if journey init throws (defensive try/catch
        # prevents one bad init from killing all later DOMContentLoaded listeners,
        # which would leave the deck un-navigable).
        boot = "document.addEventListener('DOMContentLoaded', function () {\n"
        if wants_premium_journey(html):
            boot += "  if (typeof initPremiumJourney === 'function') {\n"
            boot += "    try { initPremiumJourney(); } catch (e) { console.error('[PremiumJourney] init failed', e); }\n"
            boot += "  }\n"
        boot += "  try { new SlideEngine(); } catch (e) { console.error('[SlideEngine] init failed', e); }\n"
        boot += "});\n"
        footer_parts.append("<script>\n" + boot + "</script>")

    if footer_parts:
        footer = "\n".join(footer_parts)
        idx = html.lower().rfind("</body>")
        if idx == -1:
            html = html + "\n" + footer
        else:
            html = html[:idx] + footer + "\n" + html[idx:]

    marker = (
        "<!-- Premium Presentations — standalone bundle. "
        "Engine: shared/ via ./scripts/bundle-deck.py -->\n"
    )
    if "standalone bundle" not in html:
        html = re.sub(r"(<!DOCTYPE html>\s*)", r"\1" + marker, html, count=1, flags=re.I)

    return html


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle deck HTML into one file")
    parser.add_argument("html", type=Path, help="Source deck HTML (may link to ../../shared/)")
    parser.add_argument("-o", "--output", type=Path, help="Output path (default: stdout)")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file with the bundled result",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-bundle even if the HTML looks already standalone",
    )
    args = parser.parse_args()

    html_path = args.html.resolve()
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1

    out_path = html_path if args.in_place else args.output
    if not args.in_place and out_path is None:
        out_path = html_path.with_name(html_path.stem + ".standalone.html")

    original = read_text(html_path)
    if args.force:
        # Strip any previous inlined content + standalone marker so the bundler
        # re-inlines from shared/ source. Re-link to ../../shared/ first.
        linked = unstandalone_html(original)
        bundled = bundle_html(linked, html_path)
    else:
        bundled = bundle_html(original, html_path)

    if bundled == original and not args.force:
        print(f"Already standalone (no ../../shared/ links): {html_path}")
        return 0

    if args.in_place or out_path:
        out_path.write_text(bundled, encoding="utf-8")
        print(f"Bundled → {out_path}")
    else:
        sys.stdout.write(bundled)
        return 0

    if re.search(r"<pre\s+class=[\"']mermaid[\"']", bundled, re.I):
        env = {**os.environ, "VALIDATE_HTML": str(out_path), "VALIDATE_SPEC": ""}
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_deck.py")],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            print("Bundle wrote file but diagram validation failed.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
