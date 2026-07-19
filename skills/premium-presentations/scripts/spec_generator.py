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

# Authored-sounding speaker notes tied to each content pattern. Rotated in
# sync with CONTENT_PATTERNS so every generated slide ships with a concrete
# delivery cue instead of a generic placeholder.
PATTERN_SPEAKER_NOTES = (
    "Walk through each stage card left to right — pause on the one most novel to this audience. "
    "Remind them that depth comes in the next act; this slide establishes the vocabulary. "
    "Ask if anyone has seen a different breakdown before moving on.",
    "Call out the dividing line first — that contrast is the whole point of this slide. "
    "Give one concrete example from each column before reading the labels. "
    "Transition: 'The shift from left to right is what the rest of this deck unpacks.'",
    "Narrate the data flow phase by phase as the animation cycles — don't rush ahead of it. "
    "Highlight the handoff arrows; those are where real-world failures hide. "
    "If the room is live, invite a question about any node before advancing.",
    "Read the headline stat first, then let the numbers sit for two seconds. "
    "Explain the 'why panel' takeaway in your own words — don't just repeat what's on screen. "
    "Transition: 'These numbers set the baseline; the next slides show what moves them.'",
    "Anchor the audience to today on the timeline before showing where the industry is heading. "
    "Emphasise that the eras overlap — change is gradual, not a hard cut. "
    "If time is short, skip the middle era and jump from origin to present.",
    "Read each pipeline stage as a question the system must answer, not just a label. "
    "Point out where latency accumulates — usually the middle stages. "
    "Transition: 'Every stage you see here maps to a decision your team will make.'",
    "Let the diagram render fully before speaking — give the audience five seconds to orient. "
    "Trace the critical path aloud; ignore secondary branches on a first pass. "
    "Offer to share the source file after the session for anyone who wants to dig deeper.",
    "Zoom into the highlighted line or block first — that's the crux, not the boilerplate. "
    "Explain what would break if you removed that section; that's the insight. "
    "Transition: 'You'll write something very close to this in the hands-on portion.'",
    "Contextualise the proportions before citing the absolute numbers. "
    "Call out the tallest bar and the shortest — the gap is the story. "
    "Transition: 'These ratios shift dramatically once you apply the pattern we'll cover next.'",
    "Run the checklist as a quick poll — ask the room how many items they already have in place. "
    "Mark the items that typically block teams longest; those are where coaching time goes. "
    "Close: 'Everything checked here means you're ready to move to the next module.'",
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
            "Welcome the audience and state the lesson goal in one sentence. "
            "Give a brief orientation: what they'll be able to do by the end. "
            "Keep this under 30 seconds — energy matters more than detail here."
        )
    elif i == 2:
        title, typ, pattern = "Hook", "Hook Quote", "slide--quote"
        beat = '"Let this quote sit for a moment before we unpack it."'
        notes = (
            "Read the quote slowly — let it land before you comment on it. "
            "Share one sentence on why this quote frames the entire lesson. "
            "Transition: 'That tension is exactly what we're here to resolve today.'"
        )
    elif i == count:
        title, typ, pattern = "Closing", "Closing Quote", "slide--quote"
        beat = '"One takeaway above everything else — here it is."'
        notes = (
            "Read the closing quote aloud, then pause for three seconds. "
            "Restate the single most important takeaway from the session in your own words. "
            "Point to next steps or resources before opening for questions."
        )
    elif i in (4, 8, 12) and count >= 12:
        title, typ, pattern = f"Act break {i}", "Divider", "DIV+ divider-act"
        beat = '"Quick breath — next act opens with a new question."'
        notes = (
            f"Signal the transition explicitly: 'We've covered Act {i // 4}, now into Act {i // 4 + 1}.' "
            "Take a breath here — let the audience absorb what came before. "
            "One sentence previewing the next act's core question is enough."
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
