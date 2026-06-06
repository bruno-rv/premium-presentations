---
target: "presentation themes: shared/premium-themes.css + templates + decks"
total_score: 25
p0_count: 0
p1_count: 3
timestamp: 2026-06-06T16-00-22Z
slug: n-themes-shared-premium-themes-css-templates-decks
---
# Impeccable Theme Critique: Premium Presentations

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Deck progress, dots, counter, and hints are present, but mobile controls become tiny. |
| 2 | Match System / Real World | 3 | The presentation metaphors mostly fit, especially progress and presenter controls. |
| 3 | User Control and Freedom | 3 | Theme cycling and controls work, but global localStorage theme restore can override a deck's intended default. |
| 4 | Consistency and Standards | 2 | Source tokens, raw templates, and bundled decks drift from one another. |
| 5 | Error Prevention | 1 | The studio index links to raw templates that render unstyled because placeholders remain unresolved. |
| 6 | Recognition Rather Than Recall | 3 | Labels and deck cards are clear; control shortcuts are exposed. |
| 7 | Flexibility and Efficiency | 3 | Keyboard shortcuts, theme switching, presenter tooling, and bundling support expert use. |
| 8 | Aesthetic and Minimalist Design | 2 | The system has a clear mood, but several AI-tell patterns remain: side-tabs, gradient text, dark glow, overused fonts. |
| 9 | Error Recovery | 2 | Validation scripts exist, but broken preview links and theme override behavior are not surfaced in UI. |
| 10 | Help and Documentation | 3 | README and app copy are practical; theme behavior could be documented more explicitly. |
| **Total** | | **25/40** | **Useful system, but theme delivery needs hardening.** |

## Audit Health Score

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2 | Contrast is mostly fine, but red accent on white is only 3.96:1 and mobile controls are below 44px. |
| 2 | Performance | 2 | Detector found layout-property transitions; grain, blur, and glow are used broadly. |
| 3 | Responsive Design | 2 | Decks avoid page-level horizontal overflow, but title blocks are tight and controls are too small on mobile. |
| 4 | Theming | 2 | Tokens exist, but raw templates break when opened and localStorage can mask source defaults. |
| 5 | Anti-Patterns | 2 | Impeccable found 68 findings across the primary target set. |
| **Total** | | **10/20** | **Acceptable, with significant theme QA issues.** |

## Anti-Patterns Verdict

Does it look AI-generated? Partly. The core deck system is more distinctive than a generic SaaS template: dark editorial, warm signal, and white/red broadcast all have coherent intent. The problem is repetition and residue. Fraunces, Instrument Serif, Montserrat, gradient text, side-tab borders, dark glow, grain, and repeated numbered act dividers appear across generated outputs often enough that the system starts to read like a house style built from current AI defaults.

Deterministic scan on primary templates, primary decks, and app index returned 68 findings:

- overused-font: 29
- side-tab: 15
- layout-transition: 11
- em-dash-overuse: 4
- numbered-section-markers: 4
- dark-glow: 2
- gradient-text: 2
- single-font: 1

Key source examples:

- `templates/premium-base.html:2` and `templates/red-base.html:2` contain `{{THEME}}`; `:10` links use `{{SHARED}}`, so direct previews fail.
- `assets/studio/index.html:66` and `assets/studio/index.html:78` link directly to raw templates.
- `shared/premium-themes.css:153-173` uses gradient-clipped ghost numerals in red dividers.
- `shared/premium-themes.css:342-347` uses red/silver side-tab borders on compare callouts.
- `shared/premium-deck.css:63-66` transitions progress width; `:85-98` transitions max-width for dot labels.

Visual overlay was skipped because the current Codex Browser page-evaluation surface is read-only for mutation, so Impeccable's live detector script could not be injected reliably. Browser screenshot also failed twice with `Page.captureScreenshot` timeouts, so visual evidence came from rendered DOM, computed styles, and detector output.

## Overall Impression

The themes are directionally strong but not yet impeccable. They have enough identity to be worth keeping, especially the red theme's broadcast premise and the warm theme's serious technical mood. The biggest opportunity is to separate intentional presentation language from leftover generated tropes, then make preview and theme-switch behavior deterministic.

## What's Working

