---
name: premium-presentations
description: >-
  Generate, edit, validate, and bundle complete HTML slide decks using the
  Premium Presentations repository: SlideEngine navigation, dynamic theme
  discovery, theme visuals, presenter mode, timer, annotations, search, TTS,
  clicker support, OG covers, Mermaid/diagram tooling, and reusable creative
  components. Use when creating or modifying any presentation, slide deck,
  talk, lecture, workshop, pitch, or browser-rendered HTML deck.
---

# Premium Presentations

Use this skill to create production HTML decks from the repo, not from memory.
Prefer repo scripts and shared runtime modules over hand-rolled deck engines.

## Repo Setup

1. Work from the Premium Presentations repo root. If the repo is not the current
   workspace, locate it via the user-provided path or `PREMIUM_PRESENTATIONS_REPO`.
2. Discover themes dynamically:

```bash
./scripts/list-themes.py
```

Never treat the current theme names as a closed list. Themes are declared by
`html[data-theme="..."]` selectors in `shared/premium-themes.css`. If
`templates/<theme>-base.html` exists, the scaffold script uses it; otherwise it
falls back to `templates/premium-base.html`.

## Create A Deck

```bash
./scripts/new-deck.sh <theme> <slug> "<title>" <slide_count>
./scripts/validate-deck.sh decks/<slug>/<slug>-slides.html decks/<slug>/<slug>-slide-spec.md
```

For unspecified themes, use the first theme returned by `list-themes.py` unless
the topic clearly calls for another discovered theme. Use lowercase hyphenated
slugs.

For 8+ slides, use the generated slide spec as the contract. Fill content in the
HTML deck, keeping one main idea per slide and using shared components for
layout.

## Required Runtime

New decks must keep the shared runtime included by the templates:

- `premium-themes.css`: theme tokens discovered from CSS selectors.
- `premium-deck.css`: slide layout, title/divider visual injection, dot nav.
- `premium-components.css`: compare, journey, timeline, cards, bars, code panes.
- `premium-diagrams.css` and `premium-mermaid.js`: diagram slides and fit checks.
- `premium-controller.js`: shared deck state, presenter events, and navigation API.
- `premium-controls.js`: theme switch, parallax, curtain, theme visuals.
- `premium-annotations.js`: marker and laser tools.
- `premium-timer.js`, `premium-presenter.js`, `premium-search.js`,
  `premium-clicker.js`, `premium-tts.js`, `premium-og-cover.js`.
- `premium-journey.js`: opt-in runtime for `.journey-stage` SVG path slides.
- `slide-engine.js`: scroll-snap navigation, counters, auto-hiding dot rail,
  presenter events, keyboard/touch navigation.

## Theme Visuals

Theme visuals are theme-level, not deck-specific.

- Title slides (`.slide--title`) get a `hero` visual.
- Divider slides (`.slide--divider`) get a `map` visual.
- Default asset convention: `shared/assets/chatgpt-theme-visuals/<theme>-hero.png`
  and `<theme>-map.png`.
- Override per deck with `data-theme-visual-<theme>-<role>` attributes or
  `window.PremiumThemeVisuals`.
- Disable on a slide with `data-theme-visual="off"`.

When adding a new theme, add its `html[data-theme="new-theme"]` token block,
optional `templates/new-theme-base.html`, and optional visual assets using the
same naming convention. Load custom webfonts through the template `<link>` tags
or `data-theme-fonts-<theme>="https://..."` on `<html>`. Do not update skill
prose just to add a theme.

## Build Guidance

- Start from `new-deck.sh`; do not create a parallel deck scaffold.
- Use `components.md` only when choosing advanced visual blocks.
- Use `reference.md` for runtime details and extension points.
- Use `examples.md` for copy-paste slide markup.
- Keep branding generic unless the user explicitly requests brand chrome.
- Do not add closing footer-note rows, "NEXT:" citations, or lesson-pill rows.
- Use icons/controls already provided by the shared runtime rather than adding
  ad hoc UI controls.

## Validate

Run validation before completion:

```bash
./scripts/validate-runtime-contract.py
./scripts/validate-deck.sh decks/<slug>/<slug>-slides.html decks/<slug>/<slug>-slide-spec.md
git diff --check
```

For shared runtime or template edits, re-bundle affected generated HTML files
and rerun the runtime contract:

```bash
python3 scripts/bundle_deck.py decks/<slug>/<slug>-slides.html --in-place --force
./scripts/validate-runtime-contract.py
```

Then run a browser smoke test for navigation/theme visuals when the change
touches runtime CSS/JS.
