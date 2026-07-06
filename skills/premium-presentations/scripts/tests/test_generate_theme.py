#!/usr/bin/env python3
"""Tests for generate_theme.py — AT2: block discoverable, token-complete, gate-passing.
AT3: low-contrast palette rejected, fail-closed (nothing appended)."""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import generate_theme  # noqa: E402
from _common import THEMES_CSS, discover_themes  # noqa: E402
from validate_contrast import check_palette, scan_themes_css  # noqa: E402

# The full ADR-c token set a generated block must carry (self-contained,
# no :root fallback layer — see ADR-c empirical finding).
EXPECTED_TOKENS = {
    "bg", "text", "accent", "surface", "surface2", "border", "border-bright",
    "text-dim", "accent-strong", "accent-dim", "accent2",
    "gold", "gold-dim", "orange", "orange-dim", "cyan", "cyan-dim",
    "green", "green-dim", "red", "red-dim", "blue", "violet", "violet-dim",
    "code-bg", "code-text", "progress-gradient",
    "grain-opacity", "flow-glow-alpha",
    "term-bg", "term-bar", "term-text",
    "font-display", "font-body", "font-editorial", "font-mono",
}


class BuildThemeCssTests(unittest.TestCase):
    def test_aa_palette_is_token_complete_and_gate_passing(self) -> None:
        css_block, tokens = generate_theme.build_theme_css(
            "aa-brand", "#0b1220", "#f4f6fb", "#22c55e", "#141d33"
        )
        self.assertEqual(EXPECTED_TOKENS, set(tokens))
        self.assertIn('html[data-theme="aa-brand"]', css_block)
        self.assertEqual([], check_palette(tokens))

    def test_low_contrast_palette_fails_check_palette(self) -> None:
        _, tokens = generate_theme.build_theme_css(
            "bad-brand", "#ffffff", "#cccccc", "#dddddd", "#ffffff"
        )
        errors = check_palette(tokens)
        self.assertTrue(errors)
        self.assertIn("--text on --bg", "\n".join(errors))

    def test_light_ground_uses_light_semantic_palette(self) -> None:
        _, tokens = generate_theme.build_theme_css(
            "light-brand", "#ffffff", "#1a1a1a", "#0066cc", "#f5f5f7"
        )
        self.assertEqual(tokens["blue"], "#0066cc")  # light-ground semantic constant

    def test_dark_ground_uses_dark_semantic_palette(self) -> None:
        _, tokens = generate_theme.build_theme_css(
            "dark-brand", "#08080a", "#eaedf2", "#4a9eff", "#111114"
        )
        self.assertEqual(tokens["blue"], "#60a5fa")  # dark-ground semantic constant


