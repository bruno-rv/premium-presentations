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


class _FakePage:
    def __init__(self, slide_count: int) -> None:
        self.slide_count = slide_count
        self.evaluate_calls: list[tuple[str, object | None]] = []
        self.viewport_calls: list[dict[str, int]] = []

    def goto(self, *_args: object, **_kwargs: object) -> None:
        return None

    def set_viewport_size(self, viewport: dict[str, int]) -> None:
        self.viewport_calls.append(viewport)

    def wait_for_timeout(self, *_args: object) -> None:
        raise AssertionError("layout validation must not use fixed timeouts")

    def evaluate(self, script: str, argument: object | None = None) -> object:
        self.evaluate_calls.append((script, argument))
        if script == validate_layout.READINESS_JS:
            return None
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


def _run_sweep(slide_count: int) -> tuple[_FakePage, list[str], list[str]]:
    page = _FakePage(slide_count)
    playwright = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _FakeSyncPlaywright(page)  # type: ignore[attr-defined]
    playwright.sync_api = sync_api  # type: ignore[attr-defined]

    with mock.patch.dict(
        sys.modules,
        {"playwright": playwright, "playwright.sync_api": sync_api},
    ), mock.patch.object(validate_layout, "discover_themes", return_value=["red", "warm"]):
        errors, warnings = validate_layout._playwright_check(Path("deck.html"))
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

        expected_calls = 2 * (1 + 3)  # themes * (theme readiness + viewports)
        self.assertEqual(len(small_page.evaluate_calls), expected_calls)
        self.assertEqual(len(large_page.evaluate_calls), expected_calls)
        self.assertEqual(len(large_page.viewport_calls), 2 * 3)

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

    def test_readiness_waits_for_fonts_and_two_animation_frames(self) -> None:
        for script in (validate_layout.READINESS_JS, validate_layout.LAYOUT_SNAPSHOT_JS):
            self.assertIn("document.fonts.ready", script)
            self.assertGreaterEqual(script.count("requestAnimationFrame"), 2)


class LayoutSnapshotBrowserTests(unittest.TestCase):
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
