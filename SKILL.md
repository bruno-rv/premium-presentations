---
name: premium-presentations
description: >-
  Generate, edit, validate, and bundle complete Premium Presentations HTML slide
  decks from this self-contained skill repository. Use when creating or
  modifying presentations, slide decks, talks, lectures, workshops, pitches,
  browser-rendered HTML decks, presenter-mode decks, themed decks, Mermaid
  diagram decks, or reusable presentation templates with the bundled scripts,
  themes, runtime, assets, and validators.
---

# Premium Presentations

This repository root is the self-contained skill package and deck generator. Use the
bundled scripts, templates, shared runtime, assets, and references from this
folder instead of recreating a slide framework from memory.

## Start

1. Work from the directory containing this `SKILL.md`. If the current workspace
   is elsewhere, locate this folder through the skill path, the user-provided
   path, or `PREMIUM_PRESENTATIONS_SKILL`.
2. Discover themes dynamically:

```bash
./scripts/list-themes.py
```

Themes come from `html[data-theme="..."]` selectors in
`shared/premium-themes.css`. Do not hardcode the current theme names.

## Create A Deck

```bash
./scripts/new-deck.sh <theme> <slug> "<title>" <slide_count>
./scripts/validate-deck.sh decks/<slug>/<slug>-slides.html
```

Use lowercase hyphenated slugs. For unspecified themes, use the first theme
returned by `list-themes.py` unless the topic clearly calls for another
discovered theme. For 8+ slides, use the generated slide spec as the authoring
contract, then validate against it after the HTML has been expanded to the
planned slide count.

## Runtime Contract

Keep generated decks on the shared runtime stack:

- CSS: `premium-themes.css`, `premium-deck.css`, `premium-components.css`,
  `premium-diagrams.css`, `premium-annotations.css`, `premium-extras.css`.
- JS: `premium-controller.js`, `premium-controls.js`,
  `premium-annotations.js`, `premium-timer.js`, `premium-tts.js`,
  `premium-search.js`, `premium-clicker.js`, `premium-og-cover.js`,
  `premium-presenter.js`, `slide-engine.js`.
- Red decks also include `premium-red-brand.css` and `premium-red-chrome.js`.

Run `./scripts/validate-runtime-contract.py` after template, theme, bundler, or
shared runtime edits.

## Reference Files

- `references/design.md`: audience, style, anti-patterns, and deck design
  principles.
- `references/runtime.md`: runtime modules, extension points, theme visuals,
  Mermaid, presenter/chrome behavior.
- `references/components.md`: reusable visual components and snippet IDs.
- `references/examples.md`: copy-paste slide markup patterns.
- `references/themes-red.md`: red theme rules.
- `references/slide-spec-template.md`: deck planning template used by
  `scripts/new-deck.sh`.

Load only the reference needed for the current task.

## Build Guidance

- Start from `scripts/new-deck.sh`; do not create a parallel scaffold.
- Use `templates/` and `shared/` as the source of truth.
- Use `templates/components/` snippets for advanced visual blocks.
- Read `references/design.md` before large new decks or broad redesigns.
- Keep one dominant idea per slide.
- Keep branding generic unless the user explicitly requests brand chrome.
- Do not add closing footer-note rows, "NEXT:" citations, or lesson-pill rows.
- Use the provided runtime controls instead of ad hoc controls.

## Validate

Before completion, run the checks that match the change:

```bash
./scripts/validate-runtime-contract.py
./scripts/validate-deck.sh decks/<slug>/<slug>-slides.html decks/<slug>/<slug>-slide-spec.md
git diff --check
```

For shared runtime or template edits, re-bundle affected generated HTML files:

```bash
python3 scripts/bundle_deck.py decks/<slug>/<slug>-slides.html --in-place --force
./scripts/validate-runtime-contract.py
```

When changing browser behavior, run a browser smoke test for navigation, theme
visuals, and controls.
