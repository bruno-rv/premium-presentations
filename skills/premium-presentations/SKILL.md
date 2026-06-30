---
name: premium-presentations
description: >-
  Generates, edits, validates, and bundles complete Premium Presentations HTML
  slide decks from this self-contained repository skill. Use when creating or
  modifying presentations, slide decks, talks, lectures, workshops, pitches,
  browser-rendered HTML decks, presenter-mode decks, themed decks, Mermaid
  diagram decks, or reusable presentation templates, and when bundling decks,
  adding speaker timers, annotations, OG covers, or validating deck output
  with the bundled scripts, themes, runtime, assets, and validators.
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

**Step 3 — Validate**

```bash
python3 scripts/validate_deck.py assets/decks/<slug>/<slug>-slides.html assets/decks/<slug>/<slug>-slide-spec.md
```

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
or shared runtime edits.

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

These commands verify generated deck output (skill-package CI checks live in
`README.md`). Before completion, run the checks that match the change:

```bash
./scripts/validate_runtime_contract.py
python3 scripts/validate_deck.py assets/decks/<slug>/<slug>-slides.html assets/decks/<slug>/<slug>-slide-spec.md
git diff --check
```

For shared runtime or template edits, re-bundle affected generated HTML files:

```bash
python3 scripts/bundle_deck.py assets/decks/<slug>/<slug>-slides.html --in-place --force
./scripts/validate_runtime_contract.py
```

When changing browser behavior, run a browser smoke test for navigation, theme
visuals, and controls.
