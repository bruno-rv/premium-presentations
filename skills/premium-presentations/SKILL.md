---
name: premium-presentations
description: >-
  Generates, edits, validates, and bundles complete Premium Presentations HTML
  slide decks from this self-contained repository skill. Use when creating or
  modifying presentations, slide decks, talks, lectures, workshops, pitches,
  browser-rendered HTML decks, presenter-mode decks, themed decks, Mermaid
  diagram decks, or reusable presentation templates, and when bundling decks,
  adding speaker timers, annotations, OG covers, or validating deck output
  with the bundled scripts, themes, runtime, assets, and validators. Also
  covers exporting a finished deck to PDF, an OG cover image, or a Markdown
  speaker-notes handout.
---

# Premium Presentations

This directory is the Claude skill. Use the bundled scripts, references, and
assets from this folder instead of recreating a slide framework from memory.

## Start

1. Work from the directory containing this `SKILL.md`. If the current workspace
   is elsewhere, locate this folder through the skill path, the user-provided
   path, or `PREMIUM_PRESENTATIONS_REPO`.
2. Discover themes dynamically:

```bash
./scripts/list-themes.py
```

Themes come from `html[data-theme="..."]` selectors in
`assets/shared/premium-themes.css`. Do not hardcode the current theme names.

## Create A Deck

**Step 1 — Content-First Brief (required before any slide work)**

Before scaffolding or writing slides, fill the Content-First Brief in the spec:
- Topic archetype (abstract concept / process / data story / historical / debate)
- Hero moment: the one slide the audience must carry out + which component surfaces it
- Audience's wrong assumption at entry (drives the opening hook)
- Exclusion list: 2–3 components that would feel forced on this topic
- Narrative arc type (linear / before→after / exploration→synthesis / problem→solution)
- Color semantics budget: each accent color gets one semantic role for this deck only

Do not assign components to slides until this brief is complete. The routing table in
`references/components.md` is a tool that serves the brief — not a starting point.

**Step 2 — Scaffold and spec**

```bash
./scripts/new-deck.sh <theme> <slug> "<title>" <slide_count>
```

For 8+ slides, use the generated slide spec as the contract. Derive act structure
from the topic's natural phases (Narrative Arc section in the spec) — not from a
default intro/body/conclusion rhythm. Divider slides mark act boundaries.

If the hero moment requires a visual that no catalog pattern covers, invent one:
name it, describe its structure in Design Directives > Signature visual, and flag
it for catalog addition after review. Forcing a poor-fit catalog pattern is worse.

**Step 3 — Validate (hard gate)**

```bash
python3 scripts/deck_doctor.py assets/decks/<slug>/<slug>-slides.html assets/decks/<slug>/<slug>-slide-spec.md
```

Exit 1 → fix the reported issues in deck or spec, re-bundle if the fix touched
`assets/shared/` or `assets/templates/`, re-run. Repeat until exit 0. A deck is
not done until deck doctor exits 0 — never deliver a deck with failing
validation. `scripts/validate_deck.py` and `./scripts/validate_runtime_contract.py`
stay available for isolated debugging of one check.

Use lowercase hyphenated slugs. For unspecified themes, use the first theme
returned by `list-themes.py` unless the topic clearly calls for another
discovered theme. `assets/decks/` is generated output and ignored by git; commit
a finished deck only when the user explicitly asks.

## Runtime Contract

Generated decks must carry the shared CSS/JS runtime stack — the full module
table lives in `references/runtime.md`. Conditional additions:

- Journey SVG slides that use `.journey-stage` also include
  `premium-journey.js`.
- Live-flow slides that use `.live-flow` also include `premium-flow.js`.
- Mermaid diagram slides also include `premium-mermaid.js` and
  `premium-diagrams.css` handling.
- Red decks also include `premium-red-brand.css` and `premium-red-chrome.js`.
- Visual Design Power decks carry `premium-design-power.css/js` for theme
  composer output, layout variants, density checks, motion profiles,
  data visualization blocks, and visual asset audits.

