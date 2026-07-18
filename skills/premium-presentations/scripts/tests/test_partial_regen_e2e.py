from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from slide_html import parse_slide_spans


SCRIPTS = Path(__file__).resolve().parent.parent
SKILL_ROOT = SCRIPTS.parent
# Each CLI mutation runs Deck Doctor, including Playwright layout checks. The
# hosted Ubuntu runner can take more than two minutes for that validation.
SUBPROCESS_TIMEOUT = 240

try:
    import playwright  # noqa: F401

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class PartialRegenE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def copy_reviewable_fixture(self) -> tuple[Path, Path]:
        source = SKILL_ROOT / "assets" / "examples" / "rag-vector-graph"
        deck = self.root / "rag-vector-graph-slides.html"
        spec = self.root / "rag-vector-graph-slide-spec.md"
        shutil.copy2(source / deck.name, deck)
        shutil.copy2(source / spec.name, spec)
        return deck, spec

    @mock.patch(
        f"{__name__}.subprocess.run",
        side_effect=subprocess.TimeoutExpired(["tool"], SUBPROCESS_TIMEOUT),
    )
    def test_subprocess_timeout_is_actionable(self, _run: mock.Mock) -> None:
        with self.assertRaisesRegex(
            AssertionError, "partial regeneration command timed out after 240 seconds"
        ):
            self.run_command(["tool"], label="partial regeneration command")

    def test_browser_launch_timeout_is_bounded(self) -> None:
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        launches = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "launch"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "chromium"
        ]
        self.assertEqual(1, len(launches))
        timeout = next(
            (keyword.value for keyword in launches[0].keywords if keyword.arg == "timeout"),
            None,
        )
        self.assertIsInstance(timeout, ast.Constant)
        self.assertEqual(60_000, timeout.value)

    def run_command(
        self, command: list[str], *, label: str
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                text=True,
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"{label} timed out after {SUBPROCESS_TIMEOUT} seconds")

    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = self.run_command(
            [sys.executable, str(SCRIPTS / "partial_regen.py"), *arguments],
            label="partial regeneration command",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def fragment_for(self, deck: Path, slide_id: str, old: str, new: str) -> Path:
        span = next(item for item in parse_slide_spans(deck.read_text(encoding="utf-8")) if item.slide_id == slide_id)
        fragment = span.raw.replace(old, new)
        path = self.root / f"{slide_id}.html"
        path.write_text(fragment, encoding="utf-8")
        return path

    @unittest.skipUnless(HAS_PLAYWRIGHT, "playwright not installed — skipping theme-homage integration check")
    def test_public_cli_round_trip_preserves_theme_homage_payload(self) -> None:
        deck, spec = self.copy_reviewable_fixture()
        original = deck.read_text(encoding="utf-8")
        marker = "/* --- theme-visuals-embed --- */"
        start = original.index(marker)
        start = original.rfind("<script", 0, start)
        end = original.index("</script>", start) + len("</script>")
        homage = original[start:end]

        self.run_cli("init", "--deck", str(deck), "--spec", str(spec), "--apply")
        spec.write_text(
            spec.read_text(encoding="utf-8").replace(
                "Retrieval benchmark", "Verified retrieval benchmark", 1
            ),
            encoding="utf-8",
        )
        plan = self.run_cli("plan", "--deck", str(deck), "--spec", str(spec), "--json")
        changed = json.loads(plan.stdout)["changed"]
        self.assertEqual(1, len(changed))
        slide_id = next(iter(changed))
        fragment = self.fragment_for(
            deck, slide_id, "Retrieval benchmark", "Verified retrieval benchmark"
        )
        self.run_cli(
            "apply", "--deck", str(deck), "--spec", str(spec), "--fragment", f"{slide_id}={fragment}"
        )

        updated = deck.read_text(encoding="utf-8")
        updated_start = updated.index(marker)
        updated_start = updated.rfind("<script", 0, updated_start)
        updated_end = updated.index("</script>", updated_start) + len("</script>")
        self.assertEqual(updated[updated_start:updated_end], homage)

        doctor = self.run_command(
            [sys.executable, str(SCRIPTS / "deck_doctor.py"), str(deck), str(spec)],
            label="Deck Doctor",
        )
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assert_theme_homages_remain_embedded(deck)

    def assert_theme_homages_remain_embedded(self, deck: Path) -> None:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        console_errors: list[str] = []
        failed_requests: list[str] = []
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True, timeout=60_000)
            except PlaywrightError as error:
                if "mach_port_rendezvous" in str(error):
                    self.skipTest("Chromium launch is blocked by the delegated sandbox")
                raise
            try:
                page = browser.new_page()
                page.set_default_timeout(30_000)
                page.set_default_navigation_timeout(60_000)
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("requestfailed", lambda request: failed_requests.append(request.url))
                page.goto(deck.as_uri(), wait_until="load")
                themes = page.evaluate("Object.keys(window.PremiumThemeVisuals).sort()")
                self.assertTrue(themes)
                for theme in themes:
                    result = page.evaluate(
                        """theme => {
                            window.PremiumPresentations.setTheme(theme);
                            const payload = window.PremiumThemeVisuals[theme];
                            const visuals = [...document.querySelectorAll('.theme-visual')]
                                .map(visual => ({
                                    role: visual.dataset.themeVisualRole,
                                    src: visual.querySelector('.theme-visual__image')?.getAttribute('src') || '',
                                }));
                            return {payload, visuals};
                        }""",
                        theme,
                    )
                    self.assertTrue(result["payload"]["hero"].startswith("data:image/webp;base64,"))
                    self.assertTrue(result["payload"]["map"].startswith("data:image/webp;base64,"))
                    for role in ("hero", "map"):
                        sources = [
                            visual["src"]
                            for visual in result["visuals"]
                            if visual["role"] == role
                        ]
                        self.assertTrue(sources, f"{theme} has no injected {role} visual")
                        self.assertTrue(
                            all(source == result["payload"][role] for source in sources),
                            f"{theme} {role} visual src does not match PremiumThemeVisuals",
                        )
                page.locator("#premium-controls-tab").click()
                self.assertEqual(page.locator("#premium-controls-tab").get_attribute("aria-expanded"), "true")
                self.assertTrue(page.locator("#premium-controls-panel").count())
                self.assertEqual(page.evaluate("typeof window.PremiumPresenter"), "object")
            finally:
                browser.close()
        self.assertEqual(console_errors, [])
        self.assertEqual(failed_requests, [])
