from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import partial_regen
from slide_html import parse_slide_spans


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

        for unsafe_basename in (".", ".."):
            with_unsafe_basename = dict(state)
            with_unsafe_basename["deck"] = unsafe_basename
            cases.append(with_unsafe_basename)

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

    def test_plan_refuses_misplaced_id_column_as_full_regeneration(self) -> None:
        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace(
                "| # | ID | Act |", "| # | Act | ID |", 1
            ),
            encoding="utf-8",
        )

        result = partial_regen.plan_pair(deck, spec)
        cli_rc, _ = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec)]
        )

        self.assertEqual(
            (result.status, result.reason_code),
            ("full_regeneration_required", "invalid_identity_column"),
        )
        self.assertEqual(cli_rc, 2)

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

    def test_non_object_transaction_json_is_controlled_invalid_input(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        backup = deck.parent / ".partial-regen" / "backups" / "transaction"
        backup.mkdir(parents=True)
        (backup / "metadata.json").write_text("[]", encoding="utf-8")

        rc, output = self.run_main(
            ["plan", "--deck", str(deck), "--spec", str(spec), "--json"]
        )

        self.assertEqual(rc, 1)
        payload = json.loads(output)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["reasonCode"], "invalid_input")
        self.assertNotIn("AttributeError", output)

    def test_public_cli_help_preserves_success_exit_code(self) -> None:
        rc, output = self.run_main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("init", output)
        self.assertIn("plan", output)


