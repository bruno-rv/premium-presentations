#!/usr/bin/env python3
"""List Premium Presentations themes declared in assets/shared/premium-themes.css."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
THEME_RE = re.compile(
    r"html\[data-theme=(?:\"([a-z0-9][a-z0-9-]*)\"|'([a-z0-9][a-z0-9-]*)'|([a-z0-9][a-z0-9-]*))\]"
)


def discover_themes(css_path: Path) -> list[str]:
    css = css_path.read_text(encoding="utf-8")
    themes: list[str] = []
    for match in THEME_RE.finditer(css):
        theme = next(group for group in match.groups() if group)
        if theme not in themes:
            themes.append(theme)
    return themes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--css",
        type=Path,
        default=ASSETS / "shared" / "premium-themes.css",
        help="Path to premium-themes.css",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON instead of one theme per line")
    args = parser.parse_args()

    themes = discover_themes(args.css)
    if args.json:
        print(json.dumps({"themes": themes}, indent=2))
    else:
        print("\n".join(themes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
