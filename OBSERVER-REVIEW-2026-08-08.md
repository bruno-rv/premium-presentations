# Observer Review — refactor-premium-presentation

**Date:** 2026-08-08
**Observer session:** monitoring peer session `refactor-premium-presentation [857e4e]`
**Repo HEAD at review:** `def4ae5` (main) + 8 uncommitted files in the shared working tree
**Status:** all findings resolved and re-verified — see sections 5 and 6. Sections 1–4 record the
review as it stood against the *first* draft of section C, which was rejected; the shipped
behaviour is the opposite of what F2 describes. Read section 5 for what actually landed.
**Primary objective under audit:** (1) increase code quality, (2) reduce total deck build time

---

## 1. Scope observed

Two landed sections plus one in-flight section:

| Section | State | Files |
|---|---|---|
| A — batched layout validation | landed, `c31f634` (branch `codex/optimize-deck-validation`, merged) | `validate_layout.py`, `tests/test_validate_layout.py` |
| B — README refresh | landed, `def4ae5` (branch `codex/readme-updates`, merged) | `README.md` |
| C — sweep hardening + readiness tuning | **uncommitted**, revised and verified | `validate_layout.py`, `validate_deck.py`, `deck_doctor.py`, `export_pdf.py`, `og_cover.py`, `SKILL.md`, `tests/test_validate_layout.py`, `tests/test_deck_doctor.py` |

Section C is described below in two states: the **first draft**, which defaulted the layout sweep
to the deck's authored theme and which this review rejected, and the **revised** version in the
tree now, which defaults to the full sweep and exposes `--single-theme` as an opt-in. Findings
F1–F8 are against the draft; section 5 records the verified fixes.

Both `codex/*` branches are fully contained in `main`; only `README.md` differs between
`main` and `codex/optimize-deck-validation`, and `codex/readme-updates` is identical to `main`.

The peer session did not respond to a status request, so section C was reconstructed from
the working-tree diff.

---

## 2. Measured build time

Method: `validate_layout._playwright_check()` on the fixed 20-slide
`assets/examples/rag-vector-graph/rag-vector-graph-slides.html`, 4 runs per configuration,
first run discarded, median of the remaining 3. Each configuration ran from its own detached
`git worktree` so the peer's live edits to the shared tree could not perturb the numbers.
Theme registry: `editorial, warm, red, cupertino`. Viewports: 1280×720, 1440×900, 1920×1080.

| Configuration | Commit / state | Themes swept | Median | Δ vs previous |
|---|---|---|---|---|
| Baseline | `2438e32` (parent of the perf commit) | 4 | **54.82 s** | — |
| Section A — batched sweep | `def4ae5` | 4 | **1.17 s** | −53.65 s (−97.9 %) |
| Section C — `load` readiness, full sweep | working tree, `--all-themes` | 4 | **0.65 s** | −0.52 s (−44 %) |
| Section C — default (theme-scoped) | working tree | 1 | **0.43 s** | −0.22 s (−34 %) |
| Section C + Mermaid gate (F6 fix), full sweep | working tree + gate, `--all-themes` | 4 | **0.64 s** | −0.01 s |
| Section C + Mermaid gate, theme-scoped | working tree + gate | 1 | **0.38 s** | −0.26 s |

The last two rows matter because the F2 argument below rests on the readiness change being
free. Adding the `.mermaid-wrap`-has-`<svg>` gate that F6 requires costs 0.01 s — the readiness
win survives the fix intact, so "keep `load` (gated), drop theme-scoping" is not weakened by it.

All four configurations reported 0 errors and 0 warnings on the reference deck, so the
speedup is not bought by dropping findings on this input.

The same effect shows up in the full Python suite, which exercises the sweep repeatedly:

| Tree | Result | Wall-clock |
|---|---|---|
| `2438e32` baseline | 420 tests, OK (1 skipped) | **589.8 s** |
| working tree (A + C) | 429 tests, 1 failure, 1 skipped | **115.7 s** |

