#!/usr/bin/env python3
"""Tests for bundle_deck.py — conditional-module inclusion and wants_* matchers."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent.parent
BUNDLER_PATH = ROOT / "scripts" / "bundle_deck.py"
SHARED = ROOT / "assets" / "shared"


def load_bundler():
    spec = importlib.util.spec_from_file_location("bundle_deck", BUNDLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {BUNDLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Minimal deck fixtures
# ---------------------------------------------------------------------------

_SHARED_LINK = '../../shared/'

def _make_minimal_deck(*, extra_body: str = '', extra_head: str = '') -> str:
    """A minimal two-slide deck that links to shared/ assets (not yet bundled)."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-extras.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-components.css">'
        f'{extra_head}'
        '</head><body>'
        '<div id="deck">'
        '<section class="slide slide--title"><h1>Title</h1>'
        '<aside class="notes">Notes.</aside></section>'
        '<section class="slide slide--quote"><blockquote>Quote</blockquote>'
        '<aside class="notes">Notes.</aside></section>'
        '</div>'
        f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
        f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
        f'{extra_body}'
        '</body></html>'
    )


def _deck_with_term_links() -> str:
    return _make_minimal_deck(
        extra_body=(
            '<script type="application/json" id="glossary">'
            '{"RAG":{"title":"RAG","body":"Retrieval-Augmented Generation"}}'
            '</script>'
            '<section class="slide">'
            '<button class="term-link" data-term="RAG">RAG</button>'
            '<aside class="notes">Notes.</aside></section>'
        )
    )


def _deck_without_term_links() -> str:
    # No data-term attributes, no id="glossary" — plain deck.
    return _make_minimal_deck()


def _deck_with_live_flow() -> str:
    return _make_minimal_deck(
        extra_body=(
            '<section class="slide">'
            '<div class="live-flow">flow content</div>'
            '<aside class="notes">Notes.</aside></section>'
        )
    )


def _deck_without_live_flow() -> str:
    return _make_minimal_deck()


# ---------------------------------------------------------------------------
# Helper: bundle a deck string via bundle_deck.bundle_html()
# ---------------------------------------------------------------------------

def bundle_string(bundler, html: str, html_path: Path) -> str:
    return bundler.bundle_html(html, html_path)


class BundleGlossaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (SHARED / "premium-glossary.js").is_file():
            raise unittest.SkipTest("premium-glossary.js not found — skipping")
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        # Use a real deck slot under the project root so ../../shared/ resolves
        # to the actual assets/shared/ directory.
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_deck_with_term_links_includes_glossary(self) -> None:
        bundled = self._bundle(_deck_with_term_links())
        # The inlined script block marker written by build_classic_scripts().
        self.assertIn("/* --- premium-glossary.js --- */", bundled,
                      "Deck WITH term-links should have premium-glossary.js inlined")

    def test_deck_without_term_links_excludes_glossary(self) -> None:
        bundled = self._bundle(_deck_without_term_links())
        # If the JS was wrongly bundled its inlined marker will be present.
        self.assertNotIn("/* --- premium-glossary.js --- */", bundled,
                         "Deck WITHOUT term-links must NOT have premium-glossary.js inlined "
                         "(CSS selector text must not trigger false positive)")


class BundleFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (SHARED / "premium-flow.js").is_file():
            raise unittest.SkipTest("premium-flow.js not found — skipping")
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_deck_with_live_flow_includes_flow(self) -> None:
        bundled = self._bundle(_deck_with_live_flow())
        self.assertIn("/* --- premium-flow.js --- */", bundled,
                      "Deck WITH live-flow class should have premium-flow.js inlined")

    def test_deck_without_live_flow_excludes_flow(self) -> None:
        bundled = self._bundle(_deck_without_live_flow())
        # CSS comments may mention "premium-flow.js" — check for the JS inlined marker.
        self.assertNotIn("/* --- premium-flow.js --- */", bundled,
                         "Deck WITHOUT live-flow must NOT have premium-flow.js inlined "
                         "(CSS comment text must not trigger false positive)")


class BundlePortableMetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_default_og_cover_meta_is_removed(self) -> None:
        html = _make_minimal_deck(
            extra_head='<meta property="og:image" content="og-cover.png">'
        )
        bundled = self._bundle(html)
        self.assertNotIn("og-cover.png", bundled)

    def test_rebundle_standalone_deck_does_not_duplicate_runtime_blocks(self) -> None:
        first = self._bundle(_make_minimal_deck())
        second = self.bundler.bundle_html(first, ROOT / "assets" / "decks" / "_test_bundle_tmp" / "deck.html")

        self.assertEqual(second.count("/* --- premium-controls.js --- */"), 1)
        self.assertEqual(second.count("/* --- slide-engine.js --- */"), 1)

    def test_remote_font_links_are_removed_from_old_decks(self) -> None:
        html = _make_minimal_deck(
            extra_head=(
                '<link rel="preconnect" href="https://fonts.googleapis.com">'
                '<link rel="preconnect" href="//fonts.gstatic.com" crossorigin>'
                '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=X">'
            )
        )
        bundled = self._bundle(html)

        self.assertNotIn("fonts.googleapis", bundled)
        self.assertNotIn("fonts.gstatic", bundled)

    def test_unsafe_theme_visual_overrides_are_removed_from_bundled_decks(self) -> None:
        html = _make_visual_deck().replace(
            "<html lang=\"en\">",
            '<html lang="en" data-theme-visual-editorial-hero="https://example.com/hero.webp" '
            'data-theme-fonts-editorial="//fonts.googleapis.com/css2?family=X">',
        )
        bundled = self._bundle(html)

        self.assertNotIn("https://example.com/hero.webp", bundled)
        self.assertNotIn("//fonts.googleapis.com", bundled)
        self.assertIn(_EMBED_MARKER, bundled)


class WantsMatcher_Tests(unittest.TestCase):
    """Unit tests for the wants_* predicate functions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def test_wants_glossary_on_data_term_attr(self) -> None:
        html = '<button class="term-link" data-term="RAG">RAG</button>'
        self.assertTrue(self.bundler.wants_premium_glossary(html))

    def test_wants_glossary_on_id_glossary(self) -> None:
        html = '<script type="application/json" id="glossary">{}</script>'
        self.assertTrue(self.bundler.wants_premium_glossary(html))

    def test_wants_glossary_false_on_css_class_selector(self) -> None:
        # CSS text that mentions ".term-link" must NOT trigger the matcher.
        html = '<style>.term-link { color: red; } .pp-notes-terms { } </style>'
        self.assertFalse(self.bundler.wants_premium_glossary(html))

    def test_wants_flow_on_class_attr(self) -> None:
        html = '<div class="live-flow step">content</div>'
        self.assertTrue(self.bundler.wants_premium_flow(html))

    def test_wants_flow_false_on_css_text(self) -> None:
        html = '<style>.live-flow { display: flex; }</style>'
        self.assertFalse(self.bundler.wants_premium_flow(html))

    def test_wants_journey_on_class_attr(self) -> None:
        html = '<div class="journey-stage active">Stage 1</div>'
        self.assertTrue(self.bundler.wants_premium_journey(html))

    def test_wants_journey_false_on_css_text(self) -> None:
        html = '<style>.journey-stage { font-weight: bold; }</style>'
        self.assertFalse(self.bundler.wants_premium_journey(html))

    def test_wants_follow_on_html_data_follow_attr(self) -> None:
        html = '<!doctype html><html lang="en" data-follow><body></body></html>'
        self.assertTrue(self.bundler.wants_follow(html))

    def test_wants_follow_false_without_attribute(self) -> None:
        html = '<!doctype html><html lang="en"><body>data-follow mentioned in text</body></html>'
        self.assertFalse(self.bundler.wants_follow(html))

    def test_wants_follow_false_on_css_text_mentioning_data_follow(self) -> None:
        # A CSS attribute-selector string must not trigger the matcher — the
        # attribute must be on the actual <html> tag, not anywhere in the doc.
        html = '<!doctype html><html lang="en"><style>[data-follow] { color: red; }</style></html>'
        self.assertFalse(self.bundler.wants_follow(html))


class BundleFollowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (SHARED / "premium-follow.js").is_file():
            raise unittest.SkipTest("premium-follow.js not found — skipping")
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_deck_with_data_follow_includes_follow_module(self) -> None:
        html = _make_minimal_deck().replace(
            '<html lang="en">', '<html lang="en" data-follow>'
        )
        bundled = self._bundle(html)
        self.assertIn("/* --- premium-follow.js --- */", bundled,
                      "Deck WITH data-follow should have premium-follow.js inlined")

    def test_plain_deck_excludes_follow_module(self) -> None:
        bundled = self._bundle(_make_minimal_deck())
        self.assertNotIn("/* --- premium-follow.js --- */", bundled,
                         "Deck WITHOUT data-follow must NOT have premium-follow.js inlined")


_THEME_VISUALS_DIR = SHARED / "assets" / "theme-visuals"
_MANIFEST_PATH = _THEME_VISUALS_DIR / "manifest.json"
_EMBED_MARKER = "/* --- theme-visuals-embed --- */"
_CONTROLS_MARKER = "/* --- premium-controls.js --- */"


def _make_visual_deck(*, class_attr: str = '"slide slide--title"', tag: str = "section") -> str:
    """Minimal deck with a visual slide using the given class attribute markup."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-extras.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-components.css">'
        '</head><body>'
        '<div id="deck">'
        f'<{tag} class={class_attr}><h1>Title</h1>'
        '<aside class="notes">Notes.</aside>'
        f'</{tag}>'
        '<section class="slide slide--quote"><blockquote>Q</blockquote>'
        '<aside class="notes">Notes.</aside></section>'
        '</div>'
        f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
        f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
        '</body></html>'
    )


