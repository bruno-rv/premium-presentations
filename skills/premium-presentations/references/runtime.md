# Premium Presentations — Runtime Reference

## Contents

- Shared runtime module table
- Diagram slides
- Theme discovery, visuals, and chrome
- Theme extension pattern
- Mermaid and theme changes
- SlideEngine
- File naming

## Shared runtime (`assets/shared/`)

Every generated deck carries the core modules. Conditional modules are listed
at the bottom of each table.

### CSS

| File | Role |
|------|------|
| `premium-themes.css` | `html[data-theme="..."]` CSS variables only; source of truth for discovered themes |
| `premium-deck.css` | Deck structure, slide typography, tables, KPIs, scroll chrome, controls panel, 3D parallax background |
| `premium-components.css` | Creative slide blocks: shimmer, compare-split, timeline, glass/code, journey SVG, bars, setup-flow, divider — see [components.md](components.md) |
| `premium-design-power.css` | Theme-composer output, layout variants, design-power components, data-visualization blocks, motion-profile tokens, and density badges |
| `premium-diagrams.css` | Diagram slide layout, Excalidraw-style canvas, zoom/pan viewport, Mermaid error panel |
| `premium-annotations.css` | Marker tool and laser pointer styles |
| `premium-extras.css` | Runtime chrome beyond layout: curtain, PDF export, embed mode, speaker timer pill, presenter popup UI, clicker status toast |
| `premium-red-brand.css` | Red theme only: brand bar and red mark classes |

### JS

| File | Role |
|------|------|
| `slide-engine.js` | `SlideEngine` — scroll-snap navigation and the `window.PremiumDeckControls` API; progress bar, dots (labels from heading/blockquote/cite/`data-nav-title`), counter, hints, keyboard/touch, `IntersectionObserver` for `.visible`/`.reveal`; dots auto-hide after 5s |
| `premium-controller.js` | Two-window focus-ownership state machine (`deck`/`popup`/`none`) exposed as `window.PremiumController`; presenter/clicker windows coordinate through it |
| `premium-design-power.js` | Visual Design Power API: theme composer, component playground renderers, layout variants, density analysis, motion profiles, data-viz renderers, and visual-asset audit |
| `premium-controls.js` | Theme `<select>` + live switching, theme visual injection, 3D background, curtain, controls panel DOM, non-nav keyboard shortcuts |
| `premium-annotations.js` | Marker tool + laser pointer |
| `premium-timer.js` | Speaker countdown timer, pace tracking, alerts |
| `premium-tts.js` | SpeechSynthesis read-aloud |
| `premium-search.js` | Cmd+K fuzzy slide search |
| `premium-clicker.js` | WebHID clicker support + Shift+C keyboard binding |
| `premium-og-cover.js` | PNG slide export for OG covers |
| `premium-slide-content.js` | Pure functions over slide DOM: `getTitle(slide, i)`, `getNotesHtml(slide)`, `getSummaryHtml(slide)`; shared between deck and popup |
| `premium-presenter.js` | Presenter popup lifecycle, BroadcastChannel/postMessage/localStorage bridge, presenter UI DOM, timeline, and rehearsal tracking; also carries rehearsal-run persistence (localStorage, capped 10 runs, per-slide median suggested-budget block) and teleprompter distance-reading/auto-scroll mode — both popup-local, zero transport |
| `premium-mermaid.js` | Conditional (Mermaid markup): portable local renderer with optional preloaded full Mermaid support, auto-fit, clip detection, zoom/pan, theme re-render |
| `premium-journey.js` | Conditional (`.journey-stage` markup): SVG path journey animation |
| `premium-flow.js` | Conditional (`.live-flow` markup): phase spotlight cycling over `.flow-node`/`.flow-arrow` ids from `data-flow-phases` JSON, shimmer arrow animation, banner label; pauses off-screen, static under reduced motion |
| `premium-red-chrome.js` | Conditional (red decks): brand bar + hero mark injection |
| `premium-glossary.js` | Conditional (`.term-link[data-term]` or `id="glossary"` markup): parses JSON dictionary, injects `#term-popup` modal, click/Esc/focus handlers; `window.PremiumGlossary` API |
| `premium-follow.js` | Conditional (`data-follow` attribute on `<html>`, set before bundling — an attribute trigger, not a markup-class trigger): tokenized LAN follow-along. `?present=1&room=…` POSTs the current slide id to `/slide?room=…` on every `premium:slidechange`; `?follow=1&room=…` runs a single-flight recursive poll of the same endpoint (~1500ms cadence, 1400ms abort-timeout so a stalled LAN can't pile up unresolved polls, monotonic sequence guard so a late/stale response can't navigate out of order) and navigates via `document.getElementById(id).scrollIntoView()` — the same mechanism `PremiumDeckControls.goTo()` uses (the engine binds `popstate` only, so a `location.hash` assignment would not navigate). Without a mode or room token, the module returns immediately: 0 fetch, 0 listeners, 0 timers |

