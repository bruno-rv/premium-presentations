#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR_PATH = ROOT / "scripts" / "validate_deck.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_deck", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def slide(body: str, cls: str = "slide") -> str:
    return f'<section class="{cls}">{body}</section>'


BARE = slide("<h2>Heading</h2><p class='slide__body'>Two sentences.</p>")
ANCHORED = slide('<h2>H</h2><div class="stats-row"><div class="stat-card">x</div></div>')


class DeckVarietyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def variety(self, html: str):
        return self.validator.validate_deck_variety(html)

    def test_bare_slide_detected(self) -> None:
        msgs, _ = self.variety(BARE)
        self.assertEqual(1, len(msgs))
        self.assertIn("bare slide 1", msgs[0])

    def test_component_marker_is_not_bare(self) -> None:
        msgs, distinct = self.variety(ANCHORED)
        self.assertEqual([], msgs)
        self.assertEqual(1, distinct)

    def test_raw_visuals_are_not_bare(self) -> None:
        for tag in ("<svg viewBox='0 0 1 1'></svg>", "<table><tr></tr></table>", "<pre>x</pre>"):
            msgs, _ = self.variety(slide(f"<h2>H</h2>{tag}"))
            self.assertEqual([], msgs, tag)

    def test_exempt_slide_types_are_not_bare(self) -> None:
        for modifier in ("slide--title", "slide--quote", "slide--divider", "slide--diagram"):
            msgs, _ = self.variety(slide("<h2>H</h2>", cls=f"slide {modifier}"))
            self.assertEqual([], msgs, modifier)

    def test_consecutive_bare_run_warns(self) -> None:
        msgs, _ = self.variety(BARE * 3)
        run_msgs = [m for m in msgs if "consecutive bare" in m]
        self.assertEqual(1, len(run_msgs))
        self.assertIn("slides 1–3", run_msgs[0])

    def test_two_bare_slides_do_not_trigger_run_warning(self) -> None:
        msgs, _ = self.variety(BARE * 2)
        self.assertEqual([], [m for m in msgs if "consecutive bare" in m])

    def test_low_variety_on_large_deck(self) -> None:
        html = ANCHORED * 8
        msgs, distinct = self.variety(html)
        self.assertEqual(1, distinct)
        self.assertTrue(any("low visual variety" in m for m in msgs))

    def test_varied_large_deck_passes(self) -> None:
        html = "".join(
            slide(f'<h2>H</h2><div class="{marker}">x</div>')
            for marker in ("stats-row", "compare-split", "timeline-grid", "live-flow")
        ) + slide("<h2>T</h2>", cls="slide slide--title") * 4
        msgs, distinct = self.variety(html)
        self.assertEqual(4, distinct)
        self.assertEqual([], [m for m in msgs if "low visual variety" in m])

    def test_strict_variety_flag_fails_validation(self) -> None:
        html = (
            "<!DOCTYPE html><html lang='en'><head><style>"
            "@media (prefers-reduced-motion: reduce) {} "
            ".deck { scroll-snap-type: y mandatory; } .premium-bg-3d {}"
            "</style></head><body><div id='deck'>"
            + ANCHORED + BARE +
            "</div><script>/* SlideEngine PremiumPresentations */"
            "document.addEventListener('DOMContentLoaded', function () { new SlideEngine(); });"
            "</script></body></html>"
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.html"
            path.write_text(html, encoding="utf-8")
            self.assertEqual(0, self.validator.validate(path))
            self.assertEqual(1, self.validator.validate(path, strict_variety=True))


def _minimal_deck(slides_html: str) -> str:
    return (
        "<!DOCTYPE html><html lang='en'><head><style>"
        "@media (prefers-reduced-motion: reduce) {} "
        ".deck { scroll-snap-type: y mandatory; } .premium-bg-3d {}"
        "</style></head><body><div id='deck'>"
        + slides_html
        + "</div><script>/* SlideEngine PremiumPresentations */"
        "document.addEventListener('DOMContentLoaded', function () { new SlideEngine(); });"
        "</script></body></html>"
    )


SLIDE_WITH_NOTES = (
    '<section class="slide stats-row">'
    '<h2>H</h2><div class="stats-row"><div class="stat-card">x</div></div>'
    '<aside class="notes">What to say here. Transition to next topic. Keep it brief.</aside>'
    "</section>"
)

SLIDE_WITHOUT_NOTES = (
    '<section class="slide stats-row">'
    '<h2>H</h2><div class="stats-row"><div class="stat-card">x</div></div>'
    "</section>"
)


class MissingNotesWarningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()

    def validate_html(self, html: str) -> tuple[int, list[str]]:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.html"
            path.write_text(html, encoding="utf-8")
            import io
            import contextlib

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = self.validator.validate(path)
            output = buf.getvalue()
            warnings = [
                line.strip()
                for line in output.splitlines()
                if line.strip().startswith("WARN:")
            ]
            return code, warnings

    def test_missing_notes_produces_warning(self) -> None:
        html = _minimal_deck(SLIDE_WITHOUT_NOTES * 2)
        code, warnings = self.validate_html(html)
        self.assertEqual(0, code, "missing notes must not fail — it is a warning only")
        notes_warnings = [w for w in warnings if "aside" in w and "notes" in w]
        self.assertEqual(1, len(notes_warnings), f"Expected 1 notes warning, got: {warnings}")

    def test_missing_notes_warning_not_gated_by_strict_variety(self) -> None:
        html = _minimal_deck(SLIDE_WITHOUT_NOTES * 2)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.html"
            path.write_text(html, encoding="utf-8")
            import io
            import contextlib

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code_normal = self.validator.validate(path, strict_variety=False)
            output_normal = buf.getvalue()

            buf2 = io.StringIO()
            with contextlib.redirect_stdout(buf2):
                code_strict = self.validator.validate(path, strict_variety=True)
            output_strict = buf2.getvalue()

        self.assertEqual(0, code_normal)
        self.assertIn("aside", output_normal)
        self.assertIn("aside", output_strict)

    def test_all_notes_present_no_warning(self) -> None:
        html = _minimal_deck(SLIDE_WITH_NOTES * 2)
        code, warnings = self.validate_html(html)
        self.assertEqual(0, code)
        notes_warnings = [w for w in warnings if "aside" in w and "notes" in w]
        self.assertEqual(0, len(notes_warnings), f"Unexpected notes warnings: {notes_warnings}")

    def test_partial_notes_warns_correct_count(self) -> None:
        html = _minimal_deck(SLIDE_WITH_NOTES + SLIDE_WITHOUT_NOTES + SLIDE_WITHOUT_NOTES)
        code, warnings = self.validate_html(html)
        self.assertEqual(0, code)
        notes_warnings = [w for w in warnings if "aside" in w and "notes" in w]
        self.assertEqual(1, len(notes_warnings))
        self.assertIn("2 slide(s)", notes_warnings[0])


if __name__ == "__main__":
    unittest.main()
