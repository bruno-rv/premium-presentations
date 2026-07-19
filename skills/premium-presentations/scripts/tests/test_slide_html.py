from __future__ import annotations

import unittest
from types import MappingProxyType

from slide_html import (
    SlideHtmlError,
    assign_slide_ids,
    parse_json_script_span,
    parse_slide_spans,
    set_slide_budgets,
    splice_sections,
    validate_fragment,
)
from slide_spec import SlideSpecRow


DECK = """<!doctype html><html><body><div id="deck">
<section class="slide" id="intro" data-nav-title="Opening"><h1>Opening</h1><section class="detail"><p>Nested</p></section><template><section><p>Template section</p></section></template><!-- <section class="slide">fake</section> --><aside class="notes">Say opening.</aside></section>
<!-- between -->
<section data-nav-title="Proof" class="wide slide" id="proof"><script>const closing = "</section>";</script><h2>Proof</h2><aside class="notes">Explain proof.</aside></section>
</div></body></html>"""


def expected(slide_id: str, title: str) -> SlideSpecRow:
    return SlideSpecRow(slide_id, 1, MappingProxyType({"Title": title}), 1, "")


class SlideHtmlTests(unittest.TestCase):
    def test_exact_spans_ignore_raw_text_comments_and_nested_markup(self) -> None:
        spans = parse_slide_spans(DECK)
        self.assertEqual([span.slide_id for span in spans], ["intro", "proof"])
        self.assertEqual([DECK[span.start : span.end] for span in spans], [span.raw for span in spans])
        self.assertIn('<template><section><p>Template section</p></section></template>', spans[0].raw)
        self.assertIn('const closing = "</section>";', spans[1].raw)

    def test_slide_titles_are_decoded_once(self) -> None:
        source = DECK.replace('data-nav-title="Opening"', 'data-nav-title="Proof &amp;amp; Safety"')
        self.assertEqual(parse_slide_spans(source)[0].title, "Proof &amp; Safety")

    def test_json_state_span_is_real_unique_and_outside_deck(self) -> None:
        fake = '<script>const fake = \'<script type="application/json" id="premium-regen-state">{}<\\/script>\';</script>'
        state = '<script type="application/json" id="premium-regen-state">{"version":1}</script>'
        source = DECK.replace("</body>", fake + state + "</body>")
        span = parse_json_script_span(source, "premium-regen-state")
        self.assertEqual(span.content, '{"version":1}')
        self.assertEqual(source[span.start : span.end], state)
        self.assertEqual(source[span.content_start : span.content_end], span.content)
        self.assertFalse(span.inside_deck)

        with self.assertRaisesRegex(SlideHtmlError, "inside #deck"):
            parse_json_script_span(DECK.replace("</div></body>", state + "</div></body>"), "premium-regen-state")

    def test_json_state_span_rejects_missing_and_duplicate_matches(self) -> None:
        state = '<script type="application/json" id="premium-regen-state">{}</script>'
        with self.assertRaisesRegex(SlideHtmlError, "not found"):
            parse_json_script_span(DECK, "premium-regen-state")
        with self.assertRaisesRegex(SlideHtmlError, "multiple"):
            parse_json_script_span(DECK.replace("</body>", state + state + "</body>"), "premium-regen-state")

    def test_json_state_matching_uses_first_duplicate_attribute_value(self) -> None:
        later_matches = (
            '<script id="other" id="premium-regen-state" type="application/json">{}</script>',
            '<script id="premium-regen-state" type="text/plain" type="application/json">{}</script>',
        )
        for state in later_matches:
            with self.subTest(state=state), self.assertRaisesRegex(SlideHtmlError, "not found"):
                parse_json_script_span(
                    DECK.replace("</body>", state + "</body>"),
                    "premium-regen-state",
                )

        first_matches = (
            '<script id="premium-regen-state" id="other" type="application/json">{}</script>',
            '<script id="premium-regen-state" type="application/json" type="text/plain">{}</script>',
        )
        for state in first_matches:
            with self.subTest(state=state):
                span = parse_json_script_span(
                    DECK.replace("</body>", state + "</body>"),
                    "premium-regen-state",
                )
                self.assertEqual(span.content, "{}")

    def test_splice_preserves_every_untargeted_byte(self) -> None:
        replacement = '<section class="slide" id="proof" data-nav-title="Proof"><h2>Verified</h2><aside class="notes">Explain proof.</aside></section>'
        updated = splice_sections(DECK, {"proof": replacement})
        before = {span.slide_id: span.raw for span in parse_slide_spans(DECK)}
        after = {span.slide_id: span.raw for span in parse_slide_spans(updated)}
        self.assertEqual(after["intro"], before["intro"])
        self.assertEqual(updated.replace(after["proof"], "TARGET"), DECK.replace(before["proof"], "TARGET"))

    def test_splice_rejects_unknown_replacement_id(self) -> None:
        with self.assertRaisesRegex(SlideHtmlError, "missing"):
            splice_sections(DECK, {"missing": '<section class="slide"></section>'})

    def test_assigns_missing_ids_without_touching_section_bodies(self) -> None:
        no_ids = DECK.replace(' id="intro"', "").replace(' id="proof"', "")
        updated = assign_slide_ids(no_ids, ["slide-1", "slide-2"])
        spans = parse_slide_spans(updated)
        self.assertEqual([span.slide_id for span in spans], ["slide-1", "slide-2"])
        self.assertEqual([span.title for span in spans], ["Opening", "Proof"])
        self.assertEqual(
            updated.replace(' id="slide-1"', "").replace(' id="slide-2"', ""),
            no_ids,
        )

    def test_assign_ids_preserves_matching_existing_ids(self) -> None:
        self.assertEqual(assign_slide_ids(DECK, ["intro", "proof"]), DECK)

    def test_assign_ids_rejects_count_invalid_duplicates_and_mismatches(self) -> None:
        no_ids = DECK.replace(' id="intro"', "").replace(' id="proof"', "")
        cases = {
            "count": (no_ids, ["only-one"]),
            "malformed": (no_ids, ["not valid", "proof"]),
            "duplicates": (no_ids, ["same", "same"]),
            "different existing": (DECK, ["other", "proof"]),
        }
        for label, (source, ids) in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideHtmlError):
                assign_slide_ids(source, ids)

    def test_parse_rejects_invalid_deck_and_slide_structures(self) -> None:
        cases = {
            "missing deck": DECK.replace(' id="deck"', ""),
            "multiple deck": DECK.replace("</body>", '<div id="deck"></div></body>'),
            "duplicate attribute": DECK.replace('id="intro"', 'id="intro" ID="again"', 1),
            "self closing": DECK.replace("</div></body>", '<section class="slide" id="self" /></div></body>'),
            "unclosed": DECK.replace("</section>\n</div></body></html>", "\n</div></body></html>"),
            "duplicate id": DECK.replace('id="proof"', 'id="intro"'),
            "outside deck": DECK.replace("</body>", '<section class="slide" id="outside"></section></body>'),
            "nested slide": DECK.replace("<h1>Opening</h1>", '<section class="slide" id="nested"></section><h1>Opening</h1>'),
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideHtmlError):
                parse_slide_spans(source)

    def test_parse_rejects_mismatched_and_unclosed_ancestor_nesting(self) -> None:
        cases = {
            "mismatched ancestor": (
                '<div id="deck"><section class="slide" id="one"><div></section></div>'
            ),
            "unclosed ancestor": (
                '<div id="deck"><section class="slide" id="one"></section>'
            ),
        }
        for label, source in cases.items():
            with self.subTest(label=label), self.assertRaises(SlideHtmlError):
                parse_slide_spans(source)

    def test_deck_detection_uses_first_duplicate_id_value(self) -> None:
        later_match = DECK.replace(
            '<div id="deck">',
            '<div id="other" id="deck">',
        )
        with self.assertRaises(SlideHtmlError):
            parse_slide_spans(later_match)

        first_match = DECK.replace(
            '<div id="deck">',
            '<div id="deck" id="other">',
        )
        self.assertEqual(
            [span.slide_id for span in parse_slide_spans(first_match)],
            ["intro", "proof"],
        )

    def test_fragment_contract(self) -> None:
        valid = '<section class="wide slide" id="proof" data-nav-title="Proof &amp; Safety"><h2>Verified</h2><aside class="speaker notes">Explain proof.</aside></section>'
        self.assertEqual(validate_fragment(valid, expected("proof", "Proof &amp; Safety")), [])
        invalid = {
            "wrong id": valid.replace('id="proof"', 'id="other"'),
            "wrong title": valid.replace("Proof &amp; Safety", "Other"),
            "two roots": valid + valid,
            "script": valid.replace("<h2>", "<script></script><h2>"),
            "notes not final": valid.replace("</aside>", "</aside><p>After</p>"),
            "nested notes": valid.replace('<aside class="speaker notes">Explain proof.</aside>', '<div><aside class="notes">Explain proof.</aside></div>'),
            "deck control": valid.replace("<h2>", '<div id="controls"></div><h2>'),
            "duplicate id": valid.replace('id="proof"', 'id="proof" id="proof"'),
            "event handler": valid.replace("<h2>", '<a onclick="go()">x</a><h2>'),
            "javascript url": valid.replace("<h2>", '<a href=" javascript:alert(1)">x</a><h2>'),
            "outside text": "not allowed" + valid,
            "unclosed": valid.replace("</section>", ""),
        }
        for label, fragment in invalid.items():
            with self.subTest(label=label):
                self.assertTrue(validate_fragment(fragment, expected("proof", "Proof &amp; Safety")))

    def test_fragment_contract_enforces_data_budget_parity(self) -> None:
        valid = '<section class="wide slide" id="proof" data-nav-title="Proof &amp; Safety"><h2>Verified</h2><aside class="speaker notes">Explain proof.</aside></section>'
        # Insert data-budget on the root section tag (before closing '>').
        budgeted = valid.replace(
            'data-nav-title="Proof &amp; Safety">',
            'data-nav-title="Proof &amp; Safety" data-budget="70000">',
        )
        expected_row = expected("proof", "Proof &amp; Safety")

        self.assertEqual(validate_fragment(budgeted, expected_row, 70000), [])
        self.assertEqual(
            validate_fragment(budgeted, expected_row, None),
            ["fragment must not carry data-budget on a budgetless deck"],
        )
        self.assertEqual(
            validate_fragment(valid, expected_row, 70000),
            ["fragment must carry data-budget=70000"],
        )
        self.assertEqual(
            validate_fragment(budgeted, expected_row, 50000),
            ["fragment data-budget must equal 50000, got '70000'"],
        )

    def test_set_slide_budgets_only_touches_start_tags(self) -> None:
        updated = set_slide_budgets(DECK, {"intro": 50000, "proof": 70000})
        spans = parse_slide_spans(updated)
        self.assertIn('data-budget="50000"', spans[0].raw)
        self.assertIn('data-budget="70000"', spans[1].raw)
        # Bodies are byte-identical apart from the injected attribute.
        self.assertIn("<h1>Opening</h1>", spans[0].raw)
        self.assertIn("Explain proof.", spans[1].raw)

        # Replacing an existing data-budget updates it in place (no duplicate attr).
        again = set_slide_budgets(updated, {"intro": 65000})
        again_spans = parse_slide_spans(again)
        self.assertIn('data-budget="65000"', again_spans[0].raw)
        self.assertNotIn('data-budget="50000"', again_spans[0].raw)
        self.assertEqual(again_spans[1].raw, spans[1].raw)  # untouched slide unchanged

    def test_set_slide_budgets_rejects_unknown_ids_and_bad_types(self) -> None:
        with self.assertRaisesRegex(SlideHtmlError, "not present in deck"):
            set_slide_budgets(DECK, {"missing": 50000})
        with self.assertRaisesRegex(SlideHtmlError, "must be an int"):
            set_slide_budgets(DECK, {"intro": "50000"})

    def test_fragment_errors_have_stable_contract_order(self) -> None:
        fragment = '<div class="slide" id="wrong" data-nav-title="Wrong"><script></script></div>'
        self.assertEqual(
            validate_fragment(fragment, expected("proof", "Proof & Safety")),
            [
                "fragment must contain exactly one top-level section.slide",
                "fragment id must be 'proof'",
                "data-nav-title must equal decoded Title 'Proof & Safety'",
                "forbidden tag <script>",
                "fragment must contain exactly one direct aside.notes",
                "aside.notes must be the final direct child element",
            ],
        )


if __name__ == "__main__":
    unittest.main()
