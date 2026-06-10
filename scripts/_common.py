"""Shared utilities for Premium Presentations scripts.

Single source of truth for theme discovery, shared-asset resolution, and the
runtime module lists consumed by the bundler and the runtime-contract
validator.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "assets" / "shared"
THEMES_CSS = SHARED / "premium-themes.css"

# Runtime contract: every generated deck/template carries these.
REQUIRED_CSS = (
    "premium-themes.css",
    "premium-deck.css",
    "premium-components.css",
    "premium-diagrams.css",
    "premium-annotations.css",
    "premium-extras.css",
)

REQUIRED_JS = (
    "premium-controller.js",
    "premium-controls.js",
    "premium-annotations.js",
    "premium-timer.js",
    "premium-tts.js",
    "premium-search.js",
    "premium-clicker.js",
    "premium-og-cover.js",
    "premium-presenter.js",
    "slide-engine.js",
)

# Conditional modules.
RED_CSS = ("premium-red-brand.css",)
RED_JS = ("premium-red-chrome.js",)
JOURNEY_JS = ("premium-journey.js",)

# Inlining order used by bundle_deck.py: conditional modules slot in after
# premium-annotations.js so they initialize before timer/presenter chrome.
JS_BUNDLE_ORDER = REQUIRED_JS[:3] + RED_JS + JOURNEY_JS + REQUIRED_JS[3:]

THEME_RE = re.compile(
    r"html\[data-theme=(?:\"([a-z0-9][a-z0-9-]*)\"|'([a-z0-9][a-z0-9-]*)'|([a-z0-9][a-z0-9-]*))\]"
)


def discover_themes(css_path: Path | None = None) -> list[str]:
    """Return themes declared as html[data-theme=...] selectors, in order."""
    css = (css_path or THEMES_CSS).read_text(encoding="utf-8")
    themes: list[str] = []
    for match in THEME_RE.finditer(css):
        theme = next(group for group in match.groups() if group)
        if theme not in themes:
            themes.append(theme)
    return themes


def find_repo_shared(start: Path, sentinel: str = "premium-themes.css") -> Path | None:
    """Walk up from *start* to locate the shared runtime directory.

    Checks both assets/shared/ (repo layout) and shared/ (copied layout),
    using *sentinel* to confirm the directory is the real runtime.
    """
    p = start.resolve().parent
    for _ in range(8):
        for candidate in (p / "assets" / "shared", p / "shared"):
            if (candidate / sentinel).is_file():
                return candidate
        if p.parent == p:
            break
        p = p.parent
    return None
