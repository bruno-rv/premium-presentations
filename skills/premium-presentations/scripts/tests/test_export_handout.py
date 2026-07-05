#!/usr/bin/env python3
"""Tests for export_handout.py — stdlib html.parser, no browser."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import export_handout  # noqa: E402

FIXTURE_HTML = """
<!doctype html><html lang="en"><body>
<div id="deck">
<section class="slide slide--title" data-nav-title="Opening">
  <h1>Opening</h1>
  <aside class="notes">First note block.</aside>
</section>
<section class="slide" data-nav-title="Double notes">
  <h2>Double notes</h2>
  <aside class="notes">Part one.</aside>
  <p>Some visible body content in between.</p>
  <aside class="notes">Part two.</aside>
</section>
<section class="slide slide--diagram" data-nav-title="Diagram slide">
  <pre class="mermaid">flowchart LR; A-->B</pre>
  <aside class="notes">Notes for the diagram slide.</aside>
</section>
<template>
  <section class="slide" data-nav-title="Should not count">
    <aside class="notes">Ignore me — inside a template.</aside>
  </section>
</template>
</div>
</body></html>
"""

MISSING_NOTES_HTML = """
<!doctype html><html lang="en"><body>
<div id="deck">
<section class="slide" data-nav-title="Has notes">
  <h1>Has notes</h1>
  <aside class="notes">Present.</aside>
</section>
<section class="slide" data-nav-title="No notes at all">
  <h1>No notes at all</h1>
</section>
<section class="slide" data-nav-title="Blank notes">
  <h1>Blank notes</h1>
  <aside class="notes">   </aside>
</section>
</div>
</body></html>
"""

ZERO_SLIDES_HTML = """
<!doctype html><html lang="en"><body>
<div id="deck">
<p>No slides here.</p>
</div>
</body></html>
"""

# Codex round-2 repro: a slide closes *before* an <aside class="notes"> that
# follows it as a sibling. The outside notes must NOT be attributed to the
# preceding slide — it must be reported as missing notes.
NOTES_OUTSIDE_SLIDE_HTML = (
    '<section class="slide" data-nav-title="No notes"></section>'
    '<aside class="notes">outside</aside>'
)

NOTES_OUTSIDE_SLIDE_DECK_HTML = """
<!doctype html><html lang="en"><body>
<div id="deck">
<section class="slide" data-nav-title="No notes"></section>
<aside class="notes">outside</aside>
</div>
</body></html>
"""


class HandoutParserTests(unittest.TestCase):
    def test_section_count_matches_slide_count(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        self.assertEqual(len(parser.slides), 3)

    def test_title_from_data_nav_title(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        titles = [s["title"] for s in parser.slides]
        self.assertEqual(titles, ["Opening", "Double notes", "Diagram slide"])

    def test_multiple_notes_blocks_concatenated_into_one_section(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        notes = "".join(parser.slides[1]["notes"])
        self.assertIn("Part one.", notes)
        self.assertIn("Part two.", notes)

    def test_template_contents_ignored(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        titles = [s["title"] for s in parser.slides]
        self.assertNotIn("Should not count", titles)
        all_notes = "".join(n for s in parser.slides for n in s["notes"])
        self.assertNotIn("Ignore me", all_notes)

    def test_every_notes_body_non_empty(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        for s in parser.slides:
            self.assertTrue("".join(s["notes"]).strip())

    def test_to_markdown_emits_one_section_per_slide(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(FIXTURE_HTML)
        parser.close()
        markdown = export_handout.to_markdown(parser.slides)
        self.assertEqual(markdown.count("## Slide "), 3)
        self.assertIn("## Slide 1 — Opening", markdown)
        self.assertIn("## Slide 2 — Double notes", markdown)
        self.assertIn("## Slide 3 — Diagram slide", markdown)


class ExportHandoutFailClosedTests(unittest.TestCase):
    def test_missing_or_empty_notes_exits_nonzero_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "deck.html"
            html_path.write_text(MISSING_NOTES_HTML, encoding="utf-8")
            out = Path(tmp) / "out.md"
            rc = export_handout.export_handout(html_path, out)
            self.assertNotEqual(rc, 0)
            self.assertFalse(out.exists())

    def test_zero_slides_exits_nonzero_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "deck.html"
            html_path.write_text(ZERO_SLIDES_HTML, encoding="utf-8")
            out = Path(tmp) / "out.md"
            rc = export_handout.export_handout(html_path, out)
            self.assertNotEqual(rc, 0)
            self.assertFalse(out.exists())

    def test_notes_outside_slide_exits_nonzero_and_writes_nothing(self) -> None:
        """Codex round-2 repro at the CLI level: a slide closes before its
        sibling <aside class="notes">. Must fail closed, not silently treat
        the slide as covered."""
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "deck.html"
            html_path.write_text(NOTES_OUTSIDE_SLIDE_DECK_HTML, encoding="utf-8")
            out = Path(tmp) / "out.md"
            rc = export_handout.export_handout(html_path, out)
            self.assertNotEqual(rc, 0)
            self.assertFalse(out.exists())

    def test_missing_notes_helper_reports_offending_slides(self) -> None:
        parser = export_handout.HandoutParser()
        parser.feed(MISSING_NOTES_HTML)
        parser.close()
        offenders = export_handout.missing_notes(parser.slides)
        self.assertEqual(
            offenders, [(2, "No notes at all"), (3, "Blank notes")]
        )

    def test_notes_outside_slide_not_attributed_to_previous_slide(self) -> None:
        """Codex round-2 repro: <section class="slide"></section> closes,
        then a sibling <aside class="notes"> follows. Regression: _cur was
        never cleared on </section>, so the outside notes were wrongly
        appended to the already-closed slide."""
        parser = export_handout.HandoutParser()
        parser.feed(NOTES_OUTSIDE_SLIDE_HTML)
        parser.close()
        self.assertEqual(len(parser.slides), 1)
        self.assertEqual("".join(parser.slides[0]["notes"]).strip(), "")
        offenders = export_handout.missing_notes(parser.slides)
        self.assertEqual(offenders, [(1, "No notes")])


class ExportHandoutRealDeckTests(unittest.TestCase):
    """Runs against the real, shipped, moved+extended rag-vector-graph deck —
    1.2 MB of inlined runtime JS containing literal "section class=\"slide\""
    strings in string constants. Confirms html.parser's CDATA handling of
    <script>/<style> keeps those out of the parsed slide count."""

    DECK = (
        ROOT
        / "assets"
        / "examples"
        / "rag-vector-graph"
        / "rag-vector-graph-slides.html"
    )

    def test_real_deck_section_count_matches_authored_slides(self) -> None:
        if not self.DECK.is_file():
            raise unittest.SkipTest(f"Example deck not found: {self.DECK}")
        text = self.DECK.read_text(encoding="utf-8", errors="replace")
        import re

        expected = len(re.findall(r'data-nav-title="', text))
        parser = export_handout.HandoutParser()
        parser.feed(text)
        parser.close()
        self.assertEqual(len(parser.slides), expected)
        for s in parser.slides:
            self.assertTrue(
                "".join(s["notes"]).strip(), f"Empty notes for slide: {s['title']!r}"
            )

    def test_export_handout_cli_writes_file(self) -> None:
        if not self.DECK.is_file():
            raise unittest.SkipTest(f"Example deck not found: {self.DECK}")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.md"
            rc = export_handout.export_handout(self.DECK, out)
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            content = out.read_text(encoding="utf-8")
            self.assertGreater(content.count("## Slide "), 0)


if __name__ == "__main__":
    unittest.main()