Runtime 3D modes (`off/ambient/tilt/depth`) cycle with the `3` key; author a
deck default with `data-3d="<mode>"` on `<html>` — see `references/runtime.md`.
Motion profile defaults can also be authored with `data-motion-profile="<name>"`.
Generated decks are portable standalone HTML: do not add CDN scripts, remote
font links, or runtime `http(s)` asset dependencies.

Run `./scripts/validate_runtime_contract.py` after template, theme, bundler,
or shared runtime edits — required, not optional: it checks the repo-wide
contract (templates + every deck under `assets/`), which `deck_doctor.py`
does not, since doctor only scopes runtime-contract checks to the one deck
passed on its command line.

## Reference Files

- `references/runtime.md`: runtime module table, extension points, theme
  visuals, Mermaid, presenter/chrome behavior.
- `references/design.md`: audience, style, anti-patterns, and deck design
  principles.
- `references/components.md`: reusable visual components and snippet IDs.
- `references/examples.md`: copy-paste slide markup patterns.
- `references/themes-red.md`: red theme rules.
- `references/slide-spec-template.md`: deck planning template used by
  `scripts/new-deck.sh`.

Load only the reference needed for the current task.

## Build Guidance

- Start from `scripts/new-deck.sh`; do not create a parallel scaffold.
- Use `assets/templates/` and `assets/shared/` as the source of truth.
- Use `assets/templates/components/` snippets for advanced visual blocks.
- Route every content slide through the content-type → component table in
  `references/components.md`; bare heading + paragraph slides are not allowed.
- Use the provided runtime controls instead of ad hoc controls.
- Follow `references/design.md` for slide design principles (one dominant
  idea per slide, generic branding unless requested, no closing footer-note
  rows, "NEXT:" citations, or lesson-pill rows).
- **Speaker notes (mandatory):** for every `<section class="slide …">`,
  render the spec's Speaker Notes field as an `<aside class="notes">` element
  placed as the **last child** inside the section — after all visible content.
  Notes are hidden from the audience (CSS `display: none` is applied by the
  runtime on `.slide aside.notes`). The presenter popup reads them via
  `aside.notes` selectors in `slide-engine.js`. See `references/examples.md`
  for the exact markup pattern.

## Validate

Before completion, run the gate — see Step 3. For shared runtime, theme, or
template edits, re-bundle affected generated HTML files first (so bundled
decks carry the new runtime, not a stale one), then run
`./scripts/validate_runtime_contract.py` (repo-wide; see Runtime Contract) —
a required pass for those edits, not a fallback — then re-run the gate:

```bash
python3 scripts/bundle_deck.py assets/decks/<slug>/<slug>-slides.html --in-place --force
./scripts/validate_runtime_contract.py
python3 scripts/deck_doctor.py assets/decks/<slug>/<slug>-slides.html assets/decks/<slug>/<slug>-slide-spec.md
```

Debugging only, one check at a time: `python3 scripts/validate_deck.py <deck.html> <spec.md>`,
`git diff --check` (skill-package CI checks live in `README.md`).

When changing browser behavior, run a browser smoke test for navigation, theme
visuals, and controls.

## Partial Regeneration (editing an existing deck)

The only sanctioned editing path is regenerating from an edited spec — never a
WYSIWYG-style hand-edit of the bundled HTML. When a spec change is small
(one or a few Slide Map rows), regenerate only the affected
`<section class="slide">` blocks instead of rebuilding the whole deck.

**Step 1 — Identity.** A slide's identity is its Slide Map row **index,
confirmed by title** (no stable `data-slide-id`; none exists in this repo).
Diff the edited spec against the prior spec to find which row(s) changed,
then confirm by title that the row at that index in the current deck HTML is
the same slide before touching it.

