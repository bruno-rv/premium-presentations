from __future__ import annotations

import unittest

from slide_spec import (
    SlideSpecError,
    canonical_fields,
    canonical_row,
    decoded_title,
    diff_rows,
    parse_slide_map,
    rewrite_slide_map_ids,
)


MAP = """## Slide Map

| # | ID | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes | Audience Risk |
|---|----|-----|------|-------|-------------|----------------|-----------|----------------|---------------|---------------|
| 1 | intro | 0 | Title | Opening \\| Promise | Set the frame | slide--title | N/A | Welcome | Pause once. | Low |
| 2 | proof | 1 | Content | Evidence | Compare results | BAR bar-chart | Decision | Explain the delta | Name the baseline. | High |

## Evidence Data
"""

LEGACY_5 = """## Slide Map
| # | Type | Title | Key Content | Visual Pattern |
|---|------|-------|-------------|----------------|
| 1 | Title | Opening | Set the frame | slide--title |
| 2 | Content | Evidence | Compare results | BAR bar-chart |"""

LEGACY_7 = """## Slide Map
| # | Type | Title | Key Content | Visual Pattern | Voiceover Beat | Speaker Notes |
|---|------|-------|-------------|----------------|----------------|---------------|
| 1 | Title | Opening | Set the frame | slide--title | Welcome | Pause once. |
| 2 | Content | Evidence | Compare results | BAR bar-chart | Explain | Name baseline. |"""

CURRENT_9 = """## Slide Map
| # | Act | Type | Title | Key Content | Visual Pattern | Why Panel | Voiceover Beat | Speaker Notes |
|---|-----|------|-------|-------------|----------------|-----------|----------------|---------------|
| 1 | 0 | Title | Opening | Set the frame | slide--title | N/A | Welcome | Pause once. |
| 2 | 1 | Content | Evidence | Compare results | BAR bar-chart | Decision | Explain | Name baseline. |"""