**Verdict on objective (2): met, decisively, by section A.** The layout gate went from
~55 s to ~1 s per deck — a 47× reduction and the dominant term in deck validation wall-clock.
Suite feedback time dropped ~80 % (9.8 min → 1.9 min) as a second-order effect, which matters
more for iteration speed than the per-deck number does.

---

## 3. Findings

### F1 — BLOCKING: a broken layout sweep reports `DECK HEALTHY`

`validate_layout.validate_deck_layout()` wraps the entire Playwright sweep in a bare
`except Exception` and downgrades any failure to a warning:

```python
try:
    px_errs, px_warns = _playwright_check(html_path, all_themes=all_themes, html=html)
    ...
except Exception as exc:
    warnings.append(f"Layout pixel checks failed: {exc}")
```

This is not theoretical. It fires today on the working tree:

```
WARN: Layout pixel checks failed: sweep() got an unexpected keyword argument 'all_themes'
...
DECK HEALTHY — 2 warning(s)
```

`deck_doctor.py` exits 0. The entire layout gate was disabled and the deck was declared
healthy. Any signature change, Playwright upgrade, or Chromium launch failure produces the
same silent pass.

Severity is now higher than it was before section A. At 55 s the sweep's absence was
visible as a wall-clock anomaly; at 0.4 s a skipped sweep is indistinguishable from a fast one.

**Fix:** separate the two cases. "Playwright/Chromium not installed" is a legitimate warning
(the code already handles it via the `ImportError` branch). Anything else raising out of
`_playwright_check` is a validator defect and must be an error that fails the gate.

### F2 — Default theme-scoping trades 75 % of coverage for 0.22 s

Section C narrows the sweep to the deck's authored `data-theme` unless `--all-themes` is
passed. The measurements above isolate what each half of section C actually buys:

- `networkidle` → `load`, with the Mermaid gate F6 requires: **−0.53 s, no coverage change.**
- theme-scoping on top of that: **−0.26 s, coverage 4 themes → 1.**

The stated rationale — "the runtime theme switcher is a preview convenience, not a
validation contract" — conflicts with what the project ships and documents. Decks embed the
complete theme registry as data URIs specifically so live theme switching works standalone,
and `README.md` advertises that. A layout break in `red` or `cupertino` on a deck authored in
`editorial` now ships undetected, and the report output does not say coverage was reduced.

**Recommendation:** keep the `load` change **only together with** the Mermaid-SVG gate from F6 —
ungated, `load` is not safe and `networkidle` remains the correct default. Gated, it is 67 % of
the remaining win for 0 % of the coverage. Drop the theme-scoping default: it buys the last
0.26 s by discarding three quarters of the theme coverage, silently. If theme-scoping is kept
anyway, it must (a) invert to
opt-in (`--single-theme`), or at minimum (b) print which themes were swept in the
`validate_deck` report so a reduced gate is never silent, and (c) be forced to `--all-themes`
in CI and in the release checklist.

### F3 — Section C breaks an existing test

`tests/test_deck_doctor.py::test_layout_validation_runs_once_and_rejects_layout_errors`
fails on the working tree (`AssertionError: 0 != 1`). Its mock replaces `_playwright_check`
with a positional-only stub, which no longer matches the new keyword signature. The failure
is masked by F1 — the TypeError becomes a warning instead of an error, so the sweep counter
stays at 0 and the doctor still exits 0.

Full Python suite on the working tree: **429 tests, 1 failure, 1 skipped.** The same test
passes on `2438e32` and on `def4ae5`, so the breakage is section C's.

### F4 — Section A is a bug fix mislabeled as a perf commit

The pre-batching overlap probe read
`document.querySelector('.slide.visible') || document.querySelector('.slide')` — a
document-level query — while the Python loop scrolled through slides and attributed each
result to the scrolled slide's `data-nav-title`. Scrolling does not add `.visible`, so the old
code measured the same slide on every iteration and labelled the findings with the wrong slide
titles. The divider check had a matching defect: `clip_js` iterated every divider internally
while the Python loop also iterated dividers, emitting each finding N times.

