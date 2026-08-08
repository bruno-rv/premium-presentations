#!/usr/bin/env python3
"""Focused regression tests for the batched Playwright layout sweep."""
from __future__ import annotations

import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import validate_layout  # noqa: E402


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class _FakePage:
    def __init__(self, slide_count: int, mermaid_count: int = 0) -> None:
        self.slide_count = slide_count
        self.mermaid_count = mermaid_count
        self.evaluate_calls: list[tuple[str, object | None]] = []
        self.viewport_calls: list[dict[str, int]] = []
        self.wait_for_function_calls: list[str] = []

    def goto(self, *_args: object, **_kwargs: object) -> None:
        return None

    def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self.viewport_calls.append(viewport)

    def wait_for_timeout(self, *_args: object) -> None:
        raise AssertionError("layout validation must not use fixed timeouts")

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self.mermaid_count)

    def wait_for_function(self, script: str, timeout: int | None = None) -> None:
        self.wait_for_function_calls.append(script)
        return None

    def evaluate(self, script: str, argument: object | None = None) -> object:
        self.evaluate_calls.append((script, argument))
        return {
            "dividerIssues": [
                {
                    "slide": 1,
                    "navTitle": "Act II",
                    "problem": "ghost number clipped: right",
                }
            ],
            "slideOverlaps": [
                {
                    "slide": index,
                    "navTitle": "Intro" if index == 1 else "",
                    "issues": (
                        [{"a": ".slide__body", "b": ".stats-row", "ratio": 25}]
                        if index == 1
                        else []
                    ),
                }
                for index in range(1, self.slide_count + 1)
            ],
        }


class _FakeBrowser:
    def __init__(self, page: _FakePage) -> None:
        self.page = page

    def new_page(self) -> _FakePage:
        return self.page

    def close(self) -> None:
        return None


class _FakeSyncPlaywright:
    def __init__(self, page: _FakePage) -> None:
        self.playwright = types.SimpleNamespace(
            chromium=types.SimpleNamespace(
                launch=lambda **_kwargs: _FakeBrowser(page)
            )
        )

    def __enter__(self) -> object:
        return self.playwright

    def __exit__(self, *_args: object) -> None:
        return None


def _run_sweep(
    slide_count: int,
    *,
    html: str | None = None,
    single_theme: bool = False,
    mermaid_count: int = 0,
    themes: list[str] | None = None,
) -> tuple[_FakePage, list[str], list[str]]:
    page = _FakePage(slide_count, mermaid_count=mermaid_count)
    playwright = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _FakeSyncPlaywright(page)  # type: ignore[attr-defined]
    playwright.sync_api = sync_api  # type: ignore[attr-defined]

    with mock.patch.dict(
        sys.modules,
        {"playwright": playwright, "playwright.sync_api": sync_api},
    ), mock.patch.object(
        validate_layout,
        "discover_themes",
        return_value=themes if themes is not None else ["red", "warm"],
    ):
        errors, warnings = validate_layout._playwright_check(
            Path("deck.html"), single_theme=single_theme, html=html
        )
    return page, errors, warnings