class SlideSpecTests(unittest.TestCase):
    def test_parses_ids_escaped_pipe_and_unknown_column(self) -> None:
        spec = parse_slide_map(MAP, require_ids=True)
        self.assertEqual([row.slide_id for row in spec.rows], ["intro", "proof"])
        self.assertEqual(spec.rows[0].fields["Title"], "Opening | Promise")
        self.assertEqual(spec.rows[1].fields["Audience Risk"], "High")
        self.assertEqual(spec.header_line_no, 3)
        self.assertEqual(spec.separator_line_no, 4)
        self.assertEqual(spec.rows[0].line_no, 5)

    def test_parses_legacy_and_current_maps_without_ids(self) -> None:
        cases = {
            "legacy 5-column": LEGACY_5,
            "legacy 7-column": LEGACY_7,
            "current 9-column": CURRENT_9,
        }
        for label, text in cases.items():
            with self.subTest(label=label):
                spec = parse_slide_map(text)
                self.assertEqual([row.slide_id for row in spec.rows], ["", ""])
                with self.assertRaises(SlideSpecError) as raised:
                    parse_slide_map(text, require_ids=True)
                self.assertEqual(raised.exception.code, "missing_id")

    def test_canonical_row_ignores_markdown_spacing(self) -> None:
        compact = MAP.replace("| 2 | proof |", "|2|proof|")
        self.assertEqual(
            canonical_row(parse_slide_map(MAP, require_ids=True).rows[1]),
            canonical_row(parse_slide_map(compact, require_ids=True).rows[1]),
        )

    def test_canonical_fields_ignores_identity_columns(self) -> None:
        fields = {"#": "7", "ID": "proof", "Title": "Evidence", "Audience Risk": "High"}
        self.assertEqual(
            canonical_fields(fields),
            b'{"Audience Risk":"High","Title":"Evidence"}',
        )

    def test_decoded_title_unescapes_html_entities(self) -> None:
        encoded = MAP.replace("Evidence", "Evidence &amp; Proof")
        row = parse_slide_map(encoded, require_ids=True).rows[1]
        self.assertEqual(decoded_title(row), "Evidence & Proof")

    def test_diff_reports_fields_by_stable_id(self) -> None:
        edited = MAP.replace("Compare results", "Compare verified results")
        diff = diff_rows(
            parse_slide_map(MAP, require_ids=True),
            parse_slide_map(edited, require_ids=True),
        )
        self.assertEqual(diff.structural_reasons, ())
        self.assertEqual(diff.changes[0].slide_id, "proof")
        self.assertEqual(diff.changes[0].fields, ("Key Content",))

    def test_diff_reports_structural_reasons_in_fixed_order(self) -> None:
        one_row = MAP.replace(
            "| 2 | proof | 1 | Content | Evidence | Compare results | BAR bar-chart | Decision | Explain the delta | Name the baseline. | High |\n",
            "",
        )
        count_diff = diff_rows(
            parse_slide_map(MAP, require_ids=True),
            parse_slide_map(one_row, require_ids=True),
        )
        self.assertEqual(
            count_diff.structural_reasons,
            ("slide_count_changed", "identity_set_changed"),
        )

        reordered = MAP.replace("| intro |", "| temporary |").replace(
            "| proof |", "| intro |"
        ).replace("| temporary |", "| proof |")
        order_diff = diff_rows(
            parse_slide_map(MAP, require_ids=True),
            parse_slide_map(reordered, require_ids=True),
        )
        self.assertEqual(order_diff.structural_reasons, ("identity_order_changed",))
        self.assertEqual(order_diff.changes, ())

    def test_rewrite_adds_ids_without_changing_other_cells(self) -> None:
        legacy = """## Slide Map
| # | Act | Type | Title | Key Content |
|---|-----|------|-------|-------------|
| 1 | 0 | Title | Opening \\| Promise | Set the frame |
| 2 | 1 | Content | Evidence | Compare results |"""
        rewritten = rewrite_slide_map_ids(legacy, ["intro", "proof"])
        parsed = parse_slide_map(rewritten, require_ids=True)
        self.assertEqual([row.slide_id for row in parsed.rows], ["intro", "proof"])
        self.assertEqual(parsed.rows[0].fields["Title"], "Opening | Promise")
        without_insertions = rewritten
        for inserted in (" ID |", " --- |", " intro |", " proof |"):
            without_insertions = without_insertions.replace(inserted, "", 1)
        self.assertEqual(without_insertions, legacy)

    def test_rewrite_updates_existing_id_column_without_duplicating_it(self) -> None:
        rewritten = rewrite_slide_map_ids(MAP, ["opening", "evidence"])
        parsed = parse_slide_map(rewritten, require_ids=True)
        self.assertEqual(parsed.headers.count("ID"), 1)
        self.assertEqual([row.slide_id for row in parsed.rows], ["opening", "evidence"])

    def test_rewrite_validates_the_full_id_set(self) -> None:
        cases = {
            "wrong count": ["intro"],
            "duplicate": ["intro", "intro"],
            "malformed": ["intro", "proof space"],
        }
        for label, ids in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideSpecError):
                rewrite_slide_map_ids(LEGACY_5, ids)

    def test_rejects_invalid_identity_inputs(self) -> None:
        cases = {
            "duplicate": MAP.replace("| proof |", "| intro |"),
            "malformed": MAP.replace("| proof |", "| proof space |"),
            "missing": MAP.replace("| proof |", "|  |"),
            "nonsequential ordinal": MAP.replace("| 2 | proof |", "| 4 | proof |"),
        }
        for label, text in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideSpecError):
                parse_slide_map(text, require_ids=True)

    def test_pipe_escaping_uses_odd_even_backslash_parity(self) -> None:
        cases = {
            "one": (
                r"| 1 | intro | Title | One \| Pipe | Body | Pattern |",
                "One | Pipe",
            ),
            "two": (
                r"| 1 | intro | Title | Two \\| Body | Pattern |",
                "Two \\",
            ),
            "three": (
                r"| 1 | intro | Title | Three \\\| Pipe | Body | Pattern |",
                r"Three \| Pipe",
            ),
        }
        header = """## Slide Map
| # | ID | Type | Title | Key Content | Visual Pattern |
|---|----|------|-------|-------------|----------------|
"""
        for label, (row, expected) in cases.items():
            with self.subTest(label=label):
                parsed = parse_slide_map(header + row, require_ids=True)
                self.assertEqual(parsed.rows[0].fields["Title"], expected)

    def test_rewrite_preserves_newline_style_and_trailing_newline(self) -> None:
        with_final_newline = LEGACY_5.replace("\n", "\r\n") + "\r\n"
        rewritten = rewrite_slide_map_ids(with_final_newline, ["intro", "proof"])
        self.assertTrue(rewritten.endswith("\r\n"))
        self.assertNotIn("\n", rewritten.replace("\r\n", ""))

        without_final_newline = LEGACY_5.replace("\n", "\r\n")
        rewritten = rewrite_slide_map_ids(without_final_newline, ["intro", "proof"])
        self.assertFalse(rewritten.endswith(("\n", "\r")))
        self.assertNotIn("\n", rewritten.replace("\r\n", ""))

    def test_duplicate_normalized_headers_are_rejected(self) -> None:
        duplicate = LEGACY_5.replace(
            "| # | Type | Title | Key Content | Visual Pattern |",
            "| # | Type | Title | Key Content | key   content |",
        )
        with self.assertRaises(SlideSpecError) as raised:
            parse_slide_map(duplicate)
        self.assertEqual(raised.exception.code, "duplicate_header")

    def test_last_exact_depth_slide_map_section_wins(self) -> None:
        first = LEGACY_5.replace("Opening", "Discarded").replace("## Slide Map", "### Slide Map")
        second = MAP.replace("## Evidence Data\n", "")
        third = MAP.replace("intro", "final-intro").replace("proof", "final-proof")
        text = first + "\n\n" + second + "\n" + third
        parsed = parse_slide_map(text, require_ids=True)
        self.assertEqual([row.slide_id for row in parsed.rows], ["final-intro", "final-proof"])

        rewritten = rewrite_slide_map_ids(text, ["new-intro", "new-proof"])
        self.assertIn("| 1 | intro |", rewritten)
        self.assertIn("| 1 | new-intro |", rewritten)

    def test_rejects_malformed_detected_map_with_stable_codes(self) -> None:
        cases = {
            "missing #": (
                LEGACY_5.replace("| # | Type |", "| Number | Type |"),
                "missing_header",
            ),
            "bad row width": (
                LEGACY_5.replace("| 2 | Content | Evidence | Compare results | BAR bar-chart |", "| 2 | Content | Evidence |"),
                "malformed_row",
            ),
            "unterminated row": (LEGACY_5.removesuffix("|"), "malformed_row"),
            "bad ordinal": (LEGACY_5.replace("| 2 | Content |", "| two | Content |"), "malformed_row"),
        }
        for label, (text, code) in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(SlideSpecError) as raised:
                    parse_slide_map(text)
                self.assertEqual(raised.exception.code, code)


if __name__ == "__main__":
    unittest.main()
