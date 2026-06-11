#!/usr/bin/env python3
"""List Premium Presentations themes declared in assets/shared/premium-themes.css."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import ROOT, discover_themes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--css",
        type=Path,
        default=ROOT / "assets" / "shared" / "premium-themes.css",
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