def _make_no_visual_deck() -> str:
    """Minimal deck with NO slide--title or slide--divider slides."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-extras.css">'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-components.css">'
        '</head><body>'
        '<div id="deck">'
        '<section class="slide slide--quote"><blockquote>Q</blockquote>'
        '<aside class="notes">Notes.</aside></section>'
        '<section class="slide slide--content"><p>Content</p>'
        '<aside class="notes">Notes.</aside></section>'
        '</div>'
        f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
        f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
        '</body></html>'
    )


def _make_css_only_visual_deck() -> str:
    """Deck where slide--title appears ONLY inside a <style> CSS selector, never in markup."""
    return (
        '<!DOCTYPE html><html lang="en"><head>'
        f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
        '</head><body>'
        '<style>'
        '.slide--title { background: blue; } '
        '.slide--divider .title { font-size: 2em; }'
        '</style>'
        '<div id="deck">'
        '<section class="slide slide--quote"><blockquote>Q</blockquote>'
        '<aside class="notes">Notes.</aside></section>'
        '</div>'
        f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
        f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
        '</body></html>'
    )


class BundleThemeVisualsEmbedTests(unittest.TestCase):
    """Tests for theme-visuals embed block injection (PLAN.md Approach §2 + §6)."""

    @classmethod
    def setUpClass(cls) -> None:
        if not _MANIFEST_PATH.is_file():
            raise unittest.SkipTest("theme-visuals manifest.json not found — skipping")
        if not (SHARED / "premium-controls.js").is_file():
            raise unittest.SkipTest("premium-controls.js not found — skipping")
        cls.bundler = load_bundler()
        with open(_MANIFEST_PATH, encoding="utf-8") as fh:
            cls.manifest = json.load(fh)

    def _bundle(self, html: str) -> str:
        """Bundle an HTML string via bundle_html(), using a real deck slot so ../../shared/ resolves."""
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def _bundle_via_cli(self, html: str, extra_args: list[str] | None = None) -> tuple[str, int]:
        """Write html to a temp file and invoke bundle_deck.py via subprocess.
        Returns (bundled_html, returncode).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Replicate the repo layout so ../../shared/ resolves correctly:
            # tmpdir/assets/decks/_cli_test_tmp/deck.html  →  ../../shared/ = tmpdir/assets/shared/
            deck_dir = Path(tmpdir) / "assets" / "decks" / "_cli_test_tmp"
            deck_dir.mkdir(parents=True)
            shared_link = Path(tmpdir) / "assets" / "shared"
            # Symlink shared/ so the bundler can read real JS/CSS assets.
            shared_link.symlink_to(SHARED.resolve())
            html_path = deck_dir / "deck.html"
            html_path.write_text(html, encoding="utf-8")
            out_path = deck_dir / "deck.standalone.html"
            cmd = [
                sys.executable,
                str(BUNDLER_PATH),
                str(html_path),
                "-o", str(out_path),
            ]
            if extra_args:
                cmd.extend(extra_args)
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and out_path.is_file():
                bundled = out_path.read_text(encoding="utf-8")
            else:
                bundled = result.stdout + result.stderr
            return bundled, result.returncode

    # ------------------------------------------------------------------
    # Test 1: inlined premium-controls.js rejects remote theme visual URLs
    # ------------------------------------------------------------------

    def test_controls_js_rejects_remote_theme_visual_urls(self) -> None:
        """Bundled output's inlined premium-controls.js must not bless remote
        theme visual overrides."""
        bundled = self._bundle(_make_visual_deck())
        self.assertIn("function safeThemeVisualValue", bundled)
        self.assertNotIn("(?:https?:|data:|blob:|file:", bundled)

    # ------------------------------------------------------------------
    # Test 2: embed block present with all themes × roles from manifest
    # ------------------------------------------------------------------

    def test_embed_block_present_with_all_manifest_themes_and_roles(self) -> None:
        """Bundled visual deck contains embed block; every manifest theme/role has a
        valid data:image/webp;base64, URI in the block (PLAN §6 item 2)."""
        bundled = self._bundle(_make_visual_deck())
        self.assertIn(_EMBED_MARKER, bundled,
                      "Bundled visual deck must contain the theme-visuals embed marker")
        # Extract the embed script block for targeted assertions.
        start = bundled.find(_EMBED_MARKER)
        # Find the closing tag of the embed <script> block.
        end = bundled.find("</script>", start)
        embed_block = bundled[start:end]
        for theme, theme_data in self.manifest.items():
            for asset in theme_data["assets"]:
                role = asset["role"]
                # Each theme→role combo must be represented as a data: URI.
                self.assertIn(
                    "data:image/webp;base64,",
                    embed_block,
                    f"Embed block must contain a data:image/webp;base64, URI "
                    f"(missing for theme={theme!r} role={role!r})",
                )
                # Verify the theme key appears in the embed block (as a JSON string key).
                self.assertIn(
                    f'"{theme}"',
                    embed_block,
                    f"Embed block must contain theme key {theme!r}",
                )

    def test_manifest_has_exactly_four_themes(self) -> None:
        """Manifest declares exactly 4 themes — conscious gate so new themes fail loudly."""
        self.assertEqual(
            len(self.manifest),
            4,
            f"Expected exactly 4 themes in manifest.json, got {len(self.manifest)}: "
            f"{list(self.manifest.keys())}. Update this test if adding a new theme.",
        )

    # ------------------------------------------------------------------
    # Test 3: --no-embed-visuals skips the embed block
    # ------------------------------------------------------------------

    def test_no_embed_visuals_flag_omits_block(self) -> None:
        """--no-embed-visuals CLI flag produces output with no embed marker (PLAN §6 item 3)."""
        bundled, rc = self._bundle_via_cli(_make_visual_deck(), extra_args=["--no-embed-visuals"])
        self.assertEqual(rc, 0, f"Bundler exited non-zero with --no-embed-visuals: {bundled}")
        self.assertNotIn(_EMBED_MARKER, bundled,
                         "--no-embed-visuals must omit the theme-visuals-embed block")

    # ------------------------------------------------------------------
    # Test 4: re-bundle idempotent — exactly one embed block
    # ------------------------------------------------------------------

    def test_rebundle_produces_exactly_one_embed_block(self) -> None:
        """Running bundler twice (--force) on a visual deck yields exactly one embed marker (PLAN §6 item 4)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deck_dir = Path(tmpdir) / "assets" / "decks" / "_rebundle_test_tmp"
            deck_dir.mkdir(parents=True)
            shared_link = Path(tmpdir) / "assets" / "shared"
            shared_link.symlink_to(SHARED.resolve())
            html_path = deck_dir / "deck.html"
            html_path.write_text(_make_visual_deck(), encoding="utf-8")

            # First bundle — output in-place.
            r1 = subprocess.run(
                [sys.executable, str(BUNDLER_PATH), str(html_path), "--in-place"],
                capture_output=True, text=True,
            )
            self.assertEqual(r1.returncode, 0,
                             f"First bundle failed: {r1.stdout}{r1.stderr}")

            # Second bundle with --force to re-process the already-standalone file.
            r2 = subprocess.run(
                [sys.executable, str(BUNDLER_PATH), str(html_path), "--in-place", "--force"],
                capture_output=True, text=True,
            )
            self.assertEqual(r2.returncode, 0,
                             f"Second bundle (--force) failed: {r2.stdout}{r2.stderr}")

            twice_bundled = html_path.read_text(encoding="utf-8")
            count = twice_bundled.count(_EMBED_MARKER)
            self.assertEqual(count, 1,
                             f"Expected exactly 1 embed marker after re-bundle, found {count}")

    # ------------------------------------------------------------------
    # Test 5: no slide--title / slide--divider → no embed block
    # ------------------------------------------------------------------

    def test_no_visual_slides_produces_no_embed_block(self) -> None:
        """Deck without slide--title or slide--divider gets no embed block (PLAN §6 item 5)."""
        bundled = self._bundle(_make_no_visual_deck())
        self.assertNotIn(_EMBED_MARKER, bundled,
                         "Deck with no visual slides must NOT contain the theme-visuals-embed block")

    # ------------------------------------------------------------------
    # Test 6: slide--title only in CSS selector text → no embed block
    # ------------------------------------------------------------------

    def test_css_only_slide_class_does_not_trigger_embed(self) -> None:
        """Deck whose only slide--title occurrences are in CSS selectors (not markup)
        must NOT get an embed block (PLAN §6 item 6 / Approach §2 detection rule)."""
        bundled = self._bundle(_make_css_only_visual_deck())
        self.assertNotIn(_EMBED_MARKER, bundled,
                         "CSS selector text '.slide--title' must not trigger embed; "
                         "detection must be quote-bounded class attribute match only")

    # ------------------------------------------------------------------
    # Test 7: single-quoted class attribute → embed block present
    # ------------------------------------------------------------------

    def test_single_quoted_class_attr_triggers_embed(self) -> None:
        """Single-quoted class='slide slide--title' markup must trigger embed (PLAN §6 item 7)."""
        # Build a deck with single-quoted class attribute.
        deck_html = _make_visual_deck(class_attr="'slide slide--title'")
        bundled = self._bundle(deck_html)
        self.assertIn(_EMBED_MARKER, bundled,
                      "Single-quoted class='slide slide--title' must trigger theme-visuals embed")

    # ------------------------------------------------------------------
    # Test 8: non-class attribute containing slide--title → no embed block
    # ------------------------------------------------------------------

    def test_non_class_attribute_does_not_trigger_embed(self) -> None:
        """data-x=\"slide--title\" (slide--title in a non-class attribute) must NOT trigger
        embed (PLAN §6 item 8 / Approach §2 detection rule)."""
        deck_html = _make_visual_deck(class_attr='"slide slide--quote" data-x="slide--title"',
                                      tag="section")
        # The section has class "slide slide--quote" (no visual class) but data-x="slide--title".
        # Replace with a deck where slide--title appears only in data-x, not class.
        no_title_class_html = (
            '<!DOCTYPE html><html lang="en"><head>'
            f'<link rel="stylesheet" href="{_SHARED_LINK}premium-themes.css">'
            f'<link rel="stylesheet" href="{_SHARED_LINK}premium-extras.css">'
            f'<link rel="stylesheet" href="{_SHARED_LINK}premium-components.css">'
            '</head><body>'
            '<div id="deck">'
            '<section class="slide slide--quote" data-x="slide--title"><h1>Title</h1>'
            '<aside class="notes">Notes.</aside></section>'
            '<section class="slide slide--content"><p>Content</p>'
            '<aside class="notes">Notes.</aside></section>'
            '</div>'
            f'<script src="{_SHARED_LINK}slide-engine.js"></script>'
            f'<script src="{_SHARED_LINK}premium-controls.js"></script>'
            '</body></html>'
        )
        bundled = self._bundle(no_title_class_html)
        self.assertNotIn(_EMBED_MARKER, bundled,
                         "data-x='slide--title' (non-class attribute) must NOT trigger embed; "
                         "detection must be restricted to class attribute values only")

    # ------------------------------------------------------------------
    # Test 9: missing manifest-listed asset → bundler fails non-zero / raises
    # ------------------------------------------------------------------

    def test_missing_manifest_asset_causes_bundle_failure(self) -> None:
        """If a manifest-listed .webp asset is absent, the bundler must fail
        (non-zero exit or raised exception) (PLAN §6 item 9 / Approach §2 fail-hard rule)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create a minimal repo layout:
            #   tmp/assets/decks/_miss_asset_test/deck.html
            #   tmp/assets/shared/ → symlink to real SHARED
            # Then inject a fake theme-visuals dir with a manifest that references
            # a nonexistent file, and patch the bundler's SHARED to point here.
            fake_shared = tmp_path / "fake_shared"
            fake_shared.mkdir()
            # Copy real shared content so the bundler can load CSS/JS assets.
            for item in SHARED.iterdir():
                if item.is_file():
                    shutil.copy2(item, fake_shared / item.name)
                elif item.is_dir() and item.name != "assets":
                    shutil.copytree(item, fake_shared / item.name)
            # Set up fake theme-visuals with a manifest listing a nonexistent file.
            fake_tv_dir = fake_shared / "assets" / "theme-visuals"
            fake_tv_dir.mkdir(parents=True)
            broken_manifest = {
                "editorial": {
                    "assets": [
                        {"role": "hero", "src": "editorial-hero-MISSING.webp"},
                        {"role": "map",  "src": "editorial-map-MISSING.webp"},
                    ]
                }
            }
            (fake_tv_dir / "manifest.json").write_text(
                json.dumps(broken_manifest), encoding="utf-8"
            )
            # Do NOT copy the .webp files — they remain absent.

            # Deck directory under fake_shared's parent so ../../shared/ → fake_shared.
            deck_dir = tmp_path / "assets" / "decks" / "_miss_asset_test_tmp"
            deck_dir.mkdir(parents=True)
            (tmp_path / "assets" / "shared").symlink_to(fake_shared.resolve())

            html_path = deck_dir / "deck.html"
            html_path.write_text(_make_visual_deck(), encoding="utf-8")

            # Test via subprocess using the real bundler entry point,
            # patching ROOT/SHARED inside the bundler module via monkeypatching the
            # module-level SHARED and ROOT in bundle_deck.bundle_html.
            # Since subprocess isolation is cleanest, we call via Python -c with patch.
            patch_script = f"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, {str(BUNDLER_PATH.parent)!r})