The batched version measures each slide individually under a scoped
`data-layout-validation` marker with animations and transitions forced off, restores prior
state in a `finally`, and emits each finding once. It is more correct as well as faster —
worth stating in the changelog rather than filing under `perf:`.

### F5 — Section B is a factual-accuracy pass, and it checks out

The README diff removes claims the repo does not support. Spot-checked the load-bearing one:
the old text claimed "CI additionally runs a pinned Codex plugin validator". `.github/workflows/ci.yml`
has no such step — its steps are static/bootstrap contracts, focused and aggregate Node tests,
aggregate Python tests, runtime/theme validation, `npm audit`, and `git diff --check`, which is
exactly what the new text says. Other corrections ("Guaranteed" → "Built-in" theme homages,
`/present-pr` → all three recipes, the Vercel-URL-extraction failure path) are narrowing
overclaims to what the code does. Net quality gain, no code risk.

---

### F6 — `load` readiness has no gate for asynchronous Mermaid rendering (raised by Codex)

Section C replaces `wait_until="networkidle"` with `wait_until="load"` in three scripts, on the
reasoning that the downstream readiness gates are authoritative. For `export_pdf.py` that holds —
`window.__pdfReady` plus the Mermaid-SVG gate are genuine signals. For `validate_layout.py` it
does not: after `load`, `LAYOUT_SNAPSHOT_JS` waits only on `document.fonts.ready` and a double
`requestAnimationFrame`, and nothing waits on Mermaid.

The mechanism is confirmed. `premium-mermaid.js:890-906` starts `initPremiumMermaid()` from
`DOMContentLoaded`, and it `await`s a dynamic `loadMermaid()` import before `mermaid.run()`.
`load` fires before any of that resolves. Under `networkidle` the extra ~500 ms quiet period was
incidentally covering the gap; `load` removes it. A snapshot taken mid-render measures
placeholder geometry, and real layout findings are missed silently.

Not reproduced on the reference deck: instrumenting the page shows its single `.mermaid-wrap`
already contains its `<svg>` at `fonts.ready` + double-rAF under both `load` and `networkidle`,
with no change after a further 3 s. So this is a latent race on a warm cache and one diagram,
not a demonstrated failure — but it is unguarded, and the 0-findings parity in section 2 is
consistent with either "nothing to find" or "found nothing because it looked too early".

**Fix is free, and measured:** reuse the Mermaid-SVG gate `og_cover.py` and `export_pdf.py`
already have — require every `.mermaid-wrap` to contain a rendered `<svg>` before snapshotting.
Applying it to the working tree moves the full sweep from 0.65 s to 0.64 s. Until it is applied,
`load` is not a safe default for this script.

### F7 — OG cover can capture unsettled assets (raised by Codex)

`og_cover.py` under `load` waits only for Mermaid SVGs, then screenshots immediately. Theme
visuals and optional theme fonts are injected asynchronously during runtime initialization, so a
cover can be captured with a fallback font or a missing hero image while the command still exits
0. Not measured in this review.

### F8 — An authored custom theme is never validated (raised by Codex, sharpens F2)

When the deck's `data-theme` is not in `discover_themes()`, section C leaves `themes` as the full
built-in registry. The in-code comment frames this as a safe fallback to the full sweep, but the
authored theme is precisely the one omitted: the deck is measured under 4 built-in themes and
never under the theme it actually ships with.

Scope check: `_common.discover_themes()` reads `THEMES_CSS` — the theme registry of the skill
installation the validator is running from — with no argument threading from the deck. It never
reads the registry the deck itself embeds. So a `generate_theme.py` theme written into the
repository's own `assets/shared/premium-themes.css` in a source checkout *is* discovered; a theme
installed into a workspace-owned registry via `--themes-css`, which is the flow SKILL.md
prescribes for read-only marketplace caches, is not. This predates section C — the base code also
swept only `discover_themes()` — but section C is the change that documents the behaviour as an
intentional, safe fallback, which for the workspace-registry flow it is not.

---

## 4. Adherence verdict