Linked decks use `../../shared/…` from `assets/decks/<slug>/`.

### Diagram slides (required markup)

Use `assets/templates/diagram-slide.snippet.html`. Validator enforces:

- `slide--diagram` → `slide__diagram-header` → `diagram-stage` → `mermaid-wrap` → `<pre class="mermaid">`
- `premium-diagrams.css` + `premium-mermaid.js` (inlined when bundled)
- No `max-height: 52vh|62vh` on `.mermaid-wrap` (clips content)
- Runtime: `fitMermaidDiagrams`, `bindMermaidFit`, `bindDiagramZoom`, `reportDiagramFit`
- **Diagram zoom:** scroll/pinch on canvas, drag to pan when zoomed, toolbar **+ / − / %**, double-click reset; **`+` `−` `0`** on diagram slides

**Theme discovery:** after capturing `workspace_root` and resolving the
absolute `skill_root`, run:

```bash
themes_css="$workspace_root/assets/shared/premium-themes.css"
if [ ! -f "$themes_css" ]; then
  themes_css="$skill_root/assets/shared/premium-themes.css"
fi
python3 "$skill_root/scripts/list-themes.py" \
  --themes-css "$themes_css"
```

Or inspect `html[data-theme="..."]` selectors in the bundled registry. Do not
hardcode the current theme names in generators or skill instructions.

**Runtime contract:** run `python3 "$skill_root/scripts/validate_runtime_contract.py"` after any
template, theme, bundler, or shared runtime edit. It verifies discovered theme
scaffold templates, preview templates, and generated deck HTML files carry the
common CSS/JS stack, plus red brand modules where the active template/deck is
red, plus `premium-journey.js` when a file contains `.journey-stage` markup,
plus `premium-flow.js` when a file contains `.live-flow` markup, plus
`premium-follow.js` when `<html>` carries `data-follow`.

**Contrast gate:** `deck_doctor.py` composes `scripts/validate_contrast.py` as
the 6th section, after offline portability — a stdlib WCAG
relative-luminance/contrast-ratio check over
every `html[data-theme="…"]` block in the SOURCE `premium-themes.css`
(location-independent; not the deck's own HTML, which carries no inlined
token blocks). Gated pairs: `--text`/`--bg` and `--text`/`--surface` at 4.5:1,
`--text-dim`/`--bg` at 4.5:1, `--accent`/`--bg` at 3.0:1 (accent is
heading/UI scale, never body text). Run standalone:
`python3 "$skill_root/scripts/validate_contrast.py"`.

**Brand theme generation:** keep the bundled registry read-only. Copy it to a
workspace-owned registry once, then pass that explicit path to the generator so
all built-in themes remain available:

```bash
workspace_theme_css="$workspace_root/assets/shared/premium-themes.css"
mkdir -p "$(dirname "$workspace_theme_css")"
if [ ! -f "$workspace_theme_css" ]; then
  cp "$skill_root/assets/shared/premium-themes.css" "$workspace_theme_css"
fi
themes_css="$workspace_theme_css"
python3 "$skill_root/scripts/generate_theme.py" <brand-id> \
  --bg HEX --text HEX --accent HEX --surface HEX \
  --hero-image HERO.webp --map-image MAP.webp \
  --themes-css "$workspace_theme_css"
```

