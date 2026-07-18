#!/usr/bin/env python3
"""
Bundle a Premium Presentations deck into one standalone HTML file.

Inlines local <link rel="stylesheet"> and <script src> assets from assets/shared/.
Replaces Mermaid module imports with inlined premium-mermaid.js.

Usage:
  ./scripts/bundle_deck.py assets/decks/my-talk/my-talk-slides.html
  ./scripts/bundle_deck.py assets/decks/my-talk/my-talk-slides.html -o out.html --in-place
  ./scripts/bundle_deck.py /workspace/deck.html --shared-root /path/to/assets/shared
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import JS_BUNDLE_ORDER as JS_ORDER
from _common import REQUIRED_CSS
from _common import REQUIRED_JS
from _common import ROOT, SHARED

_HTML_TAG_RE = re.compile(r"<html\b[^>]*>", re.I)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def is_remote_url(href: str) -> bool:
    return bool(re.match(r"^https?://", href, re.I)) or href.startswith("//")


def _normalize_shared_root(shared_root: Path | None) -> Path:
    """Resolve an explicit framework/shared directory to its shared assets."""
    if shared_root is None:
        return SHARED
    shared_root = shared_root.resolve()
    if (shared_root / "premium-themes.css").is_file():
        return shared_root
    for candidate in (shared_root / "assets" / "shared", shared_root / "shared"):
        if candidate.is_dir():
            return candidate
    return shared_root


def resolve_asset(
    html_path: Path,
    href: str,
    *,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> Path | None:
    if is_remote_url(href):
        return None
    if themes_css is not None and Path(href).name == "premium-themes.css":
        return themes_css.resolve()

    candidate = (html_path.parent / href).resolve()
    if candidate.is_file():
        return candidate

    # A deck copied outside the skill tree still carries ../../shared/ links.
    # Resolve that well-known framework path from the explicit read-only root.
    parts = Path(href).parts
    if "shared" in parts:
        shared = _normalize_shared_root(shared_root)
        shared_idx = parts.index("shared")
        relative = Path(*parts[shared_idx + 1:])
        return (shared / relative).resolve()
    return candidate


def strip_exports(js: str) -> str:
    js = re.sub(r"^export\s+(async\s+)?function\s+", r"\1function ", js, flags=re.M)
    js = re.sub(r"^export\s+", "", js, flags=re.M)
    return js


def escape_for_html_script(content: str) -> str:
    """Prevent `</script>` in JS/CSS comments from terminating the HTML script element."""
    return re.sub(r"</script>", r"<\\/script>", content, flags=re.I)


def escape_for_html_style(content: str) -> str:
    """Prevent `</style>` in a stylesheet from breaking out of the HTML style element."""
    return re.sub(r"</style", r"<\\/style", content, flags=re.I)


def strip_usage_docblock(content: str) -> str:
    """Remove leading /** ... */ blocks (often contain </script> in examples)."""
    return re.sub(r"^/\*\*[\s\S]*?\*/\s*\n", "", content, count=1)


def inline_stylesheets(
    html: str,
    html_path: Path,
    *,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> str:
    pattern = (
        r'<link\s+[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\']([^"\']+)["\']'
        r'[^>]*/?\s*>'
    )

    def repl(match: re.Match[str]) -> str:
        href = match.group(1)
        css_path = resolve_asset(
            html_path, href, shared_root=shared_root, themes_css=themes_css
        )
        if css_path is None:
            return match.group(0)
        if not css_path.is_file():
            raise FileNotFoundError(f"Stylesheet not found: {css_path}")
        css = escape_for_html_style(read_text(css_path))
        # Keep the runtime module name stable when --themes-css points at a
        # workspace-owned registry, so required-module detection does not
        # append the read-only framework registry a second time.
        module_name = Path(href).name
        return f"<style>\n/* --- {module_name} --- */\n{css}\n</style>"

    return re.sub(pattern, repl, html, flags=re.I)


def has_stylesheet_module(html: str, name: str) -> bool:
    marker = r"/\*\s*---\s*" + re.escape(name) + r"(?:\s+\w+)?\s*---\s*\*/"
    if re.search(marker, html, re.I):
        return True
    link = r"<link\b(?=[^>]*\brel=[\"']stylesheet[\"'])(?=[^>]*\bhref=[\"'][^\"']*" + re.escape(name) + r")[^>]*>"
    return bool(re.search(link, html, re.I))


def has_script_module(html: str, name: str) -> bool:
    marker = r"<script>\s*/\*\s*---\s*" + re.escape(name) + r"\s*---\s*\*/"
    if re.search(marker, html, re.I):
        return True
    src = r"<script\b[^>]*\bsrc=[\"'][^\"']*" + re.escape(name) + r"[\"'][^>]*>"
    return bool(re.search(src, html, re.I))


def missing_required_modules(html: str) -> list[str]:
    missing = [name for name in REQUIRED_CSS if not has_stylesheet_module(html, name)]
    missing += [name for name in REQUIRED_JS if not has_script_module(html, name)]
    return missing


def build_missing_required_styles(
    html: str,
    *,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> str:
    chunks = []
    shared = _normalize_shared_root(shared_root)
    for name in REQUIRED_CSS:
        if has_stylesheet_module(html, name):
            continue
        css_path = themes_css if name == "premium-themes.css" and themes_css else shared / name
        if not css_path.is_file():
            raise FileNotFoundError(f"Required stylesheet not found: {css_path}")
        css = escape_for_html_style(read_text(css_path))
        chunks.append(f"<style>\n/* --- {name} --- */\n{css}\n</style>")
    return "\n".join(chunks)


def inject_required_styles(
    html: str,
    *,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> str:
    styles = build_missing_required_styles(
        html, shared_root=shared_root, themes_css=themes_css
    )
    if not styles:
        return html
    head_end = html.lower().find("</head>")
    if head_end == -1:
        return styles + "\n" + html
    return html[:head_end] + styles + "\n" + html[head_end:]


def collect_script_srcs(
    html: str,
    html_path: Path,
    *,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> list[tuple[str, Path]]:
    pattern = r'<script\s+[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</script>'
    found: list[tuple[str, Path]] = []
    for href in re.findall(pattern, html, flags=re.I):
        js_path = resolve_asset(
            html_path, href, shared_root=shared_root, themes_css=themes_css
        )
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
    # Match script src reference OR class attribute usage; avoids false-positives
    # from "journey-stage" appearing in inlined CSS text after inline_stylesheets().
    return "premium-journey.js" in html or bool(
        re.search(r'class=["\'][^"\']*\bjourney-stage\b', html)
    )


def wants_premium_flow(html: str) -> bool:
    # Same guard: match class attribute, not bare substring that could appear in CSS.
    return "premium-flow.js" in html or bool(
        re.search(r'class=["\'][^"\']*\blive-flow\b', html)
    )


def wants_premium_glossary(html: str) -> bool:
    # Match script src reference, data-term= attribute, or id="glossary" tag —
    # never a bare "term-link" substring that would match CSS class definitions
    # inside inlined <style> blocks.
    return (
        "premium-glossary.js" in html
        or bool(re.search(r'\bdata-term=["\']', html))
        or bool(re.search(r'\bid=["\']glossary["\']', html))
    )


def wants_follow(html: str) -> bool:
    # Attribute-gated (like the red-theme trigger), NOT a markup-class
    # trigger (unlike journey/flow/glossary) — followability is an
    # author/recipe opt-in set on <html> BEFORE bundling; a deck cannot
    # become followable by editing already-bundled HTML.
    root_match = _HTML_TAG_RE.search(html)
    root_tag = root_match.group(0) if root_match else ""
    return "data-follow" in root_tag


def build_mermaid_module(shared_root: Path | None = None) -> str:
    mermaid_path = _normalize_shared_root(shared_root) / "premium-mermaid.js"
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
  if (typeof initPremiumFlow === 'function') {
    try { initPremiumFlow(); } catch (e) { console.error('[PremiumFlow] init failed', e); }
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


# ---------------------------------------------------------------------------
# Theme-visuals embed helpers
# ---------------------------------------------------------------------------

# Tempered-greedy, quote-bounded regex: matches slide--title/slide--divider
# only when they appear inside a class="..." or class='...' attribute VALUE.
# Raw substring search is forbidden: inlined CSS selectors contain these
# strings and would cause false-positives.  data-x="slide--title" must NOT
# match because the capture group anchors on `class\s*=`.
_VISUAL_CLASS_RE = re.compile(
    r"""\bclass\s*=\s*(["'])(?:(?!\1)[\s\S])*\bslide--(?:title|divider)\b(?:(?!\1)[\s\S])*\1"""
)

# Matches the entire injected <script> block that contains the embed marker,
# so re-bundling strips the old block before inserting a fresh one.
_EMBED_BLOCK_RE = re.compile(
    r"<script>\s*/\*\s*---\s*theme-visuals-embed\s*---\s*\*/[\s\S]*?</script>\s*",
    re.I,
)

# Relative-path detector for override-hygiene warning: a value is "relative"
# when it does NOT start with https?:, data:, blob:, file:, or /.
_RELATIVE_PATH_RE = re.compile(r"^(?!https?:|data:|blob:|file:|/)")

def _manifest_path(shared_root: Path | None = None) -> Path:
    # Resolved at call time so tests can patch the module-level SHARED.
    return _normalize_shared_root(shared_root) / "assets" / "theme-visuals" / "manifest.json"


def has_visual_slides(html: str) -> bool:
    """Return True if the deck markup contains a slide--title or slide--divider
    class attribute value (not a bare substring — see _VISUAL_CLASS_RE)."""
    return bool(_VISUAL_CLASS_RE.search(html))


def load_theme_visuals_map(shared_root: Path | None = None) -> dict[str, dict[str, Path]]:
    """Return {theme: {role: Path}} built from manifest.json.

    Falls back to globbing <theme>-hero.webp / <theme>-map.webp only when
    the manifest file is missing.  Missing manifest-listed asset files are
    reported immediately so the caller can fail hard.
    """
    manifest_path = _manifest_path(shared_root)
    visuals_dir = manifest_path.parent

    if manifest_path.is_file():
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        result: dict[str, dict[str, Path]] = {}
        for theme, meta in raw.items():
            role_map: dict[str, Path] = {}
            for entry in meta.get("assets", []):
                role = entry["role"]
                src = entry["src"]
                asset_path = visuals_dir / src
                if not asset_path.is_file():
                    raise FileNotFoundError(
                        f"theme-visuals embed: manifest lists {src!r} "
                        f"(theme={theme!r}, role={role!r}) but the file "
                        f"does not exist: {asset_path}"
                    )
                role_map[role] = asset_path
            if role_map:
                result[theme] = role_map
        return result

    # Fallback: glob for <theme>-hero.webp / <theme>-map.webp.
    result = {}
    for webp in sorted(visuals_dir.glob("*-hero.webp")):
        theme = webp.stem[: -len("-hero")]
        map_path = visuals_dir / f"{theme}-map.webp"
        role_map = {"hero": webp}
        if map_path.is_file():
            role_map["map"] = map_path
        result[theme] = role_map
    return result


def strip_theme_visuals_embed(html: str) -> str:
    """Remove any previously-injected theme-visuals embed block for idempotence."""
    return _EMBED_BLOCK_RE.sub("", html)


def strip_standalone_runtime_marker(html: str) -> str:
    return re.sub(
        r"<script>\s*/\*\s*---\s*premium-standalone-runtime\s*---\s*\*/[\s\S]*?</script>\s*",
        "",
        html,
        flags=re.I,
    )


def strip_remote_resource_links(html: str) -> str:
    """Remove fetchable remote resources from deck HTML before bundling."""
    html = re.sub(
        r"<link\b(?=[^>]*\bhref=[\"'](?:https?:)?//)[^>]*>\s*",
        "",
        html,
        flags=re.I,
    )
    html = re.sub(
        r"<script\b(?=[^>]*\bsrc=[\"'](?:https?:)?//)[^>]*>\s*</script>\s*",
        "",
        html,
        flags=re.I,
    )
    return html


def strip_unsafe_portable_attrs(html: str) -> str:
    """Drop override attributes that would make a bundled deck fetch sidecars."""
    html = re.sub(
        r"\sdata-theme-visual-[\w-]+\s*=\s*([\"'])(?!(?:data:image/|blob:))[\s\S]*?\1",
        "",
        html,
        flags=re.I,
    )
    html = re.sub(
        r"\sdata-theme-fonts-[\w-]+\s*=\s*([\"'])(?!data:text/css[,;])[\s\S]*?\1",
        "",
        html,
        flags=re.I,
    )
    return html


def strip_default_cover_meta(html: str) -> str:
    """Remove the scaffold's old relative OG cover reference.

    The deck scaffold does not create og-cover.png automatically. Keeping this
    meta tag in a standalone HTML file advertises a missing sidecar asset when
    the deck is moved or shared as a single file.
    """
    return re.sub(
        r"<meta(?=[^>]*\bproperty=[\"']og:image[\"'])(?=[^>]*\bcontent=[\"']og-cover\.png[\"'])[^>]*>\s*",
        "",
        html,
        flags=re.I,
    )


def warn_relative_visual_overrides(html: str) -> None:
    """Warn (stderr, non-fatal) when deck carries data-theme-visual-* attributes
    with relative-path values — those overrides will break outside the repo."""
    for match in re.finditer(r'\bdata-theme-visual-\S+\s*=\s*["\']([^"\']+)["\']', html):
        value = match.group(1)
        if _RELATIVE_PATH_RE.match(value):
            print(
                f"[bundle_deck] WARNING: data-theme-visual-* override has a relative "
                f"path ({value!r}) — it will break when the deck is opened outside "
                "the repo. Use a data: URI or absolute path instead.",
                file=sys.stderr,
            )


def _build_theme_visuals_payload(shared_root: Path | None = None) -> str:
    """Encode all manifest theme visuals as data: URIs and return the <script> block.

    Raises FileNotFoundError if any manifest-listed asset file is absent.
    Called only when the deck has already been confirmed to have visual slides.
    """
    theme_map = load_theme_visuals_map(shared_root)

    payload: dict[str, dict[str, str]] = {}
    for theme, role_map in theme_map.items():
        payload[theme] = {}
        for role, asset_path in role_map.items():
            raw = asset_path.read_bytes()
            b64 = base64.b64encode(raw).decode("ascii")
            payload[theme][role] = f"data:image/webp;base64,{b64}"

    payload_json = json.dumps(payload)
    return (
        "<script>\n"
        "/* --- theme-visuals-embed --- */\n"
        f"window.PremiumThemeVisuals = Object.assign(window.PremiumThemeVisuals || {{}}, {payload_json});\n"
        "</script>"
    )


def build_standalone_runtime_marker() -> str:
    return (
        "<script>\n"
        "/* --- premium-standalone-runtime --- */\n"
        "window.PremiumBundle = Object.assign(window.PremiumBundle || {}, { standalone: true });\n"
        "document.documentElement.dataset.premiumStandalone = 'true';\n"
        "</script>"
    )


def build_theme_visuals_embed(
    html: str, shared_root: Path | None = None
) -> str:
    """Build the <script> embed block when the deck has visual slides.

    Returns an empty string when the deck has no slide--title or
    slide--divider class attribute values.  Raises FileNotFoundError if a
    manifest-listed asset file is absent.
    """
    if not has_visual_slides(html):
        return ""
    return _build_theme_visuals_payload(shared_root)


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
    html = strip_theme_visuals_embed(html)
    html = strip_inlined_mermaid(html)
    html = strip_standalone_runtime_marker(html)
    return html


def bundle_html(
    html: str,
    html_path: Path,
    *,
    embed_visuals: bool = True,
    shared_root: Path | None = None,
    themes_css: Path | None = None,
) -> str:
    html = strip_remote_resource_links(html)
    html = strip_unsafe_portable_attrs(html)
    html = strip_default_cover_meta(html)

    # Already-bundled detection: if the deck is standalone AND either has the
    # embed block (visuals already embedded) or embed is disabled, return as-is.
    # If it's standalone but missing the embed block and embed_visuals is True,
    # fall through so we can inject the embed block (same pattern as REQUIRED_JS
    # auto-inject on re-bundle).
    is_standalone = (
        "/* --- premium-themes.css --- */" in html
        and "/* --- slide-engine.js --- */" in html
    )
    has_embed = "/* --- theme-visuals-embed --- */" in html
    if is_standalone:
        needs_embed = embed_visuals and not has_embed
        missing = missing_required_modules(html)
        if not needs_embed and not missing:
            return html  # already fully bundled

        # Already-bundled deck that predates the embed step and/or a required
        # module added after initial generation: retrofit only what's missing,
        # without touching the rest of the already-inlined content (re-running
        # the full pipeline below would re-append modules that are already
        # inlined, since collect_script_srcs() finds no <script src> to mark
        # them "seen").
        if needs_embed:
            warn_relative_visual_overrides(html)
            embed_block = build_theme_visuals_embed(html, shared_root)
            if embed_block:
                controls_marker = "/* --- premium-controls.js --- */"
                idx = html.find(controls_marker)
                if idx != -1:
                    # Back up to the start of the <script> tag that contains the marker.
                    script_start = html.rfind("<script>", 0, idx)
                    if script_start == -1:
                        script_start = idx
                    html = html[:script_start] + embed_block + "\n" + html[script_start:]
                else:
                    # premium-controls.js block not found; inject before </body>.
                    idx_body = html.lower().rfind("</body>")
                    if idx_body == -1:
                        html = html + "\n" + embed_block
                    else:
                        html = html[:idx_body] + embed_block + "\n" + html[idx_body:]

        if missing:
            html = inject_required_styles(
                html, shared_root=shared_root, themes_css=themes_css
            )
            missing_js = [name for name in REQUIRED_JS if not has_script_module(html, name)]
            if missing_js:
                js_paths = []
                for name in missing_js:
                    p = _normalize_shared_root(shared_root) / name
                    if not p.is_file():
                        raise FileNotFoundError(f"Required script not found: {p}")
                    js_paths.append(p)
                inline_js = build_classic_scripts(js_paths)
                idx_body = html.lower().rfind("</body>")
                if idx_body == -1:
                    html = html + "\n" + inline_js
                else:
                    html = html[:idx_body] + inline_js + "\n" + html[idx_body:]

        return html

    # Capture conditional-module decisions from the ORIGINAL html BEFORE
    # inline_stylesheets() runs.  After inlining, CSS text (e.g. ".term-link",
    # ".live-flow", ".journey-stage", ".slide--title" selectors) would cause
    # false-positive matches and bundle modules into every deck.
    use_mermaid = wants_premium_mermaid(html)
    use_journey = wants_premium_journey(html)
    use_flow = wants_premium_flow(html)
    use_glossary = wants_premium_glossary(html)
    use_follow = wants_follow(html)
    # has_visual_slides uses a quote-bounded class-attribute regex (safe post-inline),
    # but capturing pre-inline keeps it consistent with the other detection flags.
    use_embed = embed_visuals and has_visual_slides(html)

    html = inline_stylesheets(
        html, html_path, shared_root=shared_root, themes_css=themes_css
    )
    html = inject_required_styles(
        html, shared_root=shared_root, themes_css=themes_css
    )
    scripts = collect_script_srcs(
        html, html_path, shared_root=shared_root, themes_css=themes_css
    )
    html = remove_local_script_tags(html)
    html = remove_mermaid_module(html)

    script_paths: list[Path] = []
    seen_paths: set[Path] = set()
    for _, p in scripts:
        if p not in seen_paths:
            seen_paths.add(p)
            script_paths.append(p)
    if use_journey:
        journey_path = _normalize_shared_root(shared_root) / "premium-journey.js"
        if journey_path.is_file() and journey_path not in seen_paths:
            seen_paths.add(journey_path)
            script_paths.append(journey_path)
    if use_flow:
        flow_path = _normalize_shared_root(shared_root) / "premium-flow.js"
        if flow_path.is_file() and flow_path not in seen_paths:
            seen_paths.add(flow_path)
            script_paths.append(flow_path)
    if use_glossary:
        glossary_path = _normalize_shared_root(shared_root) / "premium-glossary.js"
        if glossary_path.is_file() and glossary_path not in seen_paths:
            seen_paths.add(glossary_path)
            script_paths.append(glossary_path)
    if use_follow:
        follow_path = _normalize_shared_root(shared_root) / "premium-follow.js"
        if follow_path.is_file() and follow_path not in seen_paths:
            seen_paths.add(follow_path)
            script_paths.append(follow_path)
    # Inject any REQUIRED_JS modules absent from old bundles (added after initial generation).
    for name in REQUIRED_JS:
        req_path = _normalize_shared_root(shared_root) / name
        if req_path in seen_paths:
            continue
        if not req_path.is_file():
            raise FileNotFoundError(f"Required script not found: {req_path}")
        seen_paths.add(req_path)
        script_paths.append(req_path)
    inline_js = build_classic_scripts(script_paths) if script_paths else ""

    # Warn about relative-path data-theme-visual-* overrides (non-fatal).
    warn_relative_visual_overrides(html)

    # Build the theme-visuals embed block using the pre-inline detection flag.
    # load_theme_visuals_map() / base64 encoding only runs when needed.
    embed_block = _build_theme_visuals_payload(shared_root) if use_embed else ""

    footer_parts: list[str] = []
    footer_parts.append(build_standalone_runtime_marker())
    # Embed block goes BEFORE the inlined premium-controls.js block so the
    # window.PremiumThemeVisuals global is unconditionally available when
    # syncThemeVisuals() runs (which happens at DOMContentLoaded via SlideEngine).
    if embed_block:
        footer_parts.append(embed_block)
    if inline_js:
        footer_parts.append(inline_js)

    if use_mermaid:
        html = strip_slideengine_bootstraps(html)
        footer_parts.append(build_mermaid_module(shared_root))
    elif "new SlideEngine" not in html:
        # SlideEngine MUST boot even if journey init throws (defensive try/catch
        # prevents one bad init from killing all later DOMContentLoaded listeners,
        # which would leave the deck un-navigable).
        boot = "document.addEventListener('DOMContentLoaded', function () {\n"
        if use_journey:
            boot += "  if (typeof initPremiumJourney === 'function') {\n"
            boot += "    try { initPremiumJourney(); } catch (e) { console.error('[PremiumJourney] init failed', e); }\n"
            boot += "  }\n"
        if use_flow:
            boot += "  if (typeof initPremiumFlow === 'function') {\n"
            boot += "    try { initPremiumFlow(); } catch (e) { console.error('[PremiumFlow] init failed', e); }\n"
            boot += "  }\n"
        boot += "  try { new SlideEngine(); } catch (e) { console.error('[SlideEngine] init failed', e); }\n"
        # Glossary self-initializes (no explicit init call needed — IIFE runs at parse time).
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
        "Engine: assets/shared via ./scripts/bundle_deck.py -->\n"
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
    parser.add_argument(
        "--no-embed-visuals",
        action="store_true",
        help="Skip embedding theme visuals as base64 data URIs (visuals will 404 outside the repo)",
    )
    parser.add_argument(
        "--shared-root",
        type=Path,
        help="Read-only framework shared-assets directory (for decks outside the skill tree)",
    )
    parser.add_argument(
        "--themes-css",
        type=Path,
        help="Theme registry to inline instead of the framework premium-themes.css",
    )
    args = parser.parse_args()

    html_path = args.html.resolve()
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1

    out_path = html_path if args.in_place else args.output
    if not args.in_place and out_path is None:
        out_path = html_path.with_name(html_path.stem + ".standalone.html")

    embed_visuals = not args.no_embed_visuals
    shared_root = args.shared_root.resolve() if args.shared_root else None
    themes_css = args.themes_css.resolve() if args.themes_css else None

    original = read_text(html_path)
    if args.force:
        # Strip any previous inlined content + standalone marker so the bundler
        # re-inlines from shared/ source. Re-link to ../../shared/ first.
        linked = unstandalone_html(original)
        bundled = bundle_html(
            linked,
            html_path,
            embed_visuals=embed_visuals,
            shared_root=shared_root,
            themes_css=themes_css,
        )
    else:
        bundled = bundle_html(
            original,
            html_path,
            embed_visuals=embed_visuals,
            shared_root=shared_root,
            themes_css=themes_css,
        )

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
        import contextlib
        import io

        from validate_deck import validate as validate_deck

        out_buf, err_buf = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            returncode = validate_deck(out_path)
        if returncode != 0:
            print(out_buf.getvalue(), file=sys.stderr)
            print(err_buf.getvalue(), file=sys.stderr)
            print("Bundle wrote file but diagram validation failed.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
