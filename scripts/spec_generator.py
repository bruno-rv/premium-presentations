#!/usr/bin/env python3
"""Fill the slide-spec template for a scaffolded deck.

Usage: spec_generator.py <spec-file> <slug> <title> <slide_count>

Called by new-deck.sh after copying references/slide-spec-template.md into the
deck directory. Replaces template placeholders and regenerates the slide map
table for the requested slide count.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TABLE_HEADER = (
    "| # | Type | Title | Key Content | Visual Pattern | Why Panel |\n"
    "|---|------|-------|-------------|----------------|----------|"
)

# Concrete component IDs rotated through content slides so every slot ships
# with a committed visual pattern instead of a non-committal placeholder.
CONTENT_PATTERNS = (
    "STG stage-card",
    "P9 compare-paradigm",
    "FLOW+ live-flow",
    "STAT stats-row + WHY",
    "TL timeline",
    "PIPE pipeline-vertical",
    "slide--diagram (Mermaid)",
    "GL glass-code",
    "BAR bar-chart",
    "CHK checklist",
)
PATTERN_NOTE = "(suggested — swap to fit content, never bare)"


def is_content_slide(i: int, count: int) -> bool:
    if i in (1, 2, count):
        return False
    return not (i in (4, 8, 12) and count >= 12)


def slide_row(i: int, count: int, content_ordinal: int = 0) -> str:
    if i == 1:
        title, typ, pattern = "Title", "Title", "slide--title"
    elif i == 2:
        title, typ, pattern = "Hook", "Hook Quote", "slide--quote"
    elif i == count:
        title, typ, pattern = "Closing", "Closing Quote", "slide--quote"
    elif i in (4, 8, 12) and count >= 12:
        title, typ, pattern = f"Act break {i}", "Divider", "DIV+ divider-act"
    else:
        suggestion = CONTENT_PATTERNS[content_ordinal % len(CONTENT_PATTERNS)]
        title, typ = f"Slide {i}", "Content"
        pattern = f"{suggestion} {PATTERN_NOTE}"
    return f"| {i} | {typ} | {title} | TBD | {pattern} | TBD |"


def slide_rows(count: int) -> list[str]:
    rows: list[str] = []
    content_ordinal = 0
    for i in range(1, count + 1):
        rows.append(slide_row(i, count, content_ordinal))
        if is_content_slide(i, count):
            content_ordinal += 1
    return rows


def generate_spec(text: str, slug: str, title: str, count: int) -> str:
    text = text.replace("{CODE}", slug.upper().replace("-", " "))
    text = text.replace("{code}", slug)
    text = text.replace("{Full title}", title)
    text = text.replace("{N}", str(max(15, count // 2)))

    table = TABLE_HEADER + "\n" + "\n".join(slide_rows(count))
    return re.sub(
        r"\| # \| Type \| Title \| Key Content \| Visual Pattern \| Why Panel \|\n"
        r"\|---\|[^\n]*\n"
        r"(?:\|[^\n]*\n)*",
        table.replace("\\", "\\\\") + "\n",
        text,
        count=1,
    )


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__.strip().splitlines()[2], file=sys.stderr)
        return 1
    path, slug, title, count = sys.argv[1:5]
    spec_path = Path(path)
    text = spec_path.read_text(encoding="utf-8")
    spec_path.write_text(generate_spec(text, slug, title, int(count)), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