This ports `buildThemeCss` (`premium-design-power.js`) to Python and emits the
full token set the built-in themes carry (not just the JS composer's 11) so a
generated theme renders identically to a hand-authored one — progress bar, code
windows, and semantic tags included. Runs the same contrast gate at generation
time: fail-closed, persisted themes require two distinct valid WebPs, and CSS,
normalized hero/map assets, plus `theme-visuals/manifest.json` are validated
and installed transactionally against the workspace registry. A failed
replacement or final validation restores the prior registry, and nothing is
appended on a failing palette. `--dry-run` prints the block without images or
changes.

**LAN follow-along + `/present-pr`:** `share-deck.sh`'s LAN fallback serves an
isolated temporary directory containing only `index.html` via
`scripts/lan-sync-server.py` (stdlib `ThreadingHTTPServer`, binds `0.0.0.0`,
single presenter, in-memory current-slide state only). It prints a PRESENT URL
(`?present=1&room=…`) plus a FOLLOW URL (`?follow=1&room=…`) — the latter only
when the served deck was bundled with `data-follow`. The random room token is
required on every `/slide` request; do not expose this ephemeral service to the
public internet. `/present-pr` (plugin command,
`commands/present-pr.md`) turns the current branch's PR/diff into a filled
Content-First Brief (`references/present-pr-brief.md`) and runs the
existing scaffold → spec → generate → `deck_doctor.py` pipeline unchanged.
Claude resolves bundled tools from `${CLAUDE_PLUGIN_ROOT}` and writes the deck
under `${CLAUDE_PROJECT_DIR}/assets/decks/<slug>`; it never writes into the
plugin cache.

**Provider-neutral paths:** Codex captures the workspace root before locating
or changing to the skill root, then invokes the discovered absolute skill root
for every script. Keep the skill root read-only and pass the workspace-owned
deck path explicitly:

```bash
workspace_root="$(pwd -P)"
skill_root="$(cd "<absolute-skill-root>" && pwd -P)"
themes_css="$workspace_root/assets/shared/premium-themes.css"
if [ ! -f "$themes_css" ]; then
  themes_css="$skill_root/assets/shared/premium-themes.css"
fi
deck_dir="$workspace_root/assets/decks/<slug>"
"$skill_root/scripts/new-deck.sh" --output-dir "$deck_dir" \
  --themes-css "$themes_css" \
  <theme> <slug> "<title>" <count>
python3 "$skill_root/scripts/deck_doctor.py" \
  "$deck_dir/<slug>-slides.html" "$deck_dir/<slug>-slide-spec.md"
```

**Live theme switch:** `PremiumPresentations.setTheme('<theme>')` or UI control. The control panel discovers themes from loaded CSS. Dispatches `premium-theme-change` on `<html>`.

**Theme visuals:** `.slide--title` receives a `hero` visual;
`.slide--divider` receives a `map` visual. The CSS theme set must exactly equal
the keys in `assets/shared/assets/theme-visuals/manifest.json`; every entry has
exactly one distinct `hero` and `map` WebP safe basename whose file exists and
passes RIFF chunk, bounds, format, and positive-dimension probing. Bundled
standalone decks embed the complete
validated registry as `data:` URIs, so a newly generated visual deck carries
every theme's homage and updates automatically on live theme switches. There is
no filename-guess fallback. Override with `data-theme-visual-<theme>-<role>` or
`window.PremiumThemeVisuals` only when the value is a `data:image/...` URI in
standalone output; unsafe remote or sidecar paths are ignored. Disable per slide
with `data-theme-visual="off"`.

## Partial regeneration

For an existing initialized deck, use the same provider-neutral commands from
the skill root for Claude Code and Codex:

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

Initialization is always explicit: inspect the preview and assigned IDs before
`--apply`. `plan --json` carries `schemaVersion` (currently `2`), the
backward-compatible `changed` union, and two partitions: `contentChanged`
(rows needing a replacement fragment) and `budgetOnly` (rows where every
changed field is a Slide Budget column). Both providers read the JSON plan
and create one matching section fragment for each `contentChanged` ID — on a
budgeted deck the fragment must carry the row's current `data-budget`
verbatim; the CLI makes no provider call. Supply the exact complete
`contentChanged` fragment set in one apply; `apply` takes **zero
`--fragment` arguments** when every change is `budgetOnly` — those IDs sync
`data-budget` directly (body untouched) in the same transaction. The
operation preserves untouched slide bytes and the embedded WebP hero/map
theme homages, so live theme changes keep their imagery after regeneration,
and updates every affected row's embedded state so a follow-up plan reports
zero drift; run Deck Doctor before publishing.

Require full regeneration for insertion, deletion, reordering, global
CSS/runtime/control changes, new glossary keys, or a new conditional runtime
capability. Never hand-edit the initialized baseline: section drift exits `3`.

**3D modes:** **`3`** cycles `off → ambient → tilt → depth → card` (`Shift+3` backward; handled
via `e.code === 'Digit3'`, layout-safe). `data-3d="<mode>"` on `<html>` is the source
of truth; the controls panel has a `3D` select (`#premium-3d`) and a transient toast
names the mode on every change. Modes: `ambient` = cursor parallax on the background
canvas (the old `data-parallax="on"`); `tilt` = cursor-tracked tilt of the active
slide's `.slide-3d-frame` (JS-injected wrapper — the scroll-snap `.slide` is never
transformed); `depth` = auto-elevated `translateZ` tiers on the component vocabulary
inside a slide perspective, opt out per element with `data-flat`; `card` = per-element
cursor-tracked tilt ("ball on table") — each `.stat-card`, `.glass-card`, `.flow-node`,
`.kpi`, `.compare-panel`, `.setup-step`, `.pipeline-stage`, `.code-window`,
`.terminal-window`, `.checklist-item`, `.tl-col`, `.aside-card`, `.why-panel` tilts
independently up to 14° based on cursor position relative to its own center; a glare
highlight shifts via `--card-glare` CSS var on hover; smooth spring-back on
`pointerleave` via CSS transition; only mounts for fine-pointer (mouse/stylus), no-op
under `prefers-reduced-motion`; opt out per element with `data-flat`. Resolution order:
stored pref (scoped key `premium-3d:<path>`) → author `data-3d` → legacy author
`data-parallax="on"` (→ `ambient`) → `off`. The old unscoped localStorage parallax
key is intentionally ignored. API: `PremiumPresentations.set3dMode('<mode>')`,
`cycle3d(dir)`, `get3dMode()`; compat wrappers `setParallax(bool)` / `toggleParallax()`
map to `ambient`/`off` (presenter `parallax.toggle` keeps working). `data-parallax`
stays mirrored (`on` when mode ≠ `off`). All modes flatten under
`prefers-reduced-motion` and in print/PDF.