**Step 2 — Regenerate only the changed sections.** Re-emit just the
`<section class="slide" id="slide-N">…</section>` block(s) for the changed
row(s), following the same spec → deck markup contract used to generate the
deck originally (components table, speaker notes as the last child, etc. —
see Build Guidance). Leave every other `<section>` byte-for-byte untouched.

**Step 3 — Re-bundle only if shared runtime was touched.** A content-only
edit (Key Content, copy, a chart's data) never touches
`assets/shared/` or `assets/templates/`, so no re-bundle is needed. If the
edit also required a shared runtime or template change, re-bundle per
Validate above before gating.

**Step 4 — Gate (the safety net).** Slide-count parity (Slide Map rows ==
`<section class="slide">` count, checked by `validate_deck.py`) plus a full
`deck_doctor.py` exit 0 are what make a partial regen safe without stable
IDs or a diff script:

```bash
python3 scripts/deck_doctor.py assets/decks/<slug>/<slug>-slides.html assets/decks/<slug>/<slug>-slide-spec.md
```

Non-zero exit → the partial edit broke something; fix and re-gate. Do not
ship a partial regen with a failing gate — same standard as a full build.

**Worked example (`assets/examples/rag-vector-graph/`):** Slide Map row 15 is
"Retrieval benchmark" (Content, BAR bar-chart — keyword vs vector vs hybrid
recall@10). Editing only that row's Key Content in
`rag-vector-graph-slide-spec.md` and applying this workflow means: locate row
15 by index, confirm the title on the 15th `<section class="slide">` block in
`rag-vector-graph-slides.html` matches "Retrieval benchmark", regenerate only
that section, skip the re-bundle (a Key Content edit does not touch shared
runtime), then run `deck_doctor.py` on the deck/spec pair — the HTML diff is
confined to the 15th `<section>`, slide-count parity holds (20 == 20), and
the gate exits 0.

**Revisit trigger:** if partial regens become frequent enough to justify an
automated diff script, a stable `data-slide-id` attribute becomes a
prerequisite for that script — until then, index+title is sufficient and
adding IDs now would be premature (YAGNI).

## Distribute (PDF, OG cover, handout)

Three CLI scripts turn a bundled, gate-passing deck into shareable artifacts.
All are Python, use the same Playwright Chromium as `validate_layout.py` (no
second browser stack), and require `pip install playwright && playwright
install chromium` (see `scripts/requirements.txt`) — they degrade with a
clear message, not a crash, when Playwright is absent.

```bash
python3 scripts/export_pdf.py assets/decks/<slug>/<slug>-slides.html
python3 scripts/og_cover.py assets/decks/<slug>/<slug>-slides.html
python3 scripts/export_handout.py assets/decks/<slug>/<slug>-slides.html
```

- `export_pdf.py`: drives the deck's own `?print-pdf=1` layout headlessly —
  one slide per 16:9 landscape page, selectable text, backgrounds printed.
  Writes `<slug>.pdf` next to the deck.
- `og_cover.py`: screenshots slide 1 at 1200×630 in normal (non-print) mode.
  Writes `og-cover.png` next to the deck — the exact filename
  `bundle_deck.py` rewrites `og:image` to. Replaces the removed
  `og-cover.sh`, which probed for a system Chrome install; there is now a
  single browser path across validation and export.
- `export_handout.py`: stdlib-only (`html.parser`, no browser) — emits one
  `## Slide N — <title>` Markdown section per `<section class="slide…">`,
  with that slide's `<aside class="notes">` body. Writes `<slug>-handout.md`.

## Inspectable example

`assets/examples/rag-vector-graph/` ships a real, gate-passing deck (20
slides, 12 of the 14 catalog components, authored Mermaid diagrams) with its
`-slide-spec.md` — both tracked in git (unlike `assets/decks/`, which is
gitignored working output). Read it to see the spec → deck → speaker-notes
contract in a finished deck before generating your own.
