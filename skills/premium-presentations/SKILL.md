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

This directory is the shared Premium Presentations skill. Use the bundled
scripts, references, and assets from this folder instead of recreating a slide
framework from memory.

## Start

1. Capture the workspace root before locating or changing to the skill root.
   Codex should substitute the absolute skill root it discovered for
   `<absolute-skill-root>`; Claude Code supplies the equivalent path through
   `${CLAUDE_PLUGIN_ROOT}` in `commands/present-pr.md`.

```bash
workspace_root="$(pwd -P)"
skill_root="$(cd "<absolute-skill-root>" && pwd -P)"
```

   Keep `skill_root` read-only and put decks, specs, themes, and exports under
   `workspace_root`. If the current workspace is elsewhere, locate this folder
   through the skill path, the user-provided path, or `PREMIUM_PRESENTATIONS_REPO`
   before assigning `skill_root`.
2. Discover themes dynamically from the bundled registry:

```bash
python3 "$skill_root/scripts/list-themes.py" \
  --css "$skill_root/assets/shared/premium-themes.css"
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
slug="<slug>"
deck_dir="$workspace_root/assets/decks/$slug"
"$skill_root/scripts/new-deck.sh" \
  --output-dir "$deck_dir" \
  --themes-css "$skill_root/assets/shared/premium-themes.css" \
  <theme> "$slug" "<title>" <slide_count>
```

For 8+ slides, use the generated slide spec as the contract. Derive act structure
from the topic's natural phases (Narrative Arc section in the spec) — not from a
default intro/body/conclusion rhythm. Divider slides mark act boundaries.

If the hero moment requires a visual that no catalog pattern covers, invent one:
name it, describe its structure in Design Directives > Signature visual, and flag
it for catalog addition after review. Forcing a poor-fit catalog pattern is worse.

**Step 3 — Validate (hard gate)**

```bash
python3 "$skill_root/scripts/deck_doctor.py" \
  "$deck_dir/${slug}-slides.html" \
  "$deck_dir/${slug}-slide-spec.md"
```

Exit 1 → fix the reported issues in deck or spec, re-bundle if the fix touched
`assets/shared/` or `assets/templates/`, re-run. Repeat until exit 0. A deck is
not done until deck doctor exits 0 — never deliver a deck with failing
validation. `validate_deck.py` and `validate_runtime_contract.py` under
`$skill_root/scripts/` stay available for isolated debugging of one check.

Use lowercase hyphenated slugs. For unspecified themes, use the first theme
returned by `list-themes.py` unless the topic clearly calls for another
discovered theme. `$workspace_root/assets/decks/` is generated output and
ignored by git; commit a finished deck only when the user explicitly asks.

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

Run `python3 "$skill_root/scripts/validate_runtime_contract.py"` after template, theme, bundler,
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
`validate_runtime_contract.py` (repo-wide; see Runtime Contract) —
a required pass for those edits, not a fallback — then re-run the gate:

```bash
python3 "$skill_root/scripts/bundle_deck.py" \
  "$deck_dir/${slug}-slides.html" --in-place --force \
  --shared-root "$skill_root/assets/shared"
python3 "$skill_root/scripts/validate_runtime_contract.py"
python3 "$skill_root/scripts/deck_doctor.py" \
  "$deck_dir/${slug}-slides.html" \
  "$deck_dir/${slug}-slide-spec.md"
```

Debugging only, one check at a time: `python3 "$skill_root/scripts/validate_deck.py" <deck.html> <spec.md>`,
`git diff --check` (skill-package CI checks live in `README.md`).

When changing browser behavior, run a browser smoke test for navigation, theme
visuals, and controls.

## Partial Regeneration (editing an existing deck)

Use this provider-neutral CLI only for replacing existing authored slides from
an edited Slide Map. Never hand-edit an initialized baseline deck. Capture the
workspace root before locating the skill, then invoke the discovered absolute
`skill_root`; the commands work from any current directory:

The command sequence is `partial_regen.py init`, `partial_regen.py plan`,
`partial_regen.py apply`, and `partial_regen.py rollback`.

```bash
workspace_root="$(pwd -P)"
skill_root="$(cd "<absolute-skill-root>" && pwd -P)"
python3 "$skill_root/scripts/partial_regen.py" init --deck DECK --spec SPEC
python3 "$skill_root/scripts/partial_regen.py" init --deck DECK --spec SPEC --apply
python3 "$skill_root/scripts/partial_regen.py" plan --deck DECK --spec SPEC --json
python3 "$skill_root/scripts/partial_regen.py" apply --deck DECK --spec SPEC --fragment slide-3=slide-3.html
python3 "$skill_root/scripts/partial_regen.py" rollback --deck DECK --backup BACKUP_DIRECTORY
```