| Objective | Section A | Section B | Section C |
|---|---|---|---|
| Code quality | **Improves** — removes a real measurement bug and duplicate findings; adds fake-page unit tests plus a real-Chromium regression test asserting both detection and state restoration | **Improves** — removes documented claims the repo does not implement | **Mixed** — the `load` change and its tests are clean; theme-scoping weakens a shipped gate silently, and one existing test is left failing |
| Build time | **Improves** — 54.82 s → 1.17 s | Neutral | **Improves** — 1.17 s → 0.65 s from readiness alone; the further 0.22 s comes out of coverage |

Sections A and B adhere to the objective. Section C adheres in part and is not
mergeable as it stands: F1, F3 and F6 must be fixed, F2/F8 need an explicit decision on the
theme-coverage contract, and F7 needs assessment.

An independent Codex adversarial review of the same diff returned **needs-attention / no-ship**,
independently reaching F1 and F2 and adding F6, F7 and F8. Its summary: "the layout gate can fail
open, default coverage is silently reduced, and load readiness is not semantically complete."

## 5. Re-review after fixes

The peer session addressed all findings. Verified independently against a detached-worktree
snapshot of the revised tree, not by reading the change description.

| Finding | Claim | Verified |
|---|---|---|
| F1 fail-open | sweep exceptions now fail the gate; environment issues stay warnings | **Yes.** Injected a signature defect → `FAIL: Layout pixel checks failed: bad() got an unexpected keyword argument 'single_theme'`, rc=1, no `DECK HEALTHY`. Injected an arbitrary `RuntimeError` mid-sweep → rc=1. Faked a Chromium launch failure → `WARN: Layout pixel checks skipped — Chromium unavailable`, rc=0. All three behave as specified. |
| F2 coverage | theme-scoping dropped as default; `--single-theme` is opt-in | **Yes.** Default sweeps `['editorial', 'warm', 'red', 'cupertino']`. `SKILL.md` documents the contract and points at the flag for tight edit loops. |
| F3 test | mock accepts `**kwargs` | **Yes.** `test_deck_doctor` passes; the 28 tests across the four touched modules pass. |
| F6 Mermaid gate | every `.mermaid-wrap` must contain an `<svg>` before snapshotting | **Yes.** Gate present before the theme loop, guarded by a `.mermaid-wrap` count check. |
| F7 OG cover | fonts + all images complete + double-rAF before screenshot | **Yes** by inspection. Not measured — I did not verify cover pixel output. |
| F8 custom theme | `--single-theme` validates a theme outside the registry | **Yes.** `data-theme="acme-brand"` now sweeps `['acme-brand']`; previously it fell back to the four built-ins and never measured the shipped theme. No declared theme still falls back to the full sweep. |

Structure check: everything now runs inside `with sync_playwright()`, with `finally: browser.close()`
inside it — no use-after-exit.

**Build time after fixes** (same method, same deck):

| Config | Themes | Median |
|---|---|---|
| `2438e32` baseline | 4 | 54.82 s |
| revised tree, default | 4 | **0.68 s** |
| revised tree, `--single-theme` | 1 | 0.39 s |

The default path is now **80× faster than baseline at full theme coverage** — better than the
1.17 s that landed in `def4ae5`, and without the coverage loss the earlier draft would have taken.
Both objectives are met on the default path; the speed no longer comes out of the gate.

Full Python suite on the revised snapshot: **432 tests, OK (1 skipped), 100.4 s** — against
420 tests / 589.8 s at `2438e32`. Suite feedback time is down 83 % with 12 more tests.

### Residual notes — both resolved

- **N1: documented, not fixed.** Accepted. Dispatching `premium-theme-change` would re-render
  every Mermaid diagram per theme and rebuild search, multiplying sweep cost, and would force the
  F6 gate inside the theme loop. The comment now in `READINESS_JS` names the limitation and the
  reason, which is what the note asked for.
- **N2: fixed.** The launch warning now reads "browser launch failed: {exc}" instead of asserting
  a missing Chromium. No test referenced the old string; the 28 tests across the touched modules
  still pass.

Original text of both notes follows.