**Panel:** **`H`** hide/show; unhide pins panel open (`is-open`). **`3`** cycles 3D mode.

**Presenter rehearsal:** the popup renders a horizontal timeline from the deck
snapshot. Timeline items are clickable slide jumps, show planned per-slide time
from the active timer, and switch to actual per-slide dwell while rehearsal is
running. `R` toggles rehearsal; `Shift+R` clears the rehearsal session (the
in-memory current run only — persisted history is untouched).

**Rehearsal persistence + suggested budgets:** each rehearsal run is committed
to `localStorage['premium-rehearsal:'+location.pathname]` on pause (primary
boundary) and on popup unload (crash-safety net), capped at the last 10 runs
per deck path. On (re)open, the timeline restores per-slide actual + delta
from the most-recent run whose slide count matches the loaded deck
(mismatched-length runs are kept in history but excluded from the math). The
comparison label is exactly **"vs plan"** when the loaded deck carries valid
Slide Budgets (`readSlideBudgets()` accepts a complete, valid, uniquely
identified `data-budget` vector on the normalized DOM) or **"vs average"**
(uniform total-time-over-slide-count fallback) otherwise — one centralized
planned-time-vector + label helper routes every consumer (timeline deltas,
the status line, `getLastRunDeltas()`). A "Suggested budgets" block below the
timeline shows the per-slide **median across eligible runs** as a
copy-pasteable markdown table, **ID-keyed** (`| ID | Budget (mm:ss) | Budget
(ms) |`) when the deck has stable section IDs — pastes into the Slide Map's
`Budget` columns with zero reformat. **Sample eligibility:** a slide's median
counts only if at least one saved observation for it falls in-range (1,000 ms
– 7,200,000 ms cap) across eligible runs; if any slide lacks one, the export
refuses and names the offending slides — no silent clamping. Legacy decks
without stable IDs fall back to an ordinal+title table with an "initialize
stable IDs before merging" notice. `Export JSON` copies a versioned payload
`{v: 2, identity: "id" | "ordinal", rows: [...]}`, and `Clear history` wipes
persisted runs. Deltas render only inside `#pp-timeline` `<li>` nodes — the
timer's live pace pill (`#pp-timer-pace`) is never touched by this feature.

**Teleprompter / distance-reading mode:** `m` toggles a CSS-only
distance-reading class on the notes pane (bigger font/line-height/contrast,
reclaims the previews pane); toggling mode never starts motion. `p` is the
one and only play-intent gesture — explicit start, pause, and resume of
auto-scroll of `#pp-notes`. Defaults to paused on every load and respects
`prefers-reduced-motion: reduce` by construction: users with the OS
preference set MAY start scrolling with an explicit `p`, but no load, mode
toggle, slide change, or state restoration may ever create play intent by
itself.

**Engage rule (timed vs manual):** when the loaded deck carries a complete,
valid, uniquely-identified `data-budget` vector (`readSlideBudgets()`
accepts it on the normalized DOM), `p` drives **timed scroll** paced to each
slide's budget; otherwise it falls back to today's manual constant-px/s
auto-scroll, unchanged. `]`/`[` (via `e.code`, layout-robust) mean different
things per mode: in manual mode they nudge the px/s rate (clamped
10–240 px/s); in timed mode they nudge an integer-tenths **speed multiplier**
(10 = ×1.0, clamped [5, 20] = ×0.5–×2.0).