class MutationTests(PairFixture):
    def setUp(self) -> None:
        super().setUp()
        doctor = mock.patch.object(partial_regen, "_run_deck_doctor", return_value=None)
        doctor.start()
        self.addCleanup(doctor.stop)

    def only_backup(self, deck: Path) -> Path:
        backups = sorted((deck.parent / ".partial-regen" / "backups").iterdir())
        self.assertTrue(backups)
        return backups[-1]

    def write_fragment(self, slide_id: str, title: str, body: str) -> Path:
        path = self.root / f"{slide_id}.html"
        path.write_text(
            f'<section class="slide" id="{slide_id}" data-nav-title="{title}">'
            f'<div class="content">{body}</div>'
            '<aside class="notes">Explain the updated evidence.</aside></section>',
            encoding="utf-8",
        )
        return path

    def write_ready_apply_pair(self) -> tuple[Path, Path, Path]:
        deck, spec = self.write_initialized_pair()
        spec.write_text(
            spec.read_text(encoding="utf-8").replace(
                "Compare results", "Compare verified results"
            ),
            encoding="utf-8",
        )
        return deck, spec, self.write_fragment("slide-2", "Proof", "Verified body")

    def test_init_apply_backs_up_both_files_and_commits_state(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        original = {deck.name: deck.read_bytes(), spec.name: spec.read_bytes()}
        rc, _ = self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])
        self.assertEqual(rc, 0)
        self.assertEqual(partial_regen.load_state(deck.read_text(encoding="utf-8"))["order"], ["slide-1", "slide-2"])
        backup = self.only_backup(deck)
        metadata = json.loads((backup / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual([item["target"] for item in metadata["targets"]], [deck.name, spec.name])
        self.assertEqual(metadata["status"], "committed")
        for name, content in original.items():
            self.assertEqual((backup / name).read_bytes(), content)

    def test_apply_exact_set_preserves_other_slide_and_keeps_spec(self) -> None:
        deck, spec, fragment = self.write_ready_apply_pair()
        before = {span.slide_id: span.raw for span in parse_slide_spans(deck.read_text())}
        spec_before = spec.read_bytes()
        rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"])
        self.assertEqual(rc, 0)
        after = {span.slide_id: span.raw for span in parse_slide_spans(deck.read_text())}
        self.assertEqual(after["slide-1"], before["slide-1"])
        self.assertIn("Verified body", after["slide-2"])
        self.assertEqual(spec.read_bytes(), spec_before)

    def test_public_rollback_of_apply_restores_deck_and_keeps_edited_spec(self) -> None:
        deck, spec, fragment = self.write_ready_apply_pair()
        original_deck = deck.read_bytes()
        edited_spec = spec.read_bytes()
        self.assertEqual(
            self.run_main(
                [
                    "apply",
                    "--deck",
                    str(deck),
                    "--spec",
                    str(spec),
                    "--fragment",
                    f"slide-2={fragment}",
                ]
            )[0],
            0,
        )
        backup = self.only_backup(deck)
        self.assertEqual(
            self.run_main(
                ["rollback", "--deck", str(deck), "--backup", str(backup)]
            )[0],
            0,
        )
        self.assertEqual(deck.read_bytes(), original_deck)
        self.assertEqual(spec.read_bytes(), edited_spec)

    def test_apply_rejects_invalid_fragment_sets_and_inputs(self) -> None:
        deck, spec, fragment = self.write_ready_apply_pair()
        other = self.write_fragment("slide-1", "Opening", "Extra")
        cases = [
            [f"slide-1={other}"],
            [f"slide-2={fragment}", f"slide-2={fragment}"],
            [f"slide-2={fragment}", f"slide-1={other}"],
        ]
        for fragments in cases:
            with self.subTest(fragments=fragments):
                rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), *sum((["--fragment", value] for value in fragments), [])])
                self.assertEqual(rc, 1)
        linked = self.root / "linked.html"
        try:
            os.symlink(fragment, linked)
        except OSError:
            self.skipTest("symlinks unavailable")
        rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={linked}"])
        self.assertEqual(rc, 1)

    def test_apply_rejects_new_capabilities_and_invalid_fragments(self) -> None:
        for label, body in {
            "journey": '<div class="journey-stage"></div>',
            "flow": '<div class="live-flow"></div>',
            "mermaid": '<pre class="mermaid">graph TD; A--&gt;B;</pre>',
            "glossary": '<button class="term-link" data-term="NEW_TERM">Term</button>',
            "theme": '<div class="slide--title">Hero</div>',
        }.items():
            with self.subTest(label=label):
                deck, spec, _ = self.write_ready_apply_pair()
                fragment = self.write_fragment("slide-2", "Proof", body)
                rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"])
                self.assertEqual(rc, 2)
        bad = self.write_fragment("wrong", "Wrong", "Bad")
        rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={bad}"])
        self.assertEqual(rc, 1)

    def test_fragment_capabilities_support_html_attribute_forms(self) -> None:
        for class_name, capability in {
            "journey-stage": "journey",
            "live-flow": "flow",
            "term-link": "glossary",
            "mermaid": "mermaid",
            "slide--title": "theme_homage",
            "slide--divider": "theme_homage",
        }.items():
            for form, value in {
                "unquoted": class_name,
                "entity_encoded": class_name.replace("-", "&#45;"),
            }.items():
                with self.subTest(class_name=class_name, form=form):
                    self.assertEqual(
                        partial_regen._fragment_capabilities(f"<div class={value}></div>"),
                        {capability},
                    )

    def test_failure_seams_and_rollback_recover_original_bytes(self) -> None:
        for seam in ("_create_backup", "_run_deck_doctor", "_replace_file", "_validate_committed_pair"):
            with self.subTest(seam=seam):
                deck, spec, fragment = self.write_ready_apply_pair()
                before = (deck.read_bytes(), spec.read_bytes())
                with mock.patch.object(partial_regen, seam, side_effect=OSError("injected")):
                    rc, _ = self.run_main(["apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"slide-2={fragment}"])
                self.assertEqual(rc, 1)
                self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)

    def test_rollback_restores_init_backup_and_rejects_tampering(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        original = (deck.read_bytes(), spec.read_bytes())
        self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 0)
        backup = self.only_backup(deck)
        self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 0)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), original)
        self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup / "..")])[0], 1)

    def test_rollback_of_pre_state_init_backup_derives_spec_target(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        original = (deck.read_bytes(), spec.read_bytes())
        partial_regen._create_backup(deck, "init", (deck, spec))
        backup = self.only_backup(deck)
        deck.write_bytes(deck.read_bytes() + b"\n<!-- changed -->")
        spec.write_text(spec.read_text(encoding="utf-8").replace("Opening", "Changed"), encoding="utf-8")

        rc, output = self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])

        self.assertEqual(rc, 0, output)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), original)

    def test_rollback_init_uses_nonconventional_metadata_spec_with_corrupt_state(self) -> None:
        deck, conventional_spec = self.write_uninitialized_pair()
        spec = self.root / "custom-plan.txt"
        spec.write_bytes(conventional_spec.read_bytes())
        original = (deck.read_bytes(), spec.read_bytes())
        partial_regen._create_backup(deck, "init", (deck, spec))
        backup = self.only_backup(deck)
        deck.write_text(
            deck.read_text(encoding="utf-8").replace(
                "</body>",
                '<script type="application/json" id="premium-regen-state">[]</script></body>',
            ),
            encoding="utf-8",
        )
        spec.write_text(spec.read_text(encoding="utf-8").replace("Opening", "Changed"), encoding="utf-8")

        rc, output = self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])

        self.assertEqual(rc, 0, output)
        self.assertEqual((deck.read_bytes(), spec.read_bytes()), original)

    def test_init_publish_failures_restore_originals_and_close_journal(self) -> None:
        for failed_call in (1, 2):
            with self.subTest(failed_call=failed_call):
                deck, spec = self.write_uninitialized_pair()
                original = (deck.read_bytes(), spec.read_bytes())
                real_replace = partial_regen._replace_file
                calls = 0

                def fail_publish(source: Path, target: Path) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == failed_call:
                        raise OSError("publish failure")
                    real_replace(source, target)

                with mock.patch.object(partial_regen, "_replace_file", side_effect=fail_publish):
                    self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 1)
                self.assertEqual((deck.read_bytes(), spec.read_bytes()), original)
                backup = self.only_backup(deck)
                self.assertEqual(json.loads((backup / "metadata.json").read_text())["status"], "rolled_back")

    def test_rollback_publish_failures_restore_pre_rollback_view(self) -> None:
        for failed_call in (1, 2):
            with self.subTest(failed_call=failed_call):
                deck, spec = self.write_uninitialized_pair()
                self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 0)
                backup = self.only_backup(deck)
                before = (deck.read_bytes(), spec.read_bytes())
                real_replace = partial_regen._replace_file
                calls = 0

                def fail_publish(source: Path, target: Path) -> None:
                    nonlocal calls
                    calls += 1
                    if calls == failed_call:
                        raise OSError("rollback publish failure")
                    real_replace(source, target)

                with mock.patch.object(partial_regen, "_replace_file", side_effect=fail_publish):
                    self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 1)
                self.assertEqual((deck.read_bytes(), spec.read_bytes()), before)
                rollback_metadata = json.loads((backup / "rollback-metadata.json").read_text())
                self.assertEqual(rollback_metadata["status"], "rolled_back")

    def test_rollback_recovery_rejects_tampered_journal_before_writing(self) -> None:
        for label, mutate in {
            "backup traversal": lambda journal, outside_hash: journal["targets"][0].update({"backup": "../outside", "sha256": outside_hash}),
            "target traversal": lambda journal, _: journal["targets"][0].update({"target": "../outside"}),
            "schema": lambda journal, _: journal.update({"unexpected": True}),
            "hash": lambda journal, _: journal["targets"][0].update({"sha256": "sha256:" + "0" * 64}),
        }.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary:
                    original_root = self.root
                    self.root = Path(temporary)
                    try:
                        deck, spec = self.write_uninitialized_pair()
                        self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 0)
                        backup = self.only_backup(deck)
                        before = (deck.read_bytes(), spec.read_bytes())
                        journal_targets = []
                        for target in (deck, spec):
                            name = f"rollback-{target.name}"
                            (backup / name).write_bytes(target.read_bytes())
                            journal_targets.append({"backup": name, "sha256": partial_regen._sha256(target.read_bytes()), "target": target.name})
                        journal = {"version": 1, "operation": "rollback", "status": "prepared", "targets": journal_targets}
                        outside = backup.parent / "outside"
                        outside_payload = b"<!doctype html><html><body>outside sentinel</body></html>"
                        outside.write_bytes(outside_payload)
                        mutate(journal, partial_regen._sha256(outside_payload))
                        (backup / "rollback-metadata.json").write_text(json.dumps(journal), encoding="utf-8")

                        self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 1)
                        self.assertEqual(deck.read_bytes(), before[0])
                        self.assertEqual(spec.read_bytes(), before[1])
                        self.assertEqual(outside.read_bytes(), outside_payload)
                    finally:
                        self.root = original_root

    def test_prepared_rollback_journal_is_selected_and_symlinked_request_is_rejected(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 0)
        backup = self.only_backup(deck)
        with mock.patch.object(partial_regen, "_replace_file", side_effect=OSError("interrupted rollback")):
            self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 1)
        self.assertEqual(partial_regen._prepared_backups(deck), [backup.resolve()])
        self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 0)

        linked = backup.parent / "linked-backup"
        try:
            os.symlink(backup, linked)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(linked)])[0], 1)

    def test_create_backup_refuses_symlinked_ancestors(self) -> None:
        for component in (".partial-regen", "backups"):
            with self.subTest(component=component):
                deck, spec = self.write_uninitialized_pair()
                outside = self.root / f"outside-{component}"
                outside.mkdir()
                parent = deck.parent / ".partial-regen"
                try:
                    if component == ".partial-regen":
                        os.symlink(outside, parent)
                    else:
                        parent.mkdir()
                        os.symlink(outside, parent / "backups")
                except OSError:
                    self.skipTest("symlinks unavailable")
                self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 1)

    def test_init_recovery_refuses_tampered_unrelated_sibling_target(self) -> None:
        deck, spec = self.write_uninitialized_pair()
        sibling = self.root / "unrelated.txt"
        sibling.write_text("do not replace", encoding="utf-8")
        real_backup = partial_regen._create_backup
        real_replace = partial_regen._replace_file

        def tampered_backup(deck_path: Path, operation: str, targets: tuple[Path, ...]) -> Path:
            backup = real_backup(deck_path, operation, targets)
            metadata = json.loads((backup / "metadata.json").read_text())
            item = metadata["targets"][1]
            payload = (backup / item["backup"]).read_bytes()
            (backup / sibling.name).write_bytes(payload)
            item["target"] = sibling.name
            item["backup"] = sibling.name
            (backup / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            return backup

        calls = 0
        def fail_first_publish(source: Path, target: Path) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("publish failure")
            real_replace(source, target)

        with mock.patch.object(partial_regen, "_create_backup", side_effect=tampered_backup), mock.patch.object(partial_regen, "_replace_file", side_effect=fail_first_publish):
            self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 1)
        self.assertEqual(sibling.read_text(encoding="utf-8"), "do not replace")

    def test_public_rollback_rejects_unrelated_and_dot_backup_targets(self) -> None:
        for bad_name in ("unrelated.txt", ".", ".."):
            with self.subTest(bad_name=bad_name):
                deck, spec = self.write_uninitialized_pair()
                sibling = self.root / "unrelated.txt"
                sibling.write_text("do not replace", encoding="utf-8")
                self.assertEqual(self.run_main(["init", "--deck", str(deck), "--spec", str(spec), "--apply"])[0], 0)
                backup = self.only_backup(deck)
                metadata = json.loads((backup / "metadata.json").read_text())
                item = metadata["targets"][1]
                payload = (backup / item["backup"]).read_bytes()
                if bad_name not in {".", ".."}:
                    (backup / bad_name).write_bytes(payload)
                item["target"] = bad_name
                item["backup"] = bad_name
                (backup / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
                self.assertEqual(self.run_main(["rollback", "--deck", str(deck), "--backup", str(backup)])[0], 1)
                self.assertEqual(sibling.read_text(encoding="utf-8"), "do not replace")


if __name__ == "__main__":
    unittest.main()