class BatchedLayoutSweepTests(unittest.TestCase):
    def test_sweep_has_no_fixed_timeout_calls(self) -> None:
        self.assertNotIn(
            "wait_for_timeout", inspect.getsource(validate_layout._playwright_check)
        )
        _run_sweep(slide_count=2)

    def test_evaluate_call_count_does_not_grow_with_slides(self) -> None:
        small_page, _, _ = _run_sweep(slide_count=1)
        large_page, _, _ = _run_sweep(slide_count=100)

        expected_calls = 2 * 3  # themes * viewports
        self.assertEqual(len(small_page.evaluate_calls), expected_calls)
        self.assertEqual(len(large_page.evaluate_calls), expected_calls)
        self.assertEqual(len(large_page.viewport_calls), 2 * 3)

    def test_first_snapshot_carries_theme_readiness_without_a_separate_rpc(self) -> None:
        themes = ["red", "warm", "ink", "sage"]
        page, _, _ = _run_sweep(slide_count=1, themes=themes)

        snapshot_configs = [
            argument
            for script, argument in page.evaluate_calls
            if script == validate_layout.LAYOUT_SNAPSHOT_JS
        ]
        self.assertEqual(len(page.evaluate_calls), 12)
        self.assertEqual(
            [script for script, _ in page.evaluate_calls],
            [validate_layout.LAYOUT_SNAPSHOT_JS] * 12,
        )
        self.assertTrue(all(isinstance(config, dict) for config in snapshot_configs))
        self.assertEqual(
            [
                config.get("theme")
                for config in snapshot_configs
                if isinstance(config, dict)
            ],
            ["red", None, None, "warm", None, None, "ink", None, None, "sage", None, None],
        )

    def test_batched_findings_keep_existing_message_format(self) -> None:
        _, errors, warnings = _run_sweep(slide_count=2)

        self.assertEqual(len(errors), 2 * 3)
        self.assertEqual(len(set(errors)), 2 * 3)
        self.assertEqual(
            errors,
            [
                f"[{theme} {width}x{height}] Act II: ghost number clipped: right"
                for theme in ("red", "warm")
                for width, height in ((1280, 720), (1440, 900), (1920, 1080))
            ],
        )
        self.assertEqual(len(warnings), 2 * 3)
        self.assertEqual(len(set(warnings)), 2 * 3)
        self.assertEqual(
            warnings,
            [
                f"[{theme} {width}x{height}] Intro: "
                "overlap .slide__body ∩ .stats-row (~25%)"
                for theme in ("red", "warm")
                for width, height in ((1280, 720), (1440, 900), (1920, 1080))
            ],
        )

    def test_default_sweeps_all_themes(self) -> None:
        # Default contract: full sweep over every theme in the registry, even
        # when the deck declares one — the deck embeds the full registry for
        # live theme switching, so a break under any theme is a real bug.
        page, _, _ = _run_sweep(
            slide_count=2, html='<html lang="en" data-theme="warm">'
        )
        self.assertEqual(len(page.evaluate_calls), 2 * 3)
        self.assertEqual(len(page.viewport_calls), 2 * 3)

    def test_single_theme_limits_sweep_to_declared_theme(self) -> None:
        page, _, _ = _run_sweep(
            slide_count=2,
            html='<html lang="en" data-theme="warm">',
            single_theme=True,
        )
        # themes * viewports with themes narrowed to ["warm"].
        self.assertEqual(len(page.evaluate_calls), 1 * 3)
        self.assertEqual(len(page.viewport_calls), 1 * 3)

    def test_single_theme_without_declared_theme_falls_back_to_full_sweep(self) -> None:
        page, _, _ = _run_sweep(
            slide_count=2, html="<html lang=\"en\">", single_theme=True
        )
        self.assertEqual(len(page.evaluate_calls), 2 * 3)

    def test_single_theme_validates_theme_outside_registry(self) -> None:
        # F8: a workspace-owned theme (generate_theme.py) is inlined into the
        # deck but absent from the framework registry. --single-theme must
        # still measure the deck under its authored theme, not fall back to
        # the built-in registry and skip the theme it ships with.
        page, _, _ = _run_sweep(
            slide_count=2,
            html='<html lang="en" data-theme="brand-x">',
            single_theme=True,
        )
        self.assertEqual(len(page.evaluate_calls), 1 * 3)
        self.assertEqual(len(page.viewport_calls), 1 * 3)

    def test_mermaid_gate_waits_for_svg_when_diagrams_present(self) -> None:
        page, _, _ = _run_sweep(slide_count=2, mermaid_count=1)
        self.assertEqual(len(page.wait_for_function_calls), 1)
        self.assertIn("querySelector('svg')", page.wait_for_function_calls[0])

    def test_no_mermaid_gate_without_diagrams(self) -> None:
        page, _, _ = _run_sweep(slide_count=2, mermaid_count=0)
        self.assertEqual(len(page.wait_for_function_calls), 0)


class LayoutGateFailClosedTests(unittest.TestCase):
    def test_sweep_defect_fails_gate_as_error(self) -> None:
        # F1: a defect inside the sweep (not an environment issue) must surface
        # as an error, never a warning — a silently skipped layout check would
        # report DECK HEALTHY on a broken deck.
        with mock.patch.object(
            validate_layout,
            "_playwright_check",
            side_effect=RuntimeError("boom"),
        ):
            errors, warnings = validate_layout.validate_deck_layout(
                "<html></html>", "<html></html>", Path("deck.html")
            )
        self.assertTrue(any("Layout pixel checks failed" in e for e in errors))
        self.assertFalse(any("Layout pixel checks failed" in w for w in warnings))


