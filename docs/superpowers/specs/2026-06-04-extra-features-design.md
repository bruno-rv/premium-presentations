---
name: premium-presentations-extra-features
description: Extra features (live presenter + distribution + viewer) for the Premium Presentations framework
metadata:
  type: project
---

# Premium Presentations — Extra Features Design

**Goal:** Add 12 high-leverage features (live presenter tools + distribution/viewer) to the existing vanilla HTML+JS single-file slide framework.

**Architecture:** Ship as small, isolated modules in `shared/`, wired in by `premium-base.html` so the `bundle_deck.py` bundler inlines them automatically. No build step, no new runtime dependency on a bundler — every feature is loaded by `<script>` tag in source `.linked.html`, inlined into standalone `.html` by the existing bundler. New CSS goes into one consolidated `premium-extras.css`. Theme tokens reused from `premium-themes.css` so all 3 themes (Editorial, Warm, Red) work without changes.

**Tech Stack:** Vanilla JS, Web Audio API, BroadcastChannel, Web Speech API, Wake Lock API, MediaRecorder, SnapDOM (lazy CDN for export), WebHID, View Transitions API. ~1100 LOC across 5 new JS files + 1 new CSS file + patches to 2 existing files + patches to 1 template.

---

## Scope

12 features across 2 clusters, shipped as one suite:

**Cluster A — Live Presenter (5 features):**
- A1. Speaker timer with audio bell (5/2/1 min warnings)
- A2. Blackout / curtain (`B` key, single CSS overlay)
- A3. Presenter view (dual-screen popup with notes + peek + timer)
- A4. Wake lock + pace estimate ("2 min left" warning)
- A5. Clicker / WebHID remote (with keyboard fallback for clickers that emit PageUp/PageDown)

**Cluster B — Distribution & Viewer (7 features):**
- B1. Share-link upgrade — `pushState` + `popstate` (current implementation uses `replaceState`)
- B2. OG / Twitter card meta — static `<head>` block + auto-generated cover PNG
- B3. TTS read-aloud (Web Speech API)
- B4. PDF print-CSS export (`?print-pdf` query + print button)
- B5. PNG export (lazy-load SnapDOM, one-click batch)
- B6. Search / Cmd+K palette (MiniSearch index, fuzzy + prefix)
- B7. Embed mode (iframe `?embedded` flag + postMessage API + `ResizeObserver` height sync)

**Out of scope (deferred):** MediaRecorder (heavy, 3/5 effort, niche), AI speaker coach (vendor-prefix + microphone UX), Hypothesis annotations (third-party dep), PWA/service-worker (Blob-URL trick is non-obvious for single-file), RSS feed (low ROI), i18n, citations, Markdown export, speaker analytics. Each gets a one-line note in `TODO.md` for future work.

---

## File structure

**New files (5 JS + 1 CSS + 1 script):**

```
shared/
  premium-timer.js          # A1, A4 — countdown + bell + pace estimate + wake lock
  premium-presenter.js      # A3 — popup presenter view, BroadcastChannel spine
  premium-clicker.js        # A5 — WebHID + keyboard clicker binding
  premium-tts.js            # B3 — Web Speech read-aloud
  premium-search.js         # B6 — Cmd+K fuzzy search palette
  premium-extras.css        # All new styles (A2, A3, B3, B4, B5, B6, B7 UI)
  premium-og-cover.js       # B2 — auto-render slide-1 PNG as OG cover via SnapDOM

scripts/
  export-deck.sh            # B4, B5 — one-shot PDF + PNG export via headless run
```

**Patched files (3):**

```
shared/slide-engine.js      # B1 pushState/popstate; embed-mode flag; postMessage emit
shared/premium-controls.js  # A1 timer button, A2 curtain button, B3 tts button, B4 print button
templates/premium-base.html # A1+A2+B3+B4 UI buttons; B2 og meta; B7 embed mode CSS hook
```

**No patches to:** `bundle_deck.py` (auto-inlines anything in `shared/` linked by the template), validators (structurally compatible), themes (re-uses existing tokens), or existing decks (their structure unchanged — but the new `premium-extras.css` link is auto-added on next re-bundle via the template).