- **N1 — theme sweeps bypass the runtime's theme-change path.** `READINESS_JS` sets
  `document.documentElement.dataset.theme` directly. Nothing observes that attribute; the
  `premium-theme-change` event is dispatched only by `premium-controls.js:655`. So theme-reactive
  modules never re-run during a sweep — `premium-red-chrome.js:144-152` mounts and removes
  `.red-brand-bar` and injects `.red-mark-hero` only on init and on that event, and
  `.red-brand-bar` is in `OVERLAP_SELECTORS`. A red-themed deck swept under `editorial` therefore
  measures editorial CSS with the red bar still mounted — a combination that never occurs at
  runtime. This is pre-existing (the pre-`c31f634` code set the attribute the same way), and it
  produces false positives rather than missed bugs, so it is noise rather than a hole. Not
  reproduced: the reference deck does not bundle `premium-red-chrome.js` at all. If the
  now-documented "every theme is validated" contract is meant literally, dispatching
  `premium-theme-change` in `READINESS_JS` would close it — but Mermaid also re-renders on that
  event, so the F6 gate would need to move inside the theme loop.
- **N2 — the Chromium-launch `except Exception` is broad.** Any failure from
  `p.chromium.launch()` is reported as "Chromium unavailable", including causes that are not
  that. Narrow scope, misleading message only.

## 6. Landing decisions

Decided in council between the implementing session and an independent Codex consult, after all
findings were closed. Nothing here has been committed, pushed, or tagged — that is the user's call.

1. **Separate commits, not one.** `export_pdf.py` / `og_cover.py` are export readiness, not the
   layout gate; they rode along and should be separable. The CLI flag is user-facing surface and
   the internal hardening is not — they carry different revert risk and different semver weight.
   The landed sequence:
   - `fix: harden layout sweep correctness` — `validate_layout.py`,
     `tests/test_validate_layout.py`, and the `**kwargs` hunk of `tests/test_deck_doctor.py`
   - `feat: expose opt-in single-theme validation` — `validate_deck.py`, `deck_doctor.py`,
     the rest of `tests/test_deck_doctor.py`, `SKILL.md`
   - `fix: wait for settled browser assets before export` — `export_pdf.py`, `og_cover.py`
   - `ci: smoke the real bundled deck` — `.github/workflows/ci.yml`
   - `docs: record layout validation review and known limitation` — this file, `ROADMAP.md`
   - `chore: release v2.2.0` — the four version manifests

   The first plan claimed the boundaries fell on whole files and needed no hunk-splitting. That
   was wrong, and building the commits caught it: the fail-closed change in commit 1 turns the
   old positional-only mock stub in `tests/test_deck_doctor.py` into a validator defect, so that
   file's `**kwargs` fix belongs in commit 1 and the rest in commit 2. Verified by running the
   full suite from a detached worktree at each commit rather than trusting the reasoning — 432
   tests OK at commit 1.
2. **Short-lived branch, not straight to main.** The two prior commits went straight to main, but
   this one changes validation pass/fail semantics and adds a CLI mode; that earns one explicit
   integration boundary. `git switch -c` carries the current working tree over cleanly — nothing
   else is uncommitted.
3. **Bump to 2.2.0 in this landing and tag `v2.2.0`.** Leaving four post-tag commits unversioned
   would make the merged state ambiguous, so the bump is its own `chore: release v2.2.0` commit
   and the annotated tag follows the merge. Minor, not patch:
   `--single-theme` is new user-facing capability. Not major: the stricter gate is a correctness
   fix inside the documented validator contract, though release notes must say plainly that
   previously passing decks may now fail. Four files carry the version and must align —
   `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`
   (`metadata.version`), `scripts/package.json`. `.agents/plugins/marketplace.json` has none.
4. **`c31f634` is not rewritten.** It is already on `origin/main`. Its `perf:` prefix is
   incomplete — it also fixed incorrect slide attribution and duplicate divider findings (F4).
   Correct the record in the `v2.2.0` release notes. There is no tracked `CHANGELOG.md` and one
   should not be created just to repair historical commit metadata.