Initialization is explicit: run the preview first, review its assigned stable
IDs, then use `--apply`; it never runs automatically. Claude Code and Codex
read the same JSON plan and produce the same contract: one complete matching
`<section>` fragment for every changed ID, with the expected title and final
speaker notes. The CLI does not call either provider.

Supply every changed ID in a single `apply`. A successful apply preserves every
untargeted slide byte-for-byte and preserves all embedded theme-homage images.
Run `deck_doctor.py` on the resulting deck/spec pair before publication.

Use full regeneration instead for insertions, deletions, reordering, global
CSS/runtime/control changes, new glossary keys, or new conditional
capabilities. Do not hand-edit a baseline deck after initialization: section
drift exits `3`; restore a backup or fully regenerate. An apply backup restores
only the deck, intentionally leaving the edited spec so the next plan remains
accurate.

## Distribute (PDF, OG cover, handout)

Three CLI scripts turn a bundled, gate-passing deck into shareable artifacts.
All are Python, use the same Playwright Chromium as `validate_layout.py` (no
second browser stack), and require `pip install playwright && playwright
install chromium` (see `scripts/requirements.txt`) — they degrade with a
clear message, not a crash, when Playwright is absent.

```bash
python3 "$skill_root/scripts/export_pdf.py" \
  "$deck_dir/${slug}-slides.html"
python3 "$skill_root/scripts/og_cover.py" \
  "$deck_dir/${slug}-slides.html"
python3 "$skill_root/scripts/export_handout.py" \
  "$deck_dir/${slug}-slides.html"
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

## Agent-Native Extras

- **PR-to-deck workflow:** `commands/present-pr.md` defines the Claude Code
  `/present-pr` command. Codex uses the same skill source; capture
  `workspace_root` first, resolve the discovered absolute `skill_root`, and
  pass `$workspace_root/assets/decks/<slug>` to the scaffold, validator, and
  any export script. When asked to turn the current branch's PR/diff into a
  premium deck, follow that command recipe: fill the Content-First Brief
  (`references/present-pr-brief.md`) from real `git diff`/`git log`/touched-file
  content, then run the existing `new-deck.sh` → spec → generate →
  `deck_doctor.py` pipeline verbatim. No diff-to-slide bypass.
- **Brand theme generation:** keep the bundled registry read-only. Copy it to
  a workspace-owned registry once, then pass that explicit path to the theme
  generator so all built-in themes remain available:

  ```bash
  workspace_theme_css="$workspace_root/assets/shared/premium-themes.css"
  mkdir -p "$(dirname "$workspace_theme_css")"
  if [ ! -f "$workspace_theme_css" ]; then
    cp "$skill_root/assets/shared/premium-themes.css" "$workspace_theme_css"
  fi
  python3 "$skill_root/scripts/generate_theme.py" <brand-id> \
    --bg HEX --text HEX --accent HEX --surface HEX \
    --themes-css "$workspace_theme_css"
  ```

  This appends a full-token `html[data-theme="<brand-id>"]{…}` block to the
  workspace registry, discoverable by `list-themes.py` like any built-in
  theme. Fail-closed: a palette that fails the WCAG contrast gate is rejected
  and nothing is appended. See `references/runtime.md` for the derivation and
  gated pairs.
- **Contrast gate:** `deck_doctor.py` composes `scripts/validate_contrast.py`
  as a 5th section — a repo-wide WCAG check over every theme block in
  `premium-themes.css`. Run standalone with `python3 "$skill_root/scripts/validate_contrast.py"`.
- **LAN follow-along:** `"$skill_root/scripts/share-deck.sh" <deck.html>` falls back to
  `"$skill_root/scripts/lan-sync-server.py"` (stdlib, binds `0.0.0.0`, **no auth** —
  acceptable for a venue LAN only, do not use on an untrusted network) and
  prints a PRESENT url plus a FOLLOW url. Follow-along requires the deck be
  bundled with `data-follow` on `<html>` before sharing (see
  `references/runtime.md`); a plain deck stays inert on `file://` with no
  server and no param.

## Inspectable example

`assets/examples/rag-vector-graph/` ships a real, gate-passing deck (20
slides, 12 of the 14 catalog components, authored Mermaid diagrams) with its
`-slide-spec.md` — both tracked in git (unlike `assets/decks/`, which is
gitignored working output). Read it to see the spec → deck → speaker-notes
contract in a finished deck before generating your own.