---

## Module boundaries

Each new JS file follows the same pattern: IIFE with `window.PremiumXxx = { … }` public surface, init bound to `premium-controls-ready` event, prefers-reduced-motion guard, theme tokens via CSS variables, cleanup on `premium-theme-change` where applicable.

**Inter-module communication:** Only via `BroadcastChannel('premium-deck:state')`. Channel contract:
- `{ type: 'slidechange', index, id, title }` — emitted by SlideEngine
- `{ type: 'tick', elapsedMs, remainingMs, paceMs, paceStatus }` — emitted by Timer
- `{ type: 'bell', threshold }` — emitted by Timer
- `{ type: 'curtain', on }` — emitted by Presenter
- `{ type: 'control', action }` — emitted by Presenter, listened by SlideEngine

All consumers in the same window receive their own messages (so presenter popup and main window stay in sync). The channel name includes `premium-deck:` namespace to avoid colliding with other channels on the same origin.

---

## Feature specs (concise)

### A1 + A4 — Speaker timer + bell + pace

**File:** `shared/premium-timer.js` (~200 LOC)

**UI:** Small fixed panel at top-right, below controls. Shows `mm:ss` countdown, color states (green > 5min, amber 2–5min, red < 2min, flashing < 30s).

**API:** `window.PremiumTimer.set(minutes)`, `.start()`, `.pause()`, `.reset()`. Persists state in `sessionStorage` so refresh doesn't reset.

**Bell:** Web Audio API, 3 patterns: low-high (5min), high-low (2min), high-high-high (1min). Generated via `OscillatorNode` + `GainNode` envelope. No audio file to ship.

**Pace estimate:** Rolling average of last 5 slide dwell times. Display "On pace" / "Behind — skip a slide" / "Ahead — slow down" below the timer. Emits `tick` message on BroadcastChannel.

**Wake lock:** `navigator.wakeLock.request('screen')` on first start; re-acquire on `visibilitychange`. Silent fallback for unsupported browsers.

**Shortcut:** `Shift+T` starts/pauses timer.

### A2 — Blackout / curtain

**File:** inline in `premium-extras.css` (~30 LOC CSS) + 5 LOC in `premium-controls.js` to wire button

**UI:** Fixed `::before` overlay at `z-index: 9999`, black, pointer-events: none so the speaker still gets slide-change events. Two modes: full blackout (default) and "Returning in N min" message (custom string via right-click on the curtain button).

**Shortcut:** `B` key + `.` (reveal.js convention).

### A3 — Presenter view

**File:** `shared/premium-presenter.js` (~400 LOC)

**Trigger:** "Presenter" button in control panel OR `Shift+P` shortcut.

**UI:** Opens `window.open(location.href, 'presenter', 'popup,width=1280,height=720,left=screen.width')` — the popup is the same deck URL, but with `?presenter=1`. Inside the popup, `premium-presenter.js` reads the flag, swaps the layout to a 3-column presenter view:

```
┌─────────────────────────────────────────────┐
│  CURRENT SLIDE  │  NEXT SLIDE  │  TIMER     │
│   (large)       │  (peek)      │  + NOTES   │
│                 │              │            │
└─────────────────────────────────────────────┘
```

**Sync:** `BroadcastChannel('premium-deck:state')`. The main window emits `slidechange`; the popup listens and updates its current-slide display. The popup emits `control:next|prev`; the main window listens and runs the SlideEngine nav. Bidirectional.

**Notes:** Author attaches notes per slide as `<aside class="notes">…</aside>` inside `<section>`. Engine reads it and renders in the popup's notes column. If no notes, show a "No notes for this slide" placeholder.

**Cross-window fallback:** If popup is blocked, fall back to in-page overlay (`.premium-presenter-overlay` toggled with `Shift+P`).

### A5 — Clicker / WebHID

**File:** `shared/premium-clicker.js` (~150 LOC)