5. **N1 accepted for this landing, tracked as P2.** The code comment stays. Add a ROADMAP entry
   that preserves the performance rationale and names the revisit trigger: a deck bundling
   `premium-red-chrome.js`, a second event-reactive module, or a real false-positive report.
   Acceptance for a future fix requires a fixture with an event-reactive module, correct per-theme
   lifecycle, Mermaid readiness, and a measured performance comparison — dispatching the event is
   not automatically the right implementation.
6a. **Implemented and verified.** Branch `perf/layout-validation` off `def4ae5`. Exercised the
   real CLI against the real reference deck: `--single-theme` prints
   `Layout sweep: editorial (single-theme)` and
   `DECK VALIDATED (single-theme: editorial) — run the full sweep before shipping`, rc=0, and
   never `DECK HEALTHY`; the default path still prints `DECK HEALTHY`; and `--single-theme` on a
   deck with no declared `data-theme` correctly falls back to the full sweep and prints
   `DECK HEALTHY`, so the verdict stays honest. Full Python suite 433 OK (1 skipped) in 105.8 s.
   Naming nit resolved: `_declared_theme_from_html` is now public `declared_theme_from_html`
   with a docstring naming its two roles, across all three consumers. The rename lands in
   commit 1 and the split still bisects cleanly — at `def4ae5` neither `validate_deck.py` nor
   `deck_doctor.py` referenced the function, so commit 1 renames it in isolation and commit 2
   introduces both imports already using the public name. Full suite after the rename:
   433 OK (1 skipped), 103.0 s.

6. **`--single-theme` gets a mechanical guard, not just prose.** Wording alone is weak protection
   for an autonomous-agent audience. In scope now: a single-theme run must name the theme it
   swept, must not print `DECK HEALTHY`, and SKILL.md states the negative constraint — never ship
   a deck validated only with `--single-theme`. Deferred, and re-confirmed as deferred after the
   CI smoke landed: a distinct exit status for "complete but incomplete coverage", and a
   CI/release mode that rejects the flag. Exit codes are an API contract touching every caller,
   and with the CI smoke running the full sweep there is nothing for a rejection mode to guard.
   Revisit when automation starts forwarding validator flags, a release path uses
   `--single-theme`, or a consumer needs a machine-readable partial/complete distinction.

7. **CI now smokes the real bundled deck.** Raised as an out-of-scope gap and then taken in this
   landing, because it is the only thing that exercises end-to-end what this work changed. CI ran
   the static/bootstrap contracts, focused and aggregate Node suites, aggregate Python tests,
   `validate_runtime_contract.py`, `validate_contrast.py`, `npm audit`, and `git diff --check` —
   `npm test` is `node --test tests/*.test.mjs`, so even `test:bundle` never ran there. The layout
   gate was therefore exercised in CI only by unit tests, fake-page tests, and one real-Chromium
   test over synthetic markup. The new step runs `deck_doctor.py` with its spec over
   `assets/examples/rag-vector-graph/`, which covers the full multi-theme sweep plus diagrams,
   runtime contract, portability, contrast, and spec parity. Verified locally: `DECK HEALTHY`,
   exit 0, 0.9 s, and the deck's one pre-existing bare-slide warning does not affect exit status,
   so the step is not flaky.

   A related concern was raised and checked: a release cut on a machine where Chromium fails to
   launch would pass with a warning, since environment failures are warnings by design (F1). For
   CI this is already covered — `bootstrap.py --check` asserts the managed Chromium is present
   and fails the run otherwise. The exposure is local release cuts only.

## 8. Gaps in this review

- Build time here means the deterministic validator sweep. Agent-turn latency — the other
  half of "total time to build a deck" — is not measured by this method and is not covered.
- One deck (20 slides, `editorial`, 1 Mermaid diagram) on one machine. Slide-count scaling
  was verified only through the fake-page test asserting a constant `evaluate` call count.
- The section-2 measurements were taken from detached worktrees while the implementing session
  was editing the shared tree; each configuration was measured against a fixed snapshot.
- Cover pixel output for the F7 fix was verified by inspection, not by comparing rendered images.
