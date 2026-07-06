#!/usr/bin/env python3
"""WCAG contrast gate for Premium Presentations themes.

Reads the SOURCE `premium-themes.css` (via `_common.THEMES_CSS`), not a
deck's inlined blocks — a linked deck has zero inlined `data-theme` token
blocks, so scanning deck HTML would pass vacuously.

Two entry points:
  check_palette(tokens)   generation-time fail-fast, called by generate_theme.py
                          before it appends a new theme block.
  scan_themes_css(path)   repo-wide gate over every html[data-theme=...] block
                          in premium-themes.css; composed by deck_doctor.py.

Usage (standalone CLI — repo-wide gate for CI / manual runs):
  ./scripts/validate_contrast.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import THEME_SELECTOR_SRC, THEMES_CSS

# ADR-b gated pairs: (fg_token, bg_token, min_ratio).
GATED_PAIRS = (
    ("text", "bg", 4.5),
    ("text", "surface", 4.5),
    ("text-dim", "bg", 4.5),
    ("accent", "bg", 3.0),
)

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

# Anchors on the theme-token declaration itself: `]` then optional
# whitespace then `{`, no descendant selector in between. `[^}]*` for the
# body is safe because token blocks declare only `--custom-prop: value;`
# lines and contain no nested braces. This deliberately does NOT match
# `html[data-theme="x"] .component { ... }` follow-on rule blocks further
# down premium-themes.css (e.g. `.slide`, `.compare-panel--up`).
#
# Selector alternation is shared with _common.THEME_RE (quoted-double /
# quoted-single / unquoted attribute value) so an unquoted
# `html[data-theme=brand] { ... }` block is not invisible to this gate.
_THEME_BLOCK_RE = re.compile(THEME_SELECTOR_SRC + r"\s*\{([^}]*)\}", re.I)
_TOKEN_RE = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;]+);", re.I)


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_str: str) -> float:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg: str, bg: str) -> float:
    l1, l2 = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def check_palette(tokens: dict[str, str]) -> list[str]:
    """Return one message per failing pair (empty = pass).

    Fail-closed: a gated pair whose fg or bg token is missing or not a
    solid hex value is reported as an error, not silently skipped.
    """
    errors: list[str] = []
    for fg, bg, need in GATED_PAIRS:
        fv, bv = tokens.get(fg, ""), tokens.get(bg, "")
        if not (_HEX_RE.match(fv) and _HEX_RE.match(bv)):
            errors.append(f"--{fg}/--{bg}: missing or non-hex token (need >= {need}:1)")
            continue
        r = contrast_ratio(fv, bv)
        if r < need:
            errors.append(f"--{fg} on --{bg}: {r:.2f}:1 < {need}:1 (WCAG)")
    return errors


def _parse_theme_tokens(body: str) -> dict[str, str]:
    """Extract only solid-hex token values from a theme block body.

    Tokens whose value is rgba()/var()/color-mix() are skipped (cannot
    resolve compositing without a ground) — all built-in themes define
    the four gated tokens as solid hex, so coverage stays complete.
    """
    tokens: dict[str, str] = {}
    for name, value in _TOKEN_RE.findall(body):
        value = value.strip()
        if _HEX_RE.match(value):
            tokens[name] = value
    return tokens


def parse_theme_blocks(css: str) -> list[tuple[str, int, int, str]]:
    """Parse every html[data-theme=...] token block from *css* text.

    Returns (name, start, end, body) tuples in file order. A name MAY
    repeat (duplicate blocks) — this parser reports the raw structure only;
    callers decide how to treat duplicates. Shared by scan_themes_css()
    (fail-closed on duplicates) and generate_theme.py (existence check
    before append/replace).
    """
    return [
        (m.group(1) or m.group(2) or m.group(3), m.start(), m.end(), m.group(4))
        for m in _THEME_BLOCK_RE.finditer(css)
    ]


def scan_themes_css(css_path: Path | None = None) -> list[str]:
    """Repo-wide gate: check every html[data-theme=...] token block.

    Every block is validated — not just the first seen with a given name —
    because CSS cascade applies the LAST matching block; skipping later
    duplicates would let a failing block become the active theme while this
    gate reported success. A duplicate theme name is itself a fail-closed
    error: premium-themes.css must declare each theme id in exactly one
    block.
    """
    path = css_path or THEMES_CSS
    return scan_themes_css_text(path.read_text(encoding="utf-8"))


def scan_themes_css_text(css: str) -> list[str]:
    """Same gate as scan_themes_css(), over in-memory CSS text.

    Lets a caller validate a candidate document (e.g. generate_theme.py's
    about-to-be-written CSS) before any bytes hit disk, without a
    write-then-check-then-maybe-revert dance.
    """
    errors: list[str] = []
    counts: dict[str, int] = {}
    for theme, _start, _end, body in parse_theme_blocks(css):
        counts[theme] = counts.get(theme, 0) + 1
        tokens = _parse_theme_tokens(body)
        for message in check_palette(tokens):
            errors.append(f'html[data-theme="{theme}"] {message}')
    for theme, count in counts.items():
        if count > 1:
            errors.append(
                f'html[data-theme="{theme}"]: declared {count} times '
                "(CSS cascade applies the last block; duplicate theme names "
                "are not allowed)"
            )
    return errors


def main() -> int:
    errors = scan_themes_css(THEMES_CSS)
    if errors:
        print("Contrast gate FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1
    print(f"Contrast gate OK: {THEMES_CSS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