- The token surface is clear: `editorial`, `warm`, and `red` each define background, surface, text, accent, semantic colors, code colors, progress gradient, and font roles in `shared/premium-themes.css`.
- Theme visuals are real image assets and load correctly in generated decks; the red and warm hero images reported valid natural dimensions in the browser.
- Presentation UX is unusually complete: controls, marker, laser, timer, presenter view, search, TTS, export, and keyboard shortcuts give the framework a real tool surface.

## Priority Issues

**[P1] Raw template links render broken previews**

Why it matters: the studio app promises "New deck template" and "Red template", but those links open unresolved template files. In browser evidence, both rendered as unstyled Times pages with empty CSS variables because `{{THEME}}`, `{{TITLE}}`, and `{{SHARED}}` remain literal.

Fix: point the studio cards to generated preview decks, or add static preview HTML files with concrete `data-theme`, title, and shared paths. Keep raw templates out of the clickable gallery.

Suggested command: `/impeccable harden assets/studio/index.html`

**[P1] Theme state is global when deck intent should often be local**

Why it matters: `shared/premium-controls.js:516-525` restores `localStorage["premium-theme"]` and can override a deck's source `data-theme`. A red-specific deck can load warm/editorial for a returning presenter, which is dangerous for branded decks and confusing for QA.

Fix: make theme restore opt-in per deck, namespace by pathname, or respect a deck-level lock such as `data-theme-lock="red"`.

Suggested command: `/impeccable harden shared/premium-controls.js`

**[P1] Touch targets are too small on mobile**

Why it matters: mobile evidence showed controls at 21-23px tall and dot buttons at 0 or 7-10px rendered size. Even if mobile is not the main presentation mode, authors will preview decks on phones and tablets.

Fix: add a mobile control mode with 44px minimum interactive targets, or collapse tools behind one 44px panel trigger and use larger rows inside the panel.

Suggested command: `/impeccable adapt shared/premium-deck.css`

**[P2] The theme system repeats AI-tell motifs**

Why it matters: side-tab borders, gradient text, numbered act dividers, dark glows, and reflex fonts make decks feel more generated over time, especially at contact-sheet scale.

Fix: keep one signature motif per theme and remove the rest. For red, replace side-tab callouts with full-frame broadcast panels or top-bar metadata. For warm, reduce Fraunces monoculture with a stronger body/display split.

Suggested command: `/impeccable polish shared/premium-themes.css`

**[P2] Large titles are close to clipping**

Why it matters: browser evidence found H1 blocks with `scrollH > clientH` at 1280x720 and mobile. This is small now, but it will break with longer real talk titles.

Fix: relax `.slide__display` line-height from `0.95`, lower the max clamp, or add a title-fit class/token that can be applied by scaffolded decks.

Suggested command: `/impeccable typeset shared/premium-deck.css`

## Persona Red Flags

**Technical speaker preparing a deck five minutes before a talk**: clicks "New deck template" in the studio and sees an unstyled placeholder page. Trust drops immediately because the advertised starting point does not behave like a preview.

**Returning presenter using a branded red deck**: previously selected warm or editorial in another deck, then opens a red deck and may see the persisted global theme instead of the deck's intended brand state.

**Mobile reviewer checking slides from a phone**: content largely fits, but controls and dots are too small to operate comfortably. The framework feels desktop-only even though the pages are technically responsive.

## Minor Observations

- Body/dim text contrast is mostly solid: editorial dim on bg is 4.60:1, warm dim on bg is 6.78:1, red dim on white is 6.05:1.
- Red accent on white is 3.96:1, acceptable for large text but risky for small labels or thin strokes.
- `shared/premium-deck.css:12-19` uses a full-page turbulence grain overlay. It can be intentional, but combined with glow and blur it pushes toward decorative texture.
- Generated decks include many em dashes; Winston-style presentation copy should be tighter and more claim-driven.

## Questions to Consider

- Should theme choice be a persistent user preference, a per-deck preference, or locked by the deck author?
- Are raw templates meant to be human-clickable previews, or only scaffold inputs?
- Which motif is the red theme's real signature: broadcast bars, ghost numerals, red side-tabs, or gradient typography? Keeping all four weakens it.
- Does warm need to stay all-Fraunces, or should it gain a more durable body face for technical diagrams and tables?
