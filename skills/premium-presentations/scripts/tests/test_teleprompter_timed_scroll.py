#!/usr/bin/env python3
"""Playwright smoke test for PLAN.md Workstream B (timed teleprompter scroll).

Mirrors the degrade-gracefully pattern used across this suite (see
test_export_pdf.py, test_og_cover.py, test_partial_regen_e2e.py): the real
browser assertions are skipped when Playwright/Chromium is unavailable.
PLAN.md step 17 additionally requires that this skip is NOT silent in CI or
release verification — an absent Chromium there is a hard failure, not a
skip. Locally (no CI/release-verify signal), absence degrades to a clean,
visible skip.

The exhaustive contract math (multiplier rebase, pause/resume continuity,
storage migration, engage-rule fallback, clamp bounds, no-overflow guard)
lives in scripts/tests/teleprompter-timed.test.mjs against jsdom, which does
not compute real CSS layout. This smoke test exists to confirm the same
runtime code behaves correctly against REAL browser layout (scrollHeight /
clientHeight) and REAL wall-clock timing, on a small budgeted fixture deck.
"""
from __future__ import annotations

import functools
import http.server
import os
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SHARED = ROOT / "assets" / "shared"

RUNTIME_FILES = (
    "premium-controller.js",
    "premium-timer.js",
    "premium-presenter.js",
    "slide-engine.js",
    "premium-deck.css",
    "premium-extras.css",
)

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


def _release_gate_active() -> bool:
    """CI (GitHub Actions sets CI=true automatically) or an explicit local
    release-verification run must never silently skip this smoke test."""
    return os.environ.get("CI") == "true" or os.environ.get("PREMIUM_RELEASE_VERIFY") == "1"


FIXTURE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Timed teleprompter smoke fixture</title>
<link rel="stylesheet" href="premium-deck.css">
<link rel="stylesheet" href="premium-extras.css">
<style>
  html, body { margin: 0; padding: 0; height: 100%; }
  .deck { position: relative; }
</style>
</head>
<body>
<div class="deck" id="deck">
<section class="slide" id="slide-1" data-budget="1200">
  <h1 class="slide__display">Overflowing slide</h1>
  <aside class="notes">__LONG_NOTES__</aside>
</section>
<section class="slide" id="slide-2" data-budget="1200">
  <h1 class="slide__display">Short slide</h1>
  <aside class="notes">Short.</aside>
</section>
</div>
<script src="premium-controller.js"></script>
<script src="premium-timer.js"></script>
<script src="premium-presenter.js"></script>
<script src="slide-engine.js"></script>
<script>
  new SlideEngine();
