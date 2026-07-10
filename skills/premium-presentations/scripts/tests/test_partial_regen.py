from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import partial_regen


class PairFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write_uninitialized_pair(self) -> tuple[Path, Path]:
        deck = self.root / "lesson-slides.html"
        spec = self.root / "lesson-slide-spec.md"
        deck.write_text(
            '<!doctype html><html><body><div id="deck">\n'
            '<section class="slide" data-nav-title="Opening"><h1>Original body</h1><aside class="notes">Open the lesson.</aside></section>\n'
            '<section class="slide" data-nav-title="Proof"><h2>Evidence</h2><aside class="notes">Explain the proof.</aside></section>\n'
            "</div></body></html>",
            encoding="utf-8",
        )
        spec.write_text(
            "## Slide Map\n\n"
            "| # | Act | Type | Title | Key Content |\n"
            "|---|-----|------|-------|-------------|\n"
            "| 1 | 0 | Title | Opening | Establish context |\n"
            "| 2 | 1 | Content | Proof | Compare results |\n",
            encoding="utf-8",
        )
        return deck, spec

    def write_initialized_pair(self) -> tuple[Path, Path]:
        deck, spec = self.write_uninitialized_pair()
        deck_text, spec_text, _ = partial_regen._build_init_candidates(deck, spec)
        deck.write_text(deck_text, encoding="utf-8")
        spec.write_text(spec_text, encoding="utf-8")
        return deck, spec

    def run_main(self, arguments: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = partial_regen.main(arguments)
        return result, output.getvalue()


class PlanningTests(PairFixture):
    def test_init_preview_is_read_only_and_deterministic(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        before = (deck.read_bytes(), spec.read_bytes())
        before_mtimes = (deck.stat().st_mtime_ns, spec.stat().st_mtime_ns)
        before_tree = tuple(
            sorted(path.relative_to(deck.parent) for path in deck.parent.rglob("*"))
        )

        first = partial_regen.preview_init(deck, spec)
        second = partial_regen.preview_init(deck, spec)

        self.assertEqual(first, second)
        self.assertEqual(first.status, "initialization_preview")
        self.assertEqual(tuple(first.changed), ("slide-1", "slide-2"))
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)
        self.assertEqual(
            (deck.stat().st_mtime_ns, spec.stat().st_mtime_ns), before_mtimes
        )
        self.assertEqual(
            tuple(sorted(path.relative_to(deck.parent) for path in deck.parent.rglob("*"))),
            before_tree,
        )

    def test_state_json_is_deterministic_and_script_safe(self) -> None:
        state = {
            "version": 1,
            "deck": "lesson-slides.html",
            "spec": "lesson-slide-spec.md",
            "order": ["slide-1"],
            "envelopeHash": "sha256:" + "a" * 64,
            "slides": {
                "slide-1": {
                    "row": {"Title": "A </script> title"},
                    "rowHash": "sha256:" + "b" * 64,
                    "sectionHash": "sha256:" + "c" * 64,
                }
            },
        }
        first = partial_regen.render_state(state)
        second = partial_regen.render_state(dict(reversed(list(state.items()))))
        self.assertEqual(first, second)
        self.assertNotIn("</script> title", first)
        self.assertIn("\\u003c/script> title", first)

    def test_initialized_state_round_trips_and_has_current_hashes(self) -> None:
        deck, spec = self.write_initialized_pair()
        state = partial_regen.load_state(deck.read_text(encoding="utf-8"))

        self.assertEqual(
            tuple(state),
            ("version", "deck", "spec", "order", "envelopeHash", "slides"),
        )
        self.assertEqual(state["deck"], deck.name)
        self.assertEqual(state["spec"], spec.name)
        self.assertEqual(state["order"], ["slide-1", "slide-2"])
        self.assertEqual(
            state["envelopeHash"],
            partial_regen.envelope_hash(deck.read_text(encoding="utf-8")),
        )
        self.assertEqual(partial_regen.plan_pair(deck, spec).status, "no_changes")

    def test_load_state_rejects_bad_schema_paths_and_row_hashes(self) -> None:
        deck, _ = self.write_initialized_pair()
        original = deck.read_text(encoding="utf-8")
        state = dict(partial_regen.load_state(original))
        cases = []

        with_extra = dict(state)
        with_extra["extra"] = True
        cases.append(with_extra)

        with_path = dict(state)
        with_path["deck"] = "../lesson-slides.html"
        cases.append(with_path)

        with_bad_hash = dict(state)
        with_bad_hash["slides"] = {
            key: dict(value) for key, value in state["slides"].items()
        }
        with_bad_hash["slides"]["slide-1"]["rowHash"] = "sha256:" + "0" * 64
        cases.append(with_bad_hash)

        span = partial_regen.parse_json_script_span(original, partial_regen.STATE_ID)
        for candidate in cases:
            with self.subTest(candidate=candidate):
                content = json.dumps(candidate, separators=(",", ":")).replace(
                    "<", "\\u003c"
                )
                payload = (
                    '<script type="application/json" id="premium-regen-state">'
                    f"{content}</script>"
                )
                html = original[: span.start] + payload + original[span.end :]
                with self.assertRaises(partial_regen.RegenInputError):
                    partial_regen.load_state(html)

    def test_plan_reports_one_and_multiple_row_changes(self) -> None:
        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace("Opening", "New Opening"),
            encoding="utf-8",
        )
        one = partial_regen.plan_pair(deck, spec)
        self.assertEqual(one.status, "changes_planned")
        self.assertEqual(one.changed["slide-1"], ("Title",))

        spec.write_text(
            spec.read_text(encoding="utf-8").replace(
                "Compare results", "Compare verified results"
            ),
            encoding="utf-8",
        )
        two = partial_regen.plan_pair(deck, spec)
        self.assertEqual(tuple(two.changed), ("slide-1", "slide-2"))

    def test_plan_refuses_structural_change_and_slide_drift(self) -> None:
        deck, spec = self.write_initialized_pair()
        reordered = (
            spec.read_text(encoding="utf-8")
            .replace("| 1 | slide-1 |", "| 1 | swap |", 1)
            .replace("| 2 | slide-2 |", "| 2 | slide-1 |", 1)
            .replace("| 1 | swap |", "| 1 | slide-2 |", 1)
        )
        spec.write_text(reordered, encoding="utf-8")
        structural = partial_regen.plan_pair(deck, spec)
        self.assertEqual(
            (structural.status, structural.reason_code),
            ("full_regeneration_required", "identity_order_changed"),
        )

        deck, spec = self.write_initialized_pair()
        deck.write_text(
            deck.read_text(encoding="utf-8").replace(
                "Original body", "Manual body edit"
            ),
            encoding="utf-8",
        )
        drift = partial_regen.plan_pair(deck, spec)
        self.assertEqual(
            (drift.status, drift.reason_code),
            ("baseline_drift", "section_hash_changed"),
        )

    def test_plan_refuses_envelope_drift_before_section_drift(self) -> None:
        deck, spec = self.write_initialized_pair()
        source = deck.read_text(encoding="utf-8")
        deck.write_text(
            source.replace("<body>", '<body data-edited="yes">').replace(
                "Original body", "Manual body edit"
            ),
            encoding="utf-8",
        )

        result = partial_regen.plan_pair(deck, spec)

        self.assertEqual(
            (result.status, result.reason_code),
            ("full_regeneration_required", "global_envelope_changed"),
        )

    def test_init_rejects_title_misalignment_and_unsafe_pairs(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        deck.write_text(
            deck.read_text(encoding="utf-8").replace(
                'data-nav-title="Opening"', 'data-nav-title="Different"'
            ),
            encoding="utf-8",
        )
        with self.assertRaises(partial_regen.RegenInputError):
            partial_regen.preview_init(deck, spec)

        symlink = self.root / "linked-spec.md"
        try:
            os.symlink(spec, symlink)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are unavailable")
        with self.assertRaises(partial_regen.RegenInputError):
            partial_regen.preview_init(deck, symlink)

    def test_public_cli_init_and_plan_are_read_only(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        before = (deck.read_bytes(), spec.read_bytes())

        init_rc, init_output = self.run_main(
            ["init", "--deck", str(deck), "--spec", str(spec)]
        )

        self.assertEqual(init_rc, 0)
        self.assertIn("slide-1", init_output)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)

        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace("Opening", "New Opening"),
            encoding="utf-8",
        )
        before = (deck.read_bytes(), spec.read_bytes())
        plan_rc, plan_output = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec)]
        )

        self.assertEqual(plan_rc, 0)
        self.assertIn("Claude Code or Codex", plan_output)
        self.assertIn("ID=FILE", plan_output)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)

    def test_public_cli_json_contract_and_result_exit_codes(self) -> None:
        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace("Opening", "New Opening"),
            encoding="utf-8",
        )
        rc, output = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec), "--json"]
        )
        payload = json.loads(output)
        self.assertEqual(rc, 0)
        self.assertEqual(
            tuple(payload), ("status", "reasonCode", "changed", "messages")
        )
        self.assertEqual(payload["changed"], {"slide-1": ["Title"]})

        spec.write_text(
            spec.read_text(encoding="utf-8")
            .replace("| 1 | slide-1 |", "| 1 | swap |", 1)
            .replace("| 2 | slide-2 |", "| 2 | slide-1 |", 1)
            .replace("| 1 | swap |", "| 1 | slide-2 |", 1),
            encoding="utf-8",
        )
        structural_rc, _ = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec)]
        )
        self.assertEqual(structural_rc, 2)

        deck, spec = self.write_initialized_pair()
        deck.write_text(
            deck.read_text(encoding="utf-8").replace(
                "Original body", "Manual body edit"
            ),
            encoding="utf-8",
        )
        drift_rc, _ = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec)]
        )
        self.assertEqual(drift_rc, 3)

    def test_public_cli_json_errors_are_single_deterministic_objects(self) -> None:
        rc, output = self.run_main(["plan", "--json"])

        self.assertEqual(rc, 1)
        self.assertEqual(output.count("\n"), 1)
        payload = json.loads(output)
        self.assertEqual(
            tuple(payload), ("status", "reasonCode", "changed", "messages")
        )
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["changed"], {})

    def test_public_cli_help_preserves_success_exit_code(self) -> None:
        rc, output = self.run_main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("init", output)
        self.assertIn("plan", output)


if __name__ == "__main__":
    unittest.main()
