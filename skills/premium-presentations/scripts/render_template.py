#!/usr/bin/env python3
"""Render literal ``{{NAME}}`` placeholders with HTML-escaped values."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

_PLACEHOLDER_RE = re.compile(r"\{\{([A-Z][A-Z0-9_]*)\}\}")


def render_template_text(template: str, values: dict[str, str]) -> str:
    missing: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            missing.add(key)
            return match.group(0)
        return html.escape(values[key], quote=True)

    rendered = _PLACEHOLDER_RE.sub(replace, template)
    if missing:
        raise ValueError(f"unresolved template placeholders: {', '.join(sorted(missing))}")
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--var", action="append", nargs=2, default=[], metavar=("NAME", "VALUE"))
    args = parser.parse_args(argv)
    try:
        values = {name: value for name, value in args.var}
        rendered = render_template_text(args.template.read_text(encoding="utf-8"), values)
        args.output.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