</script>
</body>
</html>
"""


def _write_fixture(directory: Path) -> Path:
    for name in RUNTIME_FILES:
        shutil.copy2(SHARED / name, directory / name)
    long_notes = "<p>Lorem ipsum dolor sit amet consectetur adipiscing elit. " * 60 + "</p>"
    html = FIXTURE_HTML.replace("__LONG_NOTES__", long_notes)
    fixture = directory / "fixture.html"
    fixture.write_text(html, encoding="utf-8")
    return fixture


def _serve(directory: Path) -> http.server.ThreadingHTTPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


class TeleprompterTimedScrollSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        if not HAS_PLAYWRIGHT:
            if _release_gate_active():
                self.fail(
                    "playwright is required in CI/release verification (CI=true or "
                    "PREMIUM_RELEASE_VERIFY=1) but is not installed — run "
                    "'pip3 install -r requirements.txt && python3 -m playwright install chromium'"
                )
            self.skipTest(
                "playwright not installed — skipping timed-teleprompter Playwright smoke test "
                "(set CI=true or PREMIUM_RELEASE_VERIFY=1 to make this a hard failure instead)"
            )

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.fixture = _write_fixture(Path(self.tmpdir.name))
        self.httpd = _serve(Path(self.tmpdir.name))
        self.addCleanup(self.httpd.shutdown)
        self.addCleanup(self.httpd.server_close)
        self.port = self.httpd.server_address[1]

    def _url(self, query: str = "") -> str:
        return f"http://127.0.0.1:{self.port}/fixture.html{query}"

    def test_timed_scroll_reaches_target_reepochs_on_slide_change_and_respects_reduced_motion(self) -> None:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        console_errors: list[str] = []

        with sync_playwright() as pw:
            try:
                browser = pw.chromium.launch(headless=True, timeout=60_000)
            except PlaywrightError as error:
                if "mach_port_rendezvous" in str(error):
                    self.skipTest("Chromium launch is blocked by the delegated sandbox")
                raise
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                context.on(
                    "console",
                    lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
                )

                deck = context.new_page()
                deck.goto(self._url(), wait_until="load")
                session = deck.evaluate("document.documentElement.dataset.session")
                self.assertTrue(session)

                popup = context.new_page()
                # Reduced-motion is set BEFORE the popup's runtime scripts run,
                # exactly as a real browser reports the OS preference from the
                # first paint onward (AT2 invariant carried into timed scroll).
                popup.emulate_media(reduced_motion="reduce")
                popup.goto(self._url(f"?presenter=1&session={session}"), wait_until="load")
                popup.wait_for_function(
                    "document.getElementById('pp-notes') && "
                    "document.getElementById('pp-notes').textContent.trim().length > 0"
                )

                engaged = popup.evaluate("window.PremiumPresenterView.getTeleprompterState().timedEngaged")
                self.assertTrue(engaged, "budgeted fixture deck must engage timed scroll")

                # --- reduced motion: mode toggle must never move anything ---
                popup.keyboard.press("m")
                popup.wait_for_timeout(150)
                state = popup.evaluate("window.PremiumPresenterView.getTeleprompterState()")
                self.assertFalse(state["scrolling"], "mode toggle alone must never start motion")
                scroll_before = popup.evaluate("document.getElementById('pp-notes').scrollTop")
                self.assertEqual(scroll_before, 0)

                # --- reduced motion: explicit p IS allowed and moves the notes ---
                popup.keyboard.press("p")
                popup.wait_for_timeout(300)
                state = popup.evaluate("window.PremiumPresenterView.getTeleprompterState()")
                self.assertTrue(state["scrolling"], "explicit p starts scroll even under reduced motion")
                mid_scroll = popup.evaluate("document.getElementById('pp-notes').scrollTop")
                self.assertGreater(mid_scroll, 0, "reduced-motion users can still explicitly scroll")

                # --- reaches target within tolerance (budget 1200ms; wait well past it) ---
                popup.wait_for_timeout(1800)
                distance = popup.evaluate(
                    "(() => { const n = document.getElementById('pp-notes'); "
                    "return n.scrollHeight - n.clientHeight; })()"
                )
                self.assertGreater(distance, 0, "the long-notes slide must actually overflow #pp-notes")
                final_scroll = popup.evaluate("document.getElementById('pp-notes').scrollTop")
                self.assertGreaterEqual(
                    final_scroll, distance * 0.95,
                    f"timed scroll should reach the target within tolerance: {final_scroll} vs {distance}",
                )

                # --- slide change re-epochs: moving to the short (non-overflowing)
                # slide must reset progress and show no motion there ---
                popup.keyboard.press(" ")  # 'next' control, routed to the deck
                popup.wait_for_timeout(400)
                counter = popup.evaluate("document.getElementById('pp-counter').textContent")
                self.assertIn("2", counter, "slide change must have actually advanced")

                reset_scroll = popup.evaluate("document.getElementById('pp-notes').scrollTop")
                self.assertLessEqual(reset_scroll, 2, "slide change zeroes accumulated progress")

                state = popup.evaluate("window.PremiumPresenterView.getTeleprompterState()")
                self.assertTrue(state["scrolling"], "play intent continues across the slide change")

                popup.wait_for_timeout(500)
                no_overflow_scroll = popup.evaluate("document.getElementById('pp-notes').scrollTop")
                self.assertEqual(no_overflow_scroll, 0, "a non-overflowing slide must show zero motion")
            finally:
                browser.close()

        self.assertEqual(console_errors, [], f"no console errors expected: {console_errors}")


if __name__ == "__main__":
    unittest.main()
