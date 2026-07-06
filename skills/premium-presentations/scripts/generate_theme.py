#!/usr/bin/env python3
"""Hex palette -> full premium-themes.css theme block (Python port of
premium-design-power.js buildThemeCss, extended to the full token set the
built-in themes emit — see DESIGN ADR-c).

The composer's JS `buildThemeCss` only emits 11 tokens; the built-in themes
each define ~34 self-contained tokens with no `:root` fallback layer for the
visual ones (progress bar, code windows, semantic tags). An 11-token theme
would pass the runtime contract but render broken. This port emits the
complete set so a generated theme is a drop-in peer of the built-ins.

Contrast-checked at generation time (fail-closed): a palette that fails
validate_contrast.check_palette() is rejected, nothing is appended.

Usage:
  ./scripts/generate_theme.py <brand-id> --bg HEX --text HEX --accent HEX --surface HEX
                              [--font-display STACK] [--css PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import colorsys
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import THEME_RE, THEMES_CSS
from validate_contrast import (
    check_palette,
    parse_theme_blocks,
    relative_luminance,
    scan_themes_css_text,
)

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Whitelist for CSS font-family stacks: letters, digits, plain spaces,
# commas, hyphens, and quotes only. No `;` `{` `}` `\` `/` (blocks CSS-comment
# `/*...*/` sequences), no other whitespace (blocks newlines/tabs), no
# control characters — a value outside this set could terminate the
# `--font-display: ...;` declaration or the enclosing block and inject
# arbitrary CSS after the contrast gate has already passed.
# \A/\Z (not ^/$) — $ tolerates a single trailing newline at end-of-string,
# which would let a lone trailing "\n" slip through undetected.
_FONT_STACK_RE = re.compile(r"\A[A-Za-z0-9 ,'\"-]+\Z")

# Two fixed semantic palettes (brand-independent by design — error=red,
# ok=green, etc. — chosen to read on their respective ground), selected by
# is_dark. Mirrors the two families already in use across the built-ins.
_SEMANTIC_DARK = {
    "red": "#f85149", "red-dim": "rgba(248, 81, 73, 0.12)",
    "green": "#3fb950", "green-dim": "rgba(63, 185, 80, 0.12)",
    "orange": "#e8a25c", "orange-dim": "rgba(232, 162, 92, 0.12)",
    "cyan": "#5ec8e8", "cyan-dim": "rgba(94, 200, 232, 0.12)",
    "violet": "#a78bfa", "violet-dim": "rgba(167, 139, 250, 0.12)",
    "gold": "#d4af37", "gold-dim": "rgba(212, 175, 55, 0.12)",
    "blue": "#60a5fa",
}
_SEMANTIC_LIGHT = {
    "red": "#d70015", "red-dim": "rgba(215, 0, 21, 0.1)",
    "green": "#248a3d", "green-dim": "rgba(36, 138, 61, 0.1)",
    "orange": "#bf5b00", "orange-dim": "rgba(191, 91, 0, 0.1)",
    "cyan": "#007aff", "cyan-dim": "rgba(0, 122, 255, 0.1)",
    "violet": "#5856d6", "violet-dim": "rgba(88, 86, 214, 0.1)",
    "gold": "#a06d1f", "gold-dim": "rgba(160, 109, 31, 0.1)",
    "blue": "#0066cc",
}

_DEFAULT_FONT_DISPLAY = "system-ui, sans-serif"
_DEFAULT_FONT_BODY = "system-ui, sans-serif"
_DEFAULT_FONT_MONO = "ui-monospace, 'SF Mono', 'Cascadia Mono', 'Menlo', monospace"


def _rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.lstrip("#")
    h = "".join(c * 2 for c in h) if len(h) == 3 else h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(r: float, g: float, b: float) -> str:
    clamp = lambda v: max(0, min(255, round(v)))
    return "#%02x%02x%02x" % (clamp(r), clamp(g), clamp(b))


def _adjust_l(hex_str: str, delta: float) -> str:
    """Lighten (delta>0) / darken (delta<0) via HSL lightness, stdlib only."""
    r, g, b = (c / 255 for c in _rgb(hex_str))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r2, g2, b2 = colorsys.hls_to_rgb(h, min(1.0, max(0.0, l + delta)), s)
    return _hex(r2 * 255, g2 * 255, b2 * 255)


def _over(fg: str, bg: str, alpha: float) -> str:
    """Composite fg@alpha over bg -> solid hex (so the contrast gate can read it)."""
    fr, fg_, fb = _rgb(fg)
    br, bg_, bb = _rgb(bg)
    return _hex(
        fr * alpha + br * (1 - alpha),
        fg_ * alpha + bg_ * (1 - alpha),
        fb * alpha + bb * (1 - alpha),
    )


def _mix(a: str, b: str, t: float) -> str:
    """Linear RGB mix: a moved t of the way toward b."""
    ar, ag, ab = _rgb(a)
    br, bg_, bb = _rgb(b)
    return _hex(ar + (br - ar) * t, ag + (bg_ - ag) * t, ab + (bb - ab) * t)


def _rgba(hex_str: str, alpha: float) -> str:
    r, g, b = _rgb(hex_str)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _desaturated_accent2(accent: str, accent_strong: str) -> str:
    """Neutral gray from the accent hue at 45% saturation, or accent-strong
    when the accent is already desaturated enough (no desaturation needed)."""
    r, g, b = (c / 255 for c in _rgb(accent))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s <= 0.45:
        return accent_strong
    r2, g2, b2 = colorsys.hls_to_rgb(h, l, 0.45)
    return _hex(r2 * 255, g2 * 255, b2 * 255)


def sanitize_brand_id(raw: str) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.strip().lower()).strip("-")
    if not slug or not THEME_RE.match(f'html[data-theme="{slug}"]'):
        raise ValueError(f"Invalid brand-id after sanitizing: {raw!r} -> {slug!r}")
    return slug


def validate_hex(name: str, value: str) -> str:
    if not _HEX_RE.match(value):
        raise ValueError(f"--{name} must be a hex color (#rgb or #rrggbb), got {value!r}")
    return value


def validate_font_stack(name: str, value: str) -> str:
    """Reject CSS/declaration-breakout characters in a font-stack value.

    Whitelist-only (letters, digits, spaces, commas, hyphens, quotes),
    plus a balanced-quotes check — strict enough to still reject a value
    that stays inside the charset but leaves a quote open.
    """
    if not value or not _FONT_STACK_RE.match(value):
        raise ValueError(
            f"--{name} must contain only letters, digits, spaces, commas, "
            f"hyphens, and quotes, got {value!r}"
        )
    if value.count('"') % 2 or value.count("'") % 2:
        raise ValueError(f"--{name} has unbalanced quotes: {value!r}")
    return value


def build_theme_css(
    brand_id: str,
    bg: str,
    text: str,
    accent: str,
    surface: str,
    *,
    font_display: str = _DEFAULT_FONT_DISPLAY,
    font_body: str = _DEFAULT_FONT_BODY,
    font_mono: str = _DEFAULT_FONT_MONO,
) -> tuple[str, dict[str, str]]:
    """Return (css_block, tokens) for the full ADR-c derivation table."""
    is_dark = relative_luminance(bg) < 0.5

    surface2 = _mix(surface, text, 0.06)
    border = _rgba(text, 0.10)
    border_bright = _rgba(accent, 0.28)
    text_dim = _over(text, bg, 0.72)
    accent_strong = _adjust_l(accent, 0.15 if is_dark else -0.15)
    accent_dim = _rgba(accent, 0.12)
    accent2 = _desaturated_accent2(accent, accent_strong)
    code_bg = _adjust_l(bg, -0.35) if is_dark else _mix(surface, text, 0.04)
    code_text = _over(text, code_bg, 0.85)
    progress_gradient = "linear-gradient(90deg, var(--accent), var(--accent-strong))"
    grain_opacity = "0.035" if is_dark else "0.015"
    flow_glow_alpha = "35%" if is_dark else "18%"
    semantic = _SEMANTIC_DARK if is_dark else _SEMANTIC_LIGHT

    tokens: dict[str, str] = {
        "bg": bg,
        "text": text,
        "accent": accent,
        "surface": surface,
        "surface2": surface2,
        "border": border,
        "border-bright": border_bright,
        "text-dim": text_dim,
        "accent-strong": accent_strong,
        "accent-dim": accent_dim,
        "accent2": accent2,
        "code-bg": code_bg,
        "code-text": code_text,
        "progress-gradient": progress_gradient,
        "grain-opacity": grain_opacity,
        "flow-glow-alpha": flow_glow_alpha,
        "term-bg": code_bg,
        "term-bar": surface2,
        "term-text": code_text,
        "font-display": font_display,
        "font-body": font_body,
        "font-editorial": font_body,
        "font-mono": font_mono,
        **semantic,
    }

    order = [
        "font-display", "font-body", "font-editorial", "font-mono",
        "bg", "surface", "surface2", "border", "border-bright",
        "text", "text-dim",
        "accent", "accent-strong", "accent-dim", "accent2",
        "gold", "gold-dim", "orange", "orange-dim", "cyan", "cyan-dim",
        "green", "green-dim", "red", "red-dim", "blue", "violet", "violet-dim",
        "code-bg", "code-text", "progress-gradient",
        "grain-opacity", "flow-glow-alpha",
        "term-bg", "term-bar", "term-text",
    ]
    lines = [f'html[data-theme="{brand_id}"] {{']
    for key in order:
        lines.append(f"  --{key}: {tokens[key]};")
    lines.append("}")
    return "\n".join(lines), tokens


def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* via temp-file + os.replace (no partial writes)."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def _compose_append(css_block: str, existing: str) -> str:
    sep = "" if existing.endswith("\n") else "\n"
    return existing + sep + "\n" + css_block + "\n"


def _compose_replace(css_block: str, existing: str, start: int, end: int) -> str:
    new_css = existing[:start] + css_block + existing[end:]
    if not new_css.endswith("\n"):
        new_css += "\n"
    return new_css


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brand_id", help="Theme id, e.g. acme (sanitized to [a-z0-9][a-z0-9-]*)")
    parser.add_argument("--bg", required=True, help="Background hex color")
    parser.add_argument("--text", required=True, help="Body text hex color")
    parser.add_argument("--accent", required=True, help="Accent hex color")
    parser.add_argument("--surface", required=True, help="Surface (card/panel) hex color")
    parser.add_argument("--font-display", default=_DEFAULT_FONT_DISPLAY, help="Display font stack")
    parser.add_argument("--css", type=Path, default=THEMES_CSS, help="Target premium-themes.css path")
    parser.add_argument("--dry-run", action="store_true", help="Print the block, do not append")
    parser.add_argument(
        "--replace", action="store_true",
        help="Rewrite an existing theme block in place instead of failing on duplicate",
    )
    args = parser.parse_args(argv)

    try:
        brand_id = sanitize_brand_id(args.brand_id)
        bg = validate_hex("bg", args.bg)
        text = validate_hex("text", args.text)
        accent = validate_hex("accent", args.accent)
        surface = validate_hex("surface", args.surface)
        font_display = validate_font_stack("font-display", args.font_display)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    css_block, tokens = build_theme_css(
        brand_id, bg, text, accent, surface, font_display=font_display
    )

    errors = check_palette(tokens)
    if errors:
        print(f"Contrast gate rejected theme {brand_id!r}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(css_block)
        return 0

    existing_css = args.css.read_text(encoding="utf-8")
    matches = [b for b in parse_theme_blocks(existing_css) if b[0] == brand_id]

    if matches and not args.replace:
        print(
            f"Error: theme {brand_id!r} already exists in {args.css} "
            f"({len(matches)} block(s)); pass --replace to overwrite.",
            file=sys.stderr,
        )
        return 1

    if len(matches) > 1:
        print(
            f"Error: theme {brand_id!r} has {len(matches)} duplicate blocks in "
            f"{args.css}; resolve the duplicates manually before using --replace.",
            file=sys.stderr,
        )
        return 1

    if matches:
        _, start, end, _ = matches[0]
        candidate = _compose_replace(css_block, existing_css, start, end)
    else:
        candidate = _compose_append(css_block, existing_css)

    # Defense in depth: check_palette() above validated the token dict
    # pre-serialization, which does not catch a font-stack value that
    # smuggles a declaration/block breakout into the emitted CSS text
    # (validate_font_stack() should already reject that, but this is the
    # backstop). Scan the full candidate document before any bytes hit
    # disk — on any error, abort and leave the file untouched.
    post_errors = scan_themes_css_text(candidate)
    if post_errors:
        print(
            f"Error: candidate {args.css} failed the post-build contrast/duplicate "
            "scan; nothing written:",
            file=sys.stderr,
        )
        for error in post_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    _atomic_write(args.css, candidate)

    print(brand_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