**Behavior:** On `Shift+C` (or first user gesture in control panel), prompt the user to select a device. Use WebHID — request devices with `usagePage === 0x0C` (Consumer Control). Map `0xB5` (Scan Next Track) → next, `0xB6` (Scan Previous Track) → prev, `0xCD` (Play/Pause) → toggle laser.

**Keyboard fallback:** Most clickers register as keyboards and emit `PageDown` / `PageUp` / `Right` / `Left`. Wire those to nav if WebHID is unavailable. Most users will never need WebHID; the keyboard fallback is the real feature.

**UI:** Small "Clicker" toggle button. Status indicator: "Connected: Logitech R400" / "Click any key on the clicker to bind" / "No device — keyboard fallback active."

### B1 — Share-link upgrade

**File:** patch `shared/slide-engine.js` (~40 LOC)

**Behavior:** Replace `history.replaceState` with `history.pushState` on each slide change. Add `popstate` listener that goes to the slide matching the new hash. Falls back to `replaceState` if `pushState` throws (file:// contexts).

### B2 — OG / Twitter card

**File:** template patch in `templates/premium-base.html` (~20 LOC) + `shared/premium-og-cover.js` (~80 LOC)

**Static meta:** Inject into `<head>`:
```html
<meta property="og:type" content="article">
<meta property="og:title" content="{{TITLE}}">
<meta property="og:description" content="Premium Presentations deck">
<meta property="og:image" content="og-cover.png">
<meta name="twitter:card" content="summary_large_image">
```

**OG cover generation:** A small `premium-og-cover.js` runs on `DOMContentLoaded`, captures slide 1 at 2× DPR via SnapDOM (lazy CDN), writes it to `og-cover.png` via `anchor.download`. Author runs `./scripts/og-cover.sh <deck>` once to generate and commit the PNG.

**Out of build:** This is a one-shot script, not part of every bundling. PNG is checked in.

### B3 — TTS read-aloud

**File:** `shared/premium-tts.js` (~80 LOC)

**UI:** "Listen" button in control panel. When active, highlights the current sentence (via `<mark>` injection on `onboundary` event) and reads aloud.

**API:** `window.PremiumTts.play()`, `.pause()`, `.stop()`, `.next()`. Auto-advances to next slide on `onend`.

**Chrome quirk:** Auto-stops every ~60s of silence. Patch: re-trigger `speak()` on `onend` if `autoPlay` is set.

**Shortcut:** `Shift+R` toggles.

### B4 — PDF export (print-CSS)

**File:** `shared/premium-extras.css` (~50 LOC) + button in `premium-controls.js` (~10 LOC)

**CSS:** When `<body class="print-pdf">` is set (added by `?print-pdf` query or "Export PDF" button):
- `@page { size: 1280px 720px; margin: 0 }`
- `.deck { overflow: visible; scroll-snap-type: none; height: auto }`
- `.slide { height: 720px; page-break-after: always }`
- Hide controls / dots / progress / 3D bg

**Button:** "Export PDF" sets `body.classList.add('print-pdf')` and calls `window.print()`. After print dialog, removes the class.

**Standalone use:** User can also open `deck.html?print-pdf` directly to skip the button.

### B5 — PNG export

**File:** `shared/premium-og-cover.js` extends to full deck export (~120 LOC total)

**UI:** "Export PNG" button. On click, lazy-loads SnapDOM (CDN, ~10 KB), captures each slide sequentially, downloads as a ZIP of PNGs OR single multi-page PNG.

**Simpler v1:** Just exports slide 1 (the OG cover use case) and surfaces a "Open in browser print dialog for full deck PDF" hint for the rest.

### B6 — Search / Cmd+K palette

**File:** `shared/premium-search.js` (~250 LOC) — depends on `minisearch` (CDN, 8 KB)

**UI:** Full-screen overlay on `Cmd+K` / `Ctrl+K` / `/`. Top input, scrollable result list. Each result shows slide number + title + first 80 chars of body.

**Index:** Built on `DOMContentLoaded` from all slide titles (`data-nav-title`, `slide__heading`, `slide__display`, `slide__label`, body text). Re-indexed on `premium-theme-change` (rare).

**Behavior:** Arrow keys navigate, Enter jumps, Esc closes. Fuzzy match score is the only ranking signal; ties broken by slide index.

**Shortcut:** `Cmd+K` / `Ctrl+K` / `/`.

### B7 — Embed mode

**File:** patches to `slide-engine.js` (~50 LOC) + `premium-extras.css` (~30 LOC)

**Activation:** Inside the deck, on `DOMContentLoaded`, check `window.self !== window.top` OR `?embedded=1` query. If true, set `data-embedded="true"` on `<html>`.

**Behavior:**
- Hide dot rail, progress bar, controls panel (CSS only — set `display: none` on `.deck-dots`, `.deck-progress`, `.premium-controls-shell` when `[data-embedded]`).
- Listen for `postMessage({type: 'goto', index})` from parent.
- Emit `postMessage({type: 'slidechange', index, id, title})` to parent on every change.
- Send `{type: 'resize', height}` to parent on `ResizeObserver` callback.

**API doc:** Include an embed snippet in the README:
```html
<iframe src="deck.html" style="width:100%;aspect-ratio:16/9;border:0"
  id="deck-frame"></iframe>
<script>
  document.getElementById('deck-frame').contentWindow
    .postMessage({type: 'goto', index: 0}, '*');
</script>
```

---

## Cluster-A shortcut map (consolidated)

| Key | Feature |
|-----|---------|
| `B` / `.` | Curtain toggle |
| `Shift+T` | Timer start/pause |
| `Shift+P` | Presenter view |
| `Shift+C` | Clicker bind |
| `Shift+R` | TTS read-aloud |

## Cluster-B shortcut map

| Key | Feature |
|-----|---------|
| `Cmd/Ctrl+K` / `/` | Search palette |
| `Shift+E` | Export menu (PDF / PNG) |

Existing shortcuts (`M`, `L`, `C`, `H`, `T`, `3`, arrows, space) preserved.

---

## Demo on 4 existing decks

After the new files ship, the 4 existing decks get re-bundled via `./scripts/bundle-deck.sh … --in-place` so the new `premium-extras.css` link (added by the patched `premium-base.html`) is inlined. **No content edits needed** — all new features activate from the shared engine. Demo deck: also add 1-2 light-touch slide additions to show new features working (e.g., a speaker-notes aside in one slide of the RAG deck to demo the presenter view).

---

## Testing strategy

- **Manual smoke tests** documented in `docs/superpowers/plans/2026-06-04-extra-features-plan.md` (each task has explicit test steps).
- **No unit tests** — vanilla JS in DOM, no test runner exists in this repo. Validators (`validate-deck.sh`, `validate_layout.py`, `validate_diagrams.py`) continue to pass.
- **Browser coverage:** Chrome + Edge + Firefox. Safari where possible. WebHID, Wake Lock, BroadcastChannel flagged as Chrome/Edge-first.

---

## Risks

- **R1 (mitigated):** Bundle size growth. Estimate: ~50 KB minified for all new JS + ~15 KB CSS. Within reason for single-file deck.
- **R2 (mitigated):** Popup blocker for presenter view. Fallback: in-page overlay.
- **R3 (accepted):** Firefox no WebHID / Wake Lock. Graceful no-op, status indicator shows "not supported."
- **R4 (accepted):** MiniSearch adds 8 KB to bundle. Worth it.
- **R5 (mitigated):** Existing decks must re-bundle. One-shot `./scripts/bundle-all-decks.sh` does it.
- **R6 (mitigated):** Cross-window BroadcastChannel doesn't work cross-device. Real-time multi-user remote needs a relay (out of scope, defer).

---

## Open questions for reviewer

1. **Presenter view: popup vs in-page?** Spec picks popup with in-page fallback. OK?
2. **OG cover: PNG committed to repo, or generated on first bundle?** Spec picks committed. OK?
3. **TTS: out of the box or opt-in?** Spec makes it opt-in via a control panel button. OK?
4. **Search: include in base bundle, or only when ≥ N slides?** Spec: always on, MiniSearch cost is small. OK?