import bundle_deck, _common

fake_shared = Path({str(fake_shared)!r})
html_path = Path({str(html_path)!r})
html = html_path.read_text(encoding='utf-8')

with patch.object(_common, 'SHARED', fake_shared), \\
     patch.object(bundle_deck, 'SHARED', fake_shared):
    try:
        bundle_deck.bundle_html(html, html_path)
        sys.exit(0)
    except Exception as exc:
        print(f'RAISED: {{exc}}', file=sys.stderr)
        sys.exit(1)
"""
            result = subprocess.run(
                [sys.executable, "-c", patch_script],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "Bundler must fail (non-zero exit or raised error) when a manifest-listed "
                f"asset file is missing. stdout={result.stdout!r} stderr={result.stderr!r}",
            )

    # ------------------------------------------------------------------
    # Test 10: embed block appears BEFORE premium-controls.js inlined block
    # ------------------------------------------------------------------

    def test_embed_block_precedes_inlined_controls_js(self) -> None:
        """Embed block marker must appear before the inlined premium-controls.js
        marker in the bundled output (PLAN §6 item 10 / Approach §2 injection order)."""
        bundled = self._bundle(_make_visual_deck())
        self.assertIn(_EMBED_MARKER, bundled,
                      "Bundled visual deck must contain the theme-visuals-embed block")
        self.assertIn(_CONTROLS_MARKER, bundled,
                      "Bundled deck must contain the inlined premium-controls.js block")
        embed_idx = bundled.index(_EMBED_MARKER)
        controls_idx = bundled.index(_CONTROLS_MARKER)
        self.assertLess(
            embed_idx,
            controls_idx,
            f"theme-visuals-embed block (pos {embed_idx}) must appear BEFORE "
            f"the inlined premium-controls.js block (pos {controls_idx})",
        )


class BundleStandaloneRetrofitTests(unittest.TestCase):
    """A standalone deck bundled before a REQUIRED_CSS/REQUIRED_JS entry existed
    must be retrofit with exactly the missing modules on a plain re-bundle
    (no --force) — never silently skipped, never duplicated."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def _bundle(self, html: str) -> str:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        path = deck_dir / "deck.html"
        try:
            path.write_text(html, encoding="utf-8")
            return bundle_string(self.bundler, html, path)
        finally:
            path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

    def test_missing_required_module_is_retrofit_exactly_once(self) -> None:
        fully_bundled = self._bundle(_make_minimal_deck())
        stale = fully_bundled.replace(
            "/* --- premium-design-power.js --- */",
            "/* --- premium-design-power.js --- REMOVED FOR TEST --- */",
        )
        # Sanity: the marker regex used by has_script_module() must no longer match.
        self.assertNotIn("/* --- premium-design-power.js --- */", stale)

        retrofit = self.bundler.bundle_html(stale, ROOT / "assets" / "decks" / "_test_bundle_tmp" / "deck.html")

        self.assertEqual(
            retrofit.count("/* --- premium-design-power.js --- */"), 1,
            "Missing required module must be injected exactly once on plain re-bundle",
        )
        for name in self.bundler.REQUIRED_JS:
            self.assertEqual(
                retrofit.count(f"/* --- {name} --- */"), 1,
                f"{name} must appear exactly once after retrofit (no duplication)",
            )

    def test_already_complete_standalone_deck_is_unchanged(self) -> None:
        fully_bundled = self._bundle(_make_minimal_deck())
        retrofit = self.bundler.bundle_html(
            fully_bundled, ROOT / "assets" / "decks" / "_test_bundle_tmp" / "deck.html"
        )
        self.assertEqual(retrofit, fully_bundled)


class EscapeForHtmlStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundler = load_bundler()

    def test_style_close_tag_is_neutralized(self) -> None:
        malicious = "body{color:red}/* </style><script>alert(1)</script> */"
        escaped = self.bundler.escape_for_html_style(malicious)
        self.assertNotIn("</style", escaped)

    def test_case_insensitive(self) -> None:
        escaped = self.bundler.escape_for_html_style("</STYLE>")
        self.assertNotIn("</style", escaped.lower())


class BundleExternalWorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def test_explicit_shared_root_wins_over_project_local_shared_asset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deck = root / "project" / "assets" / "decks" / "talk" / "deck.html"
            deck.parent.mkdir(parents=True)
            local_shared = root / "project" / "assets" / "shared"
            local_shared.mkdir(parents=True)
            framework_shared = root / "framework" / "shared"
            framework_shared.mkdir(parents=True)
            (local_shared / "premium-themes.css").write_text("local", encoding="utf-8")
            (framework_shared / "premium-themes.css").write_text(
                "framework", encoding="utf-8"
            )

            resolved = self.bundler.resolve_asset(
                deck,
                "../../shared/premium-themes.css",
                shared_root=framework_shared,
            )

            self.assertEqual(resolved, (framework_shared / "premium-themes.css").resolve())

    def test_shared_asset_traversal_outside_explicit_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deck = root / "project" / "assets" / "decks" / "talk" / "deck.html"
            deck.parent.mkdir(parents=True)
            framework_shared = root / "framework" / "shared"
            framework_shared.mkdir(parents=True)
            secret = root / "framework" / "secret.css"
            secret.write_text("must not be read", encoding="utf-8")

            self.assertIsNone(
                self.bundler.resolve_asset(
                    deck,
                    "../../shared/../../secret.css",
                    shared_root=framework_shared,
                )
            )

    def test_noncanonical_shared_path_is_ignored_with_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deck = root / "project" / "assets" / "decks" / "talk" / "deck.html"
            deck.parent.mkdir(parents=True)
            framework_shared = root / "framework" / "shared"
            framework_shared.mkdir(parents=True)
            # This is where the deck-relative candidate would land if the
            # explicit-root guard accidentally fell through to legacy logic.
            local_secret = deck.parent / "secret.css"
            local_secret.write_text("must not be inlined", encoding="utf-8")
            href = "attacker/shared/../../secret.css"

            self.assertIsNone(
                self.bundler.resolve_asset(deck, href, shared_root=framework_shared)
            )
            html = f'<link rel="stylesheet" href="{href}">'
            self.assertEqual(
                self.bundler.inline_stylesheets(
                    html, deck, shared_root=framework_shared
                ),
                html,
            )

    def test_external_deck_uses_explicit_shared_root_and_themes_css(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "framework" / "shared"
            shutil.copytree(SHARED, shared)
            custom_css = root / "workspace" / "themes.css"
            custom_css.parent.mkdir(parents=True)
            custom_css.write_text(
                (SHARED / "premium-themes.css").read_text(encoding="utf-8")
                + "\n/* workspace-theme-registry */\n",
                encoding="utf-8",
            )
            deck = root / "workspace" / "deck.html"
            deck.write_text(_make_minimal_deck(), encoding="utf-8")
            output = root / "workspace" / "deck.standalone.html"

            result = subprocess.run(
                [
                    sys.executable,
                    str(BUNDLER_PATH),
                    str(deck),
                    "--shared-root",
                    str(shared),
                    "--themes-css",
                    str(custom_css),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            bundled = output.read_text(encoding="utf-8")
            self.assertIn("workspace-theme-registry", bundled)
            self.assertIn("/* --- premium-themes.css --- */", bundled)
            self.assertEqual(bundled.count("/* --- premium-themes.css --- */"), 1)
            self.assertNotIn('../../shared/premium-themes.css', bundled)


class BundleStylesheetHrefNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundler = load_bundler()

    def _query_hash_deck(self) -> str:
        return _make_minimal_deck().replace(
            f'{_SHARED_LINK}premium-themes.css',
            f'{_SHARED_LINK}premium-themes.css?v=1#canonical',
        )

    def test_query_hash_shared_stylesheet_without_explicit_root_inlines_once(self) -> None:
        deck_dir = ROOT / "assets" / "decks" / "_test_bundle_tmp"
        deck_dir.mkdir(parents=True, exist_ok=True)
        html_path = deck_dir / "deck.html"
        try:
            html = self._query_hash_deck()
            html_path.write_text(html, encoding="utf-8")
            bundled = self.bundler.bundle_html(html, html_path)
        finally:
            html_path.unlink(missing_ok=True)
            try:
                deck_dir.rmdir()
            except OSError:
                pass

        self.assertEqual(bundled.count("/* --- premium-themes.css --- */"), 1)
        self.assertNotIn("premium-themes.css?v=1#canonical", bundled)

    def test_query_hash_shared_stylesheet_with_explicit_root_and_custom_registry_inlines_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = root / "framework" / "shared"
            shutil.copytree(SHARED, shared)
            custom_css = root / "workspace" / "themes.css"
            custom_css.parent.mkdir(parents=True)
            custom_css.write_text("custom-theme-registry", encoding="utf-8")
            deck = root / "workspace" / "deck.html"
            html = self._query_hash_deck()
            deck.write_text(html, encoding="utf-8")

            bundled = self.bundler.bundle_html(
                html,
                deck,
                shared_root=shared,
                themes_css=custom_css,
            )

            self.assertEqual(bundled.count("/* --- premium-themes.css --- */"), 1)
            self.assertIn("custom-theme-registry", bundled)
            self.assertNotIn("premium-themes.css?v=1#canonical", bundled)


if __name__ == "__main__":
    unittest.main()
