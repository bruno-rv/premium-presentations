#!/usr/bin/env python3
"""Export a Markdown speaker-notes handout from a bundled deck.

Usage: ./scripts/export_handout.py <deck.html> [-o out.md]

One `## Slide N — <title>` section per <section class="slide..."> with its
concatenated <aside class="notes"> body. stdlib html.parser only — no
browser, offline.
"""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path


class HandoutParser(HTMLParser):
    """Collect, per <section class="slide...">, its title and aside.notes body.

    html.parser treats <script>/<style> as CDATA automatically; <template> is
    NOT — we defensively ignore anything inside a <template> subtree.

    A <section> depth counter tracks how deep we are inside the *current*
    slide's own section element (1 = directly inside it, 2+ = a nested
    <section>, if any). On the matching </section> that closes the slide
    (depth returns to 0), _cur is cleared so a later, sibling
    <aside class="notes"> outside the slide can never be misattributed to it.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.slides: list[dict] = []
        self._depth_template = 0
        self._slide_section_depth = 0
        self._in_notes = False
        self._cur: dict | None = None

    def _start(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "template":
            self._depth_template += 1
            return
        if self._depth_template:
            return
        cls = a.get("class", "") or ""
        if tag == "section":
            if self._cur is not None:
                # Already inside a slide section — this is a nested <section>.
                self._slide_section_depth += 1
            elif "slide" in cls.split():
                self._cur = {"title": a.get("data-nav-title", ""), "notes": []}
                self.slides.append(self._cur)
                self._slide_section_depth = 1
        elif tag == "aside" and "notes" in cls.split() and self._cur is not None:
            self._in_notes = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._start(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Void/self-closing tag (e.g. <section class="slide" ... />): no
        # matching handle_endtag will fire, so don't let it open scope.
        if tag in ("section", "aside"):
            return
        self._start(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "template" and self._depth_template:
            self._depth_template -= 1
        elif tag == "aside":
            self._in_notes = False
        elif tag == "section" and self._cur is not None:
            self._slide_section_depth -= 1
            if self._slide_section_depth <= 0:
                self._cur = None
                self._slide_section_depth = 0

    def handle_data(self, data: str) -> None:
        if self._in_notes and self._cur is not None:
            self._cur["notes"].append(data)


def to_markdown(slides: list[dict]) -> str:
    out = []
    for i, s in enumerate(slides, 1):
        title = (s["title"] or f"Slide {i}").strip()
        notes = "".join(s["notes"]).strip()
        out.append(f"## Slide {i} — {title}\n\n{notes}\n")
    return "\n".join(out)


def missing_notes(slides: list[dict]) -> list[tuple[int, str]]:
    """Slides (1-indexed) whose notes are absent or blank after stripping."""
    return [
        (i, (s["title"] or f"Slide {i}").strip())
        for i, s in enumerate(slides, 1)
        if not "".join(s["notes"]).strip()
    ]


def export_handout(html_path: Path, out_path: Path) -> int:
    text = html_path.read_text(encoding="utf-8", errors="replace")
    parser = HandoutParser()
    parser.feed(text)
    parser.close()

    if not parser.slides:
        print(f"No slides found in {html_path} — refusing to write handout", file=sys.stderr)
        return 1

    offenders = missing_notes(parser.slides)
    if offenders:
        for i, title in offenders:
            print(f"Slide {i} — {title}: missing or empty <aside class=\"notes\">", file=sys.stderr)
        print(f"{len(offenders)} slide(s) missing notes — refusing to write handout", file=sys.stderr)
        return 1

    markdown = to_markdown(parser.slides)
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Handout written: {out_path} ({len(parser.slides)} slide(s))")
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: export_handout.py <deck.html> [-o out.md]", file=sys.stderr)
        return 1
    html_path = Path(argv[0])
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 1
    out = (
        Path(argv[2])
        if len(argv) > 2 and argv[1] == "-o"
        else html_path.with_name(html_path.stem.replace("-slides", "") + "-handout.md")
    )
    return export_handout(html_path, out)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