**Timed progress model:** `progress = accumulatedProgress + (performance.now()
− epoch) × multiplier / budgetMs`, clamped [0, 1]; `scrollTop = progress ×
(scrollHeight − clientHeight)`, read live on every tick so the target
distance is always current after notes render, mode toggle, glossary/font
settle, or resize. Notes that don't overflow never move (no division, no
motion). **Pause** (`p` again) commits the elapsed progress into
`accumulatedProgress` and clears only the epoch — position holds. **Resume**
(`p`) keeps `accumulatedProgress` and starts a fresh epoch — scroll continues
from where it stopped, no restart, no backward jump. A genuine **slide
change** zeroes `accumulatedProgress` and, while play intent is on, starts a
fresh epoch so motion continues without a new keypress — the new slide's own
budget governs pacing from that point. A **multiplier change** commits
progress under the OLD multiplier first, then rebases the epoch, so the new
rate never applies retroactively (no jump at the moment of change). Popup
close/reopen clears intent and progress (fresh module state per popup).

**Persistence:** the rate/multiplier persist in
`localStorage['premium-teleprompter']` across sessions. The schema is
versioned — `{v: 2, manualRate: number, multiplierTenths: number}` — with
transparent migration from the legacy plain-numeric-string schema (read as
`manualRate`; the next write upgrades storage to `v: 2` with no saved-rate
loss).

**Design power:** `window.PremiumDesignPower` exposes seven authoring helpers:
`themeComposer`, `components`, `layouts`, `density`, `motionProfiles`,
`dataViz`, and `assets`. Decks can set `data-motion-profile="calm|cinematic|technical|workshop|pitch"`
on `<html>`; the module applies timing CSS variables and a matching 3D default.
Set `data-density-auto="on"` to annotate slides with `data-density-level`.
Studio uses the same API for live snippet generation.

## Theme Extension Pattern

To add a theme:

1. Prefer `scripts/generate_theme.py` with `--hero-image` and `--map-image`; it
   updates CSS, normalized visuals, and the manifest transactionally.
2. Optionally add `assets/templates/<theme>-base.html` for theme-specific chrome
   (themes without one fall back to `assets/templates/premium-base.html`).
3. For a manual theme, add `html[data-theme="<theme>"]` tokens, distinct
   `<theme>-hero.webp` and `<theme>-map.webp` files, and exact hero/map entries
   in `theme-visuals/manifest.json` before running the runtime contract. An
   incomplete theme is invalid and bundling fails closed.
4. Keep font stacks portable: use system/local families. Optional runtime font
   stylesheets must be `data:text/css` URLs; remote and sidecar stylesheet
   paths are ignored by the runtime.
5. Optionally add a focused `themes-<theme>.md` reference if the theme has
   non-obvious rules.

Optional fixed **brand bar** for any theme (only if user requests custom branding):

```html
<div class="deck-bar">
  <div class="deck-bar__left">Organization</div>
  <div class="deck-bar__center">Tagline</div>
  <div class="deck-bar__right">Speaker · Year</div>
</div>
```

Use generic class names — not tied to any course product.

If a `themes-*.md` file exists for the selected theme, read it before building
theme-specific slides.

### Mermaid + theme change

`premium-mermaid.js` includes a portable local renderer for simple flowcharts.
If a deck needs full Mermaid syntax such as sequence, ER, class, or state
diagrams, preload a local bundled Mermaid object as `window.mermaid` before
calling `initPremiumMermaid()`.

```html
<script type="module">
  import { initPremiumMermaid } from '../../shared/premium-mermaid.js';
  document.addEventListener('DOMContentLoaded', async () => {
    await initPremiumMermaid();
    new SlideEngine();
  });
</script>
```

---

## SlideEngine

Prefer `assets/shared/slide-engine.js`:

```javascript
document.addEventListener('DOMContentLoaded', () => new SlideEngine());
```

`SlideEngine` builds progress bar, dots, counter, hints; handles keyboard, touch, `IntersectionObserver` for `.visible` / `.reveal`.

---

## File naming (this repo)

| Pattern | Example |
|---------|---------|
| Deck folder | `assets/decks/{slug}/` |
| HTML | `{slug}-slides.html` |
| Spec (8+ slides) | `{slug}-slide-spec.md` |

For deck anti-patterns (framework choices, branding, motion), see
[design.md](design.md).