class LayoutSnapshotBrowserTests(unittest.TestCase):
    def test_theme_snapshot_waits_for_fonts_and_two_frames_before_measuring(self) -> None:
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            self.skipTest("playwright is not installed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Error as exc:
                self.skipTest(f"chromium is unavailable: {exc}")

            try:
                page = browser.new_page(viewport={"width": 800, "height": 600})
                page.set_content(
                    """
                    <style>
                      .slide { height: 200px; position: relative; width: 300px; }
                      .slide__body, .stats-row {
                        height: 80px;
                        left: 20px;
                        position: absolute;
                        width: 120px;
                      }
                      .slide__body { top: 60px; }
                      .stats-row { top: 160px; }
                    </style>
                    <section class="slide">
                      <div class="slide__body">Body</div>
                      <div class="stats-row">Stats</div>
                    </section>
                    """
                )
                page.evaluate(
                    """
                    () => {
                      const nativeRequestAnimationFrame = window.requestAnimationFrame.bind(window);
                      window.__layoutReadiness = {
                        fontTheme: null,
                        frameCount: 0,
                        frameThemes: [],
                      };
                      Object.defineProperty(document, 'fonts', {
                        configurable: true,
                        value: {
                          ready: {
                            then(resolve) {
                              window.__layoutReadiness.fontTheme =
                                document.documentElement.dataset.theme || null;
                              resolve();
                            },
                          },
                        },
                      });
                      window.requestAnimationFrame = (callback) =>
                        nativeRequestAnimationFrame((timestamp) => {
                          window.__layoutReadiness.frameCount += 1;
                          window.__layoutReadiness.frameThemes.push(
                            document.documentElement.dataset.theme || null
                          );
                          if (window.__layoutReadiness.frameCount === 2) {
                            document.querySelector('.stats-row').style.top = '60px';
                          }
                          callback(timestamp);
                        });
                    }
                    """
                )
                snapshot = page.evaluate(
                    validate_layout.LAYOUT_SNAPSHOT_JS,
                    {
                        "theme": "warm",
                        "selectors": list(validate_layout.OVERLAP_SELECTORS),
                        "tolerance": validate_layout.CLIP_TOLERANCE_PX,
                        "ratioMin": validate_layout.OVERLAP_RATIO_WARN,
                    },
                )
                readiness = page.evaluate("() => window.__layoutReadiness")
            finally:
                browser.close()

        self.assertEqual(readiness["fontTheme"], "warm")
        self.assertEqual(readiness["frameThemes"], ["warm", "warm"])
        self.assertEqual(readiness["frameCount"], 2)
        self.assertIn(
            {"a": ".slide__body", "b": ".stats-row", "ratio": 100},
            snapshot["slideOverlaps"][0]["issues"],
        )

    def test_snapshot_finds_layout_issues_and_restores_slide_state(self) -> None:
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError:
            self.skipTest("playwright is not installed")

        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except Error as exc:
                self.skipTest(f"chromium is unavailable: {exc}")

            try:
                page = browser.new_page(viewport={"width": 800, "height": 600})
                page.set_content(
                    """
                    <style>
                      @keyframes pulse { from { filter: none; } to { filter: blur(1px); } }
                      .slide {
                        animation: pulse 10s infinite;
                        height: 200px;
                        opacity: 0;
                        position: relative;
                        transform: translateY(36px);
                        transition: opacity 5s, transform 5s;
                        width: 300px;
                      }
                      .slide.visible { opacity: 1; transform: none; }
                      .slide__number {
                        height: 30px;
                        left: 280px;
                        position: absolute;
                        top: 10px;
                        width: 60px;
                      }
                      .slide__body, .stats-row {
                        height: 80px;
                        left: 20px;
                        position: absolute;
                        top: 60px;
                        width: 120px;
                      }
                    </style>
                    <section class="slide slide--divider animated"
                             data-layout-validation="keep"
                             data-nav-title="Act II">
                      <span class="slide__number">II</span>
                      <div class="slide__body">Body</div>
                      <div class="stats-row">Stats</div>
                    </section>
                    """
                )
                before = page.eval_on_selector(
                    ".slide",
                    "el => ({ classes: el.className, marker: el.getAttribute('data-layout-validation'), animation: getComputedStyle(el).animationName })",
                )
                self.assertNotIn("visible", before["classes"].split())
                self.assertEqual(before["marker"], "keep")
                self.assertEqual(before["animation"], "pulse")

                snapshot = page.evaluate(
                    validate_layout.LAYOUT_SNAPSHOT_JS,
                    {
                        "selectors": list(validate_layout.OVERLAP_SELECTORS),
                        "tolerance": validate_layout.CLIP_TOLERANCE_PX,
                        "ratioMin": validate_layout.OVERLAP_RATIO_WARN,
                    },
                )
                after = page.eval_on_selector(
                    ".slide",
                    "el => ({ classes: el.className, marker: el.getAttribute('data-layout-validation'), animation: getComputedStyle(el).animationName })",
                )
            finally:
                browser.close()

        self.assertEqual(len(snapshot["dividerIssues"]), 1)
        self.assertIn("right", snapshot["dividerIssues"][0]["problem"])
        self.assertEqual(len(snapshot["slideOverlaps"]), 1)
        self.assertIn(
            {"a": ".slide__body", "b": ".stats-row", "ratio": 100},
            snapshot["slideOverlaps"][0]["issues"],
        )
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
