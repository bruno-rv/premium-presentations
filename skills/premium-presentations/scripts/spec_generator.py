#!/usr/bin/env python3
"""Fill the slide-spec template for a scaffolded deck.

Usage: spec_generator.py <spec-file> <slug> <title> <slide_count>

Called by new-deck.sh after copying references/slide-spec-template.md into the
deck directory. Replaces template placeholders and regenerates the slide map
table for the requested slide count.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

TABLE_HEADER = (
    "| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes | Budget (mm:ss) | Budget (ms) |\n"
    "|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|----------------|-------------|"
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

# Explanation-shaped speaker-note scaffolds tied to each content pattern.
# Rotated in sync with CONTENT_PATTERNS so every generated slide ships with
# concrete explanatory blanks to fill during authoring — never delivery cues
# or staging directions (Speaker Notes rule in references/slide-spec-template.md).
PATTERN_SPEAKER_NOTES = (
    "Core claim: [the one concept this deep dive establishes]. The copy column explains what it is and why it exists; the visual traces how its parts connect: [the linkage]. Any technical term on this slide gets an everyday-words definition here.",
    "Left side: [what that option is and its concrete limit]. Right side: [what the other option is and what it changes]. The comparison resolves as: [which fits which situation, and why].",
    "The pipeline works because each node contributes one step: [node 1] produces [output], which becomes the input to [node 2]. The arrows carry [what flows between stages]; the order is fixed because [the dependency].",
    "[Metric 1] measures [what exactly]; [metric 2] captures [aspect]; [metric 3] shows [aspect]. Together they support the takeaway: [the why-panel line restated in plain words].",
    "The first era worked because [condition]; the next emerged once [force changed]; the current state reflects [driver]. What carried across all eras: [the persistent idea].",
    "Each stage is a transformation: [stage 1] turns [input] into [output], [stage 2] refines it by [action], and the last stage delivers [result]. The order cannot change because [dependency].",
    "Every box is [a component or state]; every arrow is [a handoff or transition]. Read end to end: [one sentence covering the whole path]. The secondary branches exist because [reason].",
    "This code exists to [job]. The highlighted part carries the key behavior: it works by [mechanism], and removing it would break [consequence]. The surrounding boilerplate is [purpose in plain words].",
    "The bars compare [measure and unit]. The tallest, [label], reaches [value]; the shortest, [label], sits at [value]. The gap comes from [cause], which is the point of the chart.",
    "Each item is a testable condition: [item 1] passes when [evidence]; [item 2] when [evidence]. An unchecked item costs [consequence], so teams clear it before [next step].",
)


def escape_markdown_table_cell(value: str) -> str:
    """Escape user text for one Markdown table cell without adding new rows."""
    escaped = html.escape(str(value), quote=True)
    escaped = escaped.replace("\\", "\\\\").replace("|", "\\|")
    return escaped.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")


def is_content_slide(i: int, count: int) -> bool:
    if i in (1, 2, count):
        return False
    return not (i in (4, 8, 12) and count >= 12)


def slide_act(i: int, count: int) -> int:
    if i in (1, 2):
        return 0
    if count < 12:
        return 1
    # Dividers at 4/8/12 open the next act; slides before the first divider are act 1.
    return 1 + sum(1 for d in (4, 8, 12) if i >= d)


def slide_row(i: int, count: int, content_ordinal: int = 0) -> str:
    beat = "TBD"
    if i == 1:
        title, typ, pattern = "Title", "Title", "slide--title"
        beat = '"Welcome — here is what you will be able to do by the end."'
        notes = (
            "States what this session covers in one sentence: [topic] for [audience]. "
            "Names what the audience can do afterwards: [outcome]."
        )
    elif i == 2:
        title, typ, pattern = "Hook", "Hook Quote", "slide--quote"
        beat = '"Let this quote sit for a moment before we unpack it."'
        notes = (
            "The quote overturns a common assumption: [assumption] replaced by [claim]. "
            "Explains why that tension motivates everything that follows: [one sentence]."
        )
    elif i == count:
        title, typ, pattern = "Closing", "Closing Quote", "slide--quote"
        beat = '"One takeaway above everything else — here it is."'
        notes = (
            "Restates the anchor idea in plain words: [takeaway]. "
            "Ties it back to the opening problem: [link]. "
            "Names the immediate next action: [step]."
        )
    elif i in (4, 8, 12) and count >= 12:
        title, typ, pattern = f"Act break {i}", "Divider", "DIV+ divider-act"
        beat = '"Quick breath — next act opens with a new question."'
        notes = (
            f"Separates [the previous act's concern] from [the next act's concern]. "
            "Explains why the next act follows from the last: [bridge sentence]."
        )
    else:
        idx = content_ordinal % len(CONTENT_PATTERNS)
        suggestion = CONTENT_PATTERNS[idx]
        title, typ = f"Slide {i}", "Content"
        pattern = f"{suggestion} {PATTERN_NOTE}"
        notes = PATTERN_SPEAKER_NOTES[idx]
    act = slide_act(i, count)
    # Trailing Budget (mm:ss)/Budget (ms) cells are scaffolded empty —
    # budgetless by default (three-state rule, see slide-spec-template.md).
    # No Python script emits data-budget; filling these in is an authoring step.
    return f"| {i} | slide-{i} | {act} | {typ} | {title} | TBD | {pattern} | TBD | {beat} | {notes} |  |  |"


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
    text = text.replace("{Full title}", escape_markdown_table_cell(title))
    text = text.replace("{N}", str(max(15, count // 2)))

    table = TABLE_HEADER + "\n" + "\n".join(slide_rows(count))
    return re.sub(
        r"\| # \| (?:ID \| )?Act \| Type \| Title \| Key Content \| Visual Pattern \| Why Panel[^\n]*\n"
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
