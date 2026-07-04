#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR_PATH = ROOT / "scripts" / "spec_generator.py"
TEMPLATE_PATH = ROOT / "references" / "slide-spec-template.md"


def load_generator():
    spec = importlib.util.spec_from_file_location("spec_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SpecGeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gen = load_generator()
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        cls.spec_14 = cls.gen.generate_spec(template, "demo-deck", "Demo Deck", 14)

    def map_rows(self, spec: str) -> dict[int, str]:
        rows: dict[int, str] = {}
        in_map = False
        for line in spec.splitlines():
            if line.startswith("| # | Act |"):
                in_map = True
                continue
            if not in_map:
                continue
            if not line.startswith("|"):
                break
            match = re.match(r"^\|\s*(\d+)\s*\|", line)
            if match:
                rows[int(match.group(1))] = line
        return rows

    def test_no_noncommittal_placeholder(self) -> None:
        self.assertNotIn("slide / diagram / table", self.spec_14)

    def test_content_rows_rotate_distinct_patterns(self) -> None:
        rows = self.map_rows(self.spec_14)
        content_rows = [
            row for i, row in rows.items()
            if self.gen.is_content_slide(i, 14)
        ]
        patterns = set()
        for row in content_rows:
            cells = [c.strip() for c in row.strip("|").split("|")]
            pattern = cells[5]
            self.assertIn(self.gen.PATTERN_NOTE, pattern)
            patterns.add(pattern.replace(self.gen.PATTERN_NOTE, "").strip())
        self.assertGreaterEqual(len(patterns), 4)
        for pattern in patterns:
            self.assertIn(pattern, self.gen.CONTENT_PATTERNS)

    def test_fixed_slots_unchanged(self) -> None:
        rows = self.map_rows(self.spec_14)
        self.assertIn("slide--title", rows[1])
        self.assertIn("slide--quote", rows[2])
        self.assertIn("slide--quote", rows[14])
        for divider in (4, 8, 12):
            self.assertIn("DIV+ divider-act", rows[divider])

    def test_short_deck_has_no_dividers(self) -> None:
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        spec = self.gen.generate_spec(template, "short", "Short", 8)
        rows = self.map_rows(spec)
        self.assertNotIn("DIV+ divider-act", "\n".join(rows.values()))
        self.assertIn(self.gen.PATTERN_NOTE, rows[4])

    def test_speaker_notes_column_in_header(self) -> None:
        self.assertIn("Speaker Notes", self.spec_14)

    def test_every_slide_row_has_speaker_notes(self) -> None:
        rows = self.map_rows(self.spec_14)
        for i, row in rows.items():
            cells = [c.strip() for c in row.strip("|").split("|")]
            self.assertGreaterEqual(len(cells), 9, f"Row {i} has fewer than 9 cells")
            notes_cell = cells[8]
            self.assertTrue(
                len(notes_cell) > 10,
                f"Row {i} speaker notes cell is empty or too short: {notes_cell!r}",
            )

    def test_content_slide_notes_tied_to_pattern(self) -> None:
        rows = self.map_rows(self.spec_14)
        for i, row in rows.items():
            if not self.gen.is_content_slide(i, 14):
                continue
            cells = [c.strip() for c in row.strip("|").split("|")]
            notes_cell = cells[8]
            self.assertNotEqual(notes_cell, "TBD", f"Row {i} notes is still TBD")
            self.assertNotIn("add notes here", notes_cell.lower(), f"Row {i} has generic placeholder")

    def test_fixed_slot_notes_not_generic(self) -> None:
        rows = self.map_rows(self.spec_14)
        for fixed_slot in (1, 2, 14):
            cells = [c.strip() for c in rows[fixed_slot].strip("|").split("|")]
            notes_cell = cells[8]
            self.assertTrue(len(notes_cell) > 10, f"Slot {fixed_slot} notes too short: {notes_cell!r}")
            self.assertNotIn("add notes here", notes_cell.lower())


if __name__ == "__main__":
    unittest.main()