class SanitizeBrandIdTests(unittest.TestCase):
    def test_rejects_empty_after_sanitize(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.sanitize_brand_id("!!!")

    def test_lowercases_and_hyphenates(self) -> None:
        self.assertEqual(generate_theme.sanitize_brand_id("Acme Corp"), "acme-corp")


class ValidateHexTests(unittest.TestCase):
    def test_rejects_non_hex(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_hex("bg", "not-a-color")

    def test_accepts_three_and_six_digit_hex(self) -> None:
        self.assertEqual(generate_theme.validate_hex("bg", "#fff"), "#fff")
        self.assertEqual(generate_theme.validate_hex("bg", "#ffffff"), "#ffffff")


class ValidateFontStackTests(unittest.TestCase):
    """Codex round-2 finding 1: --font-display is copied verbatim into
    emitted CSS; a value with `;` `{` `}` newlines or comment sequences can
    terminate the declaration/block and inject CSS after the contrast gate
    has passed. validate_font_stack() is the whitelist gate for that input."""

    def test_accepts_default_and_quoted_stacks(self) -> None:
        self.assertEqual(
            generate_theme.validate_font_stack("font-display", "system-ui, sans-serif"),
            "system-ui, sans-serif",
        )
        stack = "'Helvetica Neue', Arial, sans-serif"
        self.assertEqual(generate_theme.validate_font_stack("font-display", stack), stack)

    def test_rejects_semicolon_injection(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack("font-display", "Arial; --bg: #000")

    def test_rejects_brace_escape_injection(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack(
                "font-display", "Arial'} html[data-theme=\"evil\"]{--bg:#000"
            )

    def test_rejects_newline_new_rule_injection(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack(
                "font-display", "Arial\n} html[data-theme=\"evil\"]{--bg:#000"
            )

    def test_rejects_lone_trailing_newline(self) -> None:
        # Regression: `^...+$` (not `\A...+\Z`) would let a single trailing
        # "\n" slip through, since bare `$` matches just before a final
        # newline even though the char class never consumed it.
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack("font-display", "Arial\n")

    def test_rejects_comment_sequence(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack("font-display", "Arial */ .x{color:red} /*")

    def test_rejects_backslash_escape(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack("font-display", "Arial\\2028 evil")

    def test_rejects_unbalanced_quotes(self) -> None:
        with self.assertRaises(ValueError):
            generate_theme.validate_font_stack("font-display", "Arial, 'sans-serif")


class CliIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.css_copy = Path(self.tmp.name) / "premium-themes.css"
        shutil.copy(THEMES_CSS, self.css_copy)

    def test_at2_theme_appended_and_discoverable(self) -> None:
        rc = generate_theme.main(
            [
                "brand-aa", "--bg", "#0b1220", "--text", "#f4f6fb",
                "--accent", "#22c55e", "--surface", "#141d33",
                "--css", str(self.css_copy),
            ]
        )
        self.assertEqual(rc, 0)
        themes = discover_themes(self.css_copy)
        self.assertIn("brand-aa", themes)

    def test_at3_low_contrast_rejected_fail_closed_no_append(self) -> None:
        before = self.css_copy.read_text(encoding="utf-8")
        rc = generate_theme.main(
            [
                "brand-bad", "--bg", "#ffffff", "--text", "#cccccc",
                "--accent", "#dddddd", "--surface", "#ffffff",
                "--css", str(self.css_copy),
            ]
        )
        self.assertNotEqual(rc, 0)
        after = self.css_copy.read_text(encoding="utf-8")
        self.assertEqual(before, after, "premium-themes.css must be unmodified on contrast failure")

    def test_dry_run_does_not_append(self) -> None:
        before = self.css_copy.read_text(encoding="utf-8")
        rc = generate_theme.main(
            [
                "brand-dry", "--bg", "#0b1220", "--text", "#f4f6fb",
                "--accent", "#22c55e", "--surface", "#141d33",
                "--css", str(self.css_copy), "--dry-run",
            ]
        )
        self.assertEqual(rc, 0)
        after = self.css_copy.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def _gen_args(self, brand_id: str, **overrides) -> list[str]:
        args = {
            "--bg": "#0b1220", "--text": "#f4f6fb",
            "--accent": "#22c55e", "--surface": "#141d33",
        }
        args.update(overrides)
        flat: list[str] = [brand_id]
        for k, v in args.items():
            flat += [k, v]
        return flat + ["--css", str(self.css_copy)]

    def test_duplicate_generated_name_fails_without_replace(self) -> None:
        rc1 = generate_theme.main(self._gen_args("brand-dup"))
        self.assertEqual(rc1, 0)
        after_first = self.css_copy.read_text(encoding="utf-8")

        rc2 = generate_theme.main(self._gen_args("brand-dup"))
        self.assertNotEqual(rc2, 0, "re-running with the same brand-id must fail closed")
        after_second = self.css_copy.read_text(encoding="utf-8")
        self.assertEqual(after_first, after_second, "file must be untouched on duplicate rejection")

    def test_duplicate_builtin_name_fails(self) -> None:
        existing = discover_themes(self.css_copy)
        self.assertTrue(existing, "expected at least one built-in theme to test against")
        before = self.css_copy.read_text(encoding="utf-8")

        rc = generate_theme.main(self._gen_args(existing[0]))
        self.assertNotEqual(rc, 0, "shadowing a built-in theme id must fail closed")
        after = self.css_copy.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_replace_rewrites_exactly_one_block_and_stays_gate_green(self) -> None:
        rc1 = generate_theme.main(self._gen_args("brand-replace", **{"--accent": "#22c55e"}))
        self.assertEqual(rc1, 0)
        themes_after_first = discover_themes(self.css_copy)
        self.assertEqual(themes_after_first.count("brand-replace"), 1)

        rc2 = generate_theme.main(
            self._gen_args("brand-replace", **{"--accent": "#e2b93b"}) + ["--replace"]
        )
        self.assertEqual(rc2, 0)

        themes_after_replace = discover_themes(self.css_copy)
        self.assertEqual(
            themes_after_replace.count("brand-replace"), 1,
            "replace must not leave a duplicate block behind",
        )
        css_text = self.css_copy.read_text(encoding="utf-8")
        self.assertIn("#e2b93b", css_text)

        errors = scan_themes_css(self.css_copy)
        self.assertEqual([], errors, f"contrast gate must stay green after --replace: {errors}")

    def test_duplicate_detection_catches_existing_unquoted_block(self) -> None:
        # Codex round-2 finding 2: an unquoted html[data-theme=brand] block
        # was invisible to generate_theme's own duplicate detection because
        # the shared block regex only matched quoted selectors.
        css_text = self.css_copy.read_text(encoding="utf-8")
        css_text += (
            "\nhtml[data-theme=brand-unquoted] {\n"
            "  --text: #1a1a1a;\n"
            "  --bg: #ffffff;\n"
            "  --surface: #f5f5f7;\n"
            "  --text-dim: #5c6370;\n"
            "  --accent: #0066cc;\n"
            "}\n"
        )
        self.css_copy.write_text(css_text, encoding="utf-8")
        before = self.css_copy.read_text(encoding="utf-8")

        rc = generate_theme.main(self._gen_args("brand-unquoted"))
        self.assertNotEqual(
            rc, 0, "an existing unquoted duplicate block must be detected and rejected"
        )
        after = self.css_copy.read_text(encoding="utf-8")
        self.assertEqual(before, after, "file must be untouched when the duplicate is rejected")


class FontInjectionCliTests(unittest.TestCase):
    """Codex round-2 finding 1, CLI layer: a malicious --font-display value
    must be rejected before anything reaches premium-themes.css, and the
    file must come out byte-identical (SHA-256 compare) to before the run."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.css_copy = Path(self.tmp.name) / "premium-themes.css"
        shutil.copy(THEMES_CSS, self.css_copy)

    def _sha(self) -> str:
        return hashlib.sha256(self.css_copy.read_bytes()).hexdigest()

    def _gen_args(self, brand_id: str, font_display: str) -> list[str]:
        return [
            brand_id, "--bg", "#0b1220", "--text", "#f4f6fb",
            "--accent", "#22c55e", "--surface", "#141d33",
            "--font-display", font_display,
            "--css", str(self.css_copy),
        ]

    def _assert_rejected_untouched(self, brand_id: str, font_display: str) -> None:
        before_sha = self._sha()
        rc = generate_theme.main(self._gen_args(brand_id, font_display))
        self.assertNotEqual(rc, 0, f"malicious --font-display must be rejected: {font_display!r}")
        self.assertEqual(
            before_sha, self._sha(),
            f"premium-themes.css must be byte-identical after rejecting {font_display!r}",
        )

    def test_semicolon_injection_rejected_and_file_untouched(self) -> None:
        self._assert_rejected_untouched("brand-inj-semi", "Arial; --bg: #000000")

    def test_brace_escape_injection_rejected_and_file_untouched(self) -> None:
        self._assert_rejected_untouched(
            "brand-inj-brace", 'Arial\'} html[data-theme="evil"]{--bg:#000000'
        )

    def test_newline_new_rule_injection_rejected_and_file_untouched(self) -> None:
        self._assert_rejected_untouched(
            "brand-inj-newline", 'Arial\n} html[data-theme="evil"]{--bg:#000000'
        )

    def test_benign_quoted_font_stack_still_works(self) -> None:
        rc = generate_theme.main(
            self._gen_args("brand-quoted-font", "'Helvetica Neue', Arial, sans-serif")
        )
        self.assertEqual(rc, 0)
        css_text = self.css_copy.read_text(encoding="utf-8")
        self.assertIn("--font-display: 'Helvetica Neue', Arial, sans-serif;", css_text)


if __name__ == "__main__":
    unittest.main()
