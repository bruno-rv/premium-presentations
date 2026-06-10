# Presenter View Refactor — Plan
_Round 3 — Codex APPROVED (round 1: 11 findings; round 2: 6; round 3: 3 minor, folded in)_

Scope: `assets/shared/premium-presenter.js`, `slide-engine.js` (notes/summary extraction),
`premium-extras.css` (presenter block), `premium-controller.js` (heartbeat ingestion),
`premium-timer.js` (tick identity), generation skill (notes authoring).

## Diagnosis (verified in live browser, file://, rag-vector-graph deck)

### D1 — "Sync" bug is actually a dead notes pipeline
Index sync **works**: popup rail click / arrow keys → deck navigates → deck broadcasts
`slidechange` → popup counter, rail highlight, and next-title all update. Verified
including after deck reload + session adoption.

What never updates is the **Notes pane** — the dominant content area — so the popup
*looks* frozen. Two independent causes:

1. **No notes authored.** `getSlideNotesHtml` reads `aside.notes, .slide__notes`
   (slide-engine.js:152). The generation skill never emits these elements; no deck
   has them. Result: `''` for every slide.
2. **Summary fallback returns `''` on every real slide.** `getSlideSummaryHtml`
   (slide-engine.js:164):
   - Container allowlist `.content-grid, .slide__body, .slide__points, .slide__split,
     .slide__quote` doesn't match real deck markup (`.split`, `.why-panel`,
     `.stats-row`, `.live-flow`, `.terminal-window`, tables…). Most slides → `body = null` → `''`.
   - When `.slide__body` matches a bare `<p class="slide__body">`, the lead lookup
     `clone.querySelector('p')` searches *descendants* of that `<p>` → finds nothing → `''`.
   - The strip list removes **`.reveal`** — virtually every content node in generated
     decks carries `.reveal`. Even a matching container gets emptied.

### D2 — Popup layout is structurally broken
CSS defines grid areas on `.premium-presenter` (`"top rail / main rail / status status"`,
premium-extras.css:270) but `buildPopupDom` nests `#pp-rail` **inside**
`.premium-presenter__main` (premium-presenter.js:315–326). `grid-area: rail` on a
non-grid-child is inert → the rail renders as a clipped ~80px box *below* the notes.
Also `padding-top: 220px` / `padding-bottom: 120px` reserve space for fixed panels,
producing large dead zones.

Additionally the popup-hide CSS block targets **stale class names**
(`.progress-bar`, `.counter`, `.hints` — premium-extras.css:264–266) while the actual
deck chrome classes are `.deck-progress`, `.deck-counter`, `.deck-hints`
(premium-deck.css:78,177). Deck chrome, `premium-controls` shell, native `.premium-timer`
pill, 3D frames, and toasts can all leak into the popup window.

### D3 — Debug pollution and dead code
- **Diag bar always visible**: `updateDiag()` sets `el.hidden = false` unconditionally
  and is called from `postToPeer` on every heartbeat. The `?presenter=diag` gate is
  documented (line 49) but never checked anywhere.
- `console.log('[PP-popup] rail click …')` and `'sending control.jump …'` left in
  `bindPopupEvents` / session-adoption path.
- **Audience badge is dead code**: `showDeckBadge`/`updateDeckBadge` are declared
  *inside* `init()` (premium-presenter.js:776) but called from module-scope
  `onDeckMessage()` (lines 200, 207) inside `try{}catch(_){}` → ReferenceError swallowed
  on every message. The badge never renders.
- Status footer prints raw session id; the displayed id goes stale after session
  adoption (snapshot at build time, never re-read from `html[data-session]`).
- Timer config (mode select, minutes, end-time, 3 buttons) always expanded as a
  fixed top-right panel.

### D4 — Architecture: popup re-implements what it already has
The popup **is the deck document** (same HTML, `?presenter=1`); `#deck` is merely
`display:none`. Yet titles/notes/bodyHtmls are serialized and shipped over 3 transports
(BroadcastChannel + postMessage + localStorage) via `snapshot`/`slidechange`. Only
**index, timer state, and ownership** actually need the wire. Content can be read
locally — and this unlocks real slide previews (iframes are not an option: file://
iframes are blocked as unique origins — error observed in console).

### D5 — Transport/ownership defects (from adversarial review, verified)
- **Heartbeats only reach the controller via BroadcastChannel.**
  `premium-controller.js:109` listens on BC only; `onDeckMessage()` deliberately no-ops
  on `presenter.heartbeat` (premium-presenter.js:209). On file:// (BC unavailable)
  the deck-side owner state machine never sees the popup → `isPopupAlive()` stays
  false. Ownership is effectively broken on file:// today.
- **Script order race**: templates load `premium-presenter.js` *before*
  `slide-engine.js` (premium-base.html:50–51). `buildPopupDom()` runs at
  DOMContentLoaded and renders immediately; local-content reads must not assume
  `PremiumDeckControls` exists yet.
- **Timer ticks carry no identity**: `premium-timer.js` `post()` adds only `ts`.
  With two decks open, global-channel `tick`/`bell` bleed across popups.
- **No ordering guarantee**: the same payload arrives up to 3× across transports
  with no sequence number; localStorage can lag postMessage. Stale `slidechange`
  can overwrite fresh state.

## Refactor

### Phase 1 — Triage (small diffs, immediate relief)
1. Remove debug `console.log`s. Gate diagnostics behind a **separate `?ppdiag=1`
   param** (NOT `presenter=diag` — `isInPopup()` and the controller test
   `presenter === '1'`, so overloading the value would break popup detection).
   `updateDiag()` early-returns unless the flag is set.
2. Delete the dead audience-badge path (`showDeckBadge`/`updateDeckBadge` and call
   sites). If a connection indicator is wanted on the deck later, it's a new,
   intentionally-designed transient toast — out of scope here.
3. Fix `getSlideSummaryHtml`: clone the **whole slide** (not an allowlisted container),
   strip chrome by element kind (headings, `script/style/svg`, `.slide__label`,
   `.slide__number`, nav/dots, **and `aside.notes`/`.slide__notes`** — once notes are
   authored, the summary must not duplicate them) — **never strip `.reveal`**; extract
   lead sentences / bullets / quote / table-first-column from what remains.
   Last-resort fallback: slide title.
4. Fix popup layout: make `#pp-rail` a direct grid child of `.premium-presenter`;
   drop the 220px/120px padding reservations; timer + controls become grid rows.
5. Fix the popup-hide CSS block: target the real chrome (`.deck-progress`,
   `.deck-counter`, `.deck-hints`, `.deck-dots`, `premium-controls` shell, native
   `.premium-timer` pill, `.premium-bg-3d` background, toasts). **Never hide
   `.slide-3d-frame`** — it *wraps* slide content (premium-controls.js injects it
   inside every `.slide`); hiding it would blank Phase-2c preview clones. Instead,
   flatten its transforms under `body.premium-presenter-popup` / `.pp-preview`.
   Audit `premium-controls.js` popup gating (line 163) and suppress its shell
   mount when `presenter=1`.
6. Status footer: read session live from `html[data-session]` at render time;
   compact connection dot (green/amber) + counter instead of prose.
7. **Forward heartbeats to the controller from every transport**: `onDeckMessage()`
   calls `window.PremiumController.recordHeartbeat(msg.popupFocused)` (guarded) so
   ownership works on file://. Controller's own BC listener stays (dedupe is
   harmless — it's a timestamp refresh).

### Phase 2 — Local-first popup (incremental, compatibility first)
Principle: **sync state, not content** — but land it without breaking the wire.

1. **2a — Local-content fallback layer** (small, safe first step):
   `renderSnapshot`/`renderSlidechange` prefer locally-extracted content
   (title/notes/summary from the popup's own DOM by index) and fall back to wire
   fields when local extraction is unavailable. Local extraction lives in a **new
   shared module `premium-slide-content.js`** exposing `window.PremiumSlideContent`
   (pure functions over a slide element: title, notes, summary), loaded **before**
   `premium-presenter.js` in templates and in the bundler order (`scripts/_common.py`)
   — extractors cannot stay on `SlideEngine.prototype` because slide-engine.js loads
   *after* presenter.js. `SlideEngine` delegates to the same module (no duplicate
   logic). Register the module everywhere the runtime stack is enumerated:
   templates, `scripts/_common.py`, `references/runtime.md`, and
   `validate_runtime_contract.py`. The deck side **keeps sending** `titles/notes/bodyHtmls` — existing tests
   (`test-popup-e2e.mjs` `withSlides:false` fixtures) and any already-bundled deck
   keep working unchanged. Payload slimming happens only in 2d.
2. **2b — Ordering + identity hardening** (one shared filter, not per-type patches):
   - **Single peer/session filter in the presenter transport receive path**, applied
     to ALL message types — `ready`, `heartbeat`, `closing`, `control`, `snapshot`,
     `slidechange`, `tick`, `bell`. Explicit adoption exceptions: `presenter.discover`
     / `presenter.hereIam` (the re-pairing handshake) bypass the filter; on adoption
     the popup resets its epoch. Today `handleControl()` deliberately skips session
     checks and `onPopupMessage()` accepts everything — with two decks open, a
     popup's `next` lands on BOTH decks. Two-deck control/heartbeat tests required.
   - Deck stamps every deck-authoritative message with `sessionId` + seq from a
     **central allocator** (`PremiumPresenter.nextStateSeq()` — slide-engine and
     premium-timer publish from separate modules; independent counters would make
     one stream starve the other). Popup reducer keeps **per-kind cursors**
     (`slideSeq`, `timerSeq`) so a burst of ticks never drops a valid slidechange.
   - Heartbeat forwarding (Phase 1.7) applies the same session check the
     controller's BC listener already has (`premium-controller.js:113`).
   - `premium-timer.js` includes `sessionId` in `post()`; popup filters foreign ticks.
     In the popup, the timer module goes **fully passive** (`presenter=1` → no
     session restore, no slidechange listener, no RAF loop, no wake lock, no bell
     audio, no postTick) — presenter UI renders deck-sourced timer state only;
     gating just `postTick` would leave wake-lock/bell side effects running.
3. **2c — Layout redesign + previews** (PowerPoint-style instrument panel):
   ```
   ┌────────────────────────────┬──────────────┐
   │  CURRENT slide preview     │ NEXT preview │
   │  (large, ~55% height)      │ + next title │
   ├────────────────────────────┴──────────────┤
   │  Notes / auto-summary (large type)        │
   ├───────────────────────────────────────────┤
   │ ⏱ timer · pace │ 9/14 │ ◀ ▶ │ ⚙ │ ● conn │
   └───────────────────────────────────────────┘
   ```
   - Previews: clone the popup's local slide nodes into fixed-aspect boxes scaled
     with `transform: scale()`. **Clone sanitization is mandatory**: id handling must
     be a **rename map, not a bare strip** — ids are referenced outside `id` attrs
     (journey: `data-journey-gradient` + SVG `url(#…)`; live-flow: node/arrow ids
     inside `data-flow-phases` JSON). Build old→new map, rewrite IDREFs/`url(#id)`/
     JSON refs — or strip the dynamic layers entirely and render a static fallback
     for those components. Force `.slide`/`.reveal` visible inside a `.pp-preview`
     scope, disable animations/transitions/IO-driven runtimes via the scope class,
     set `aria-hidden="true"` and `pointer-events: none`.
   - Rail becomes an overlay drawer (key `g` or hamburger) instead of permanent column.
   - Timer settings behind ⚙ disclosure; Start/Pause/Reset inline in footer.
   - Clock + elapsed alongside countdown.
   - Keyboard parity: arrows/space, `b` curtain, `t`/`⇧T`, `3`, `g` rail, `?` cheatsheet.
4. **2d — Module split + payload slimming** (last, optional if 2a–2c land clean):
   split presenter.js into transport (postToPeer/onMessage/dedup/adoption/heartbeat),
   presenterState (reducer over `{index,total,timer,connected,seq}`), presenterUI
   (idempotent render from state). Deck-side payloads drop content fields **only
   after** test fixtures migrate to local-content mode; reader keeps accepting
   legacy fields indefinitely.

### Phase 3 — Author notes at generation time
1. Add a **Speaker Notes section to the spec format itself**: new column/field in
   `references/slide-spec-template.md`, emitted by `scripts/spec_generator.py`
   (does not exist today — must be added there, not just consumed), rendered by the
   generation skill as `<aside class="notes">` per slide, documented in SKILL.md.
2. `validate_deck.py`: missing-notes check lands in the existing **warnings** bucket
   (the script has only errors/warnings — no info channel; not a failure, never
   gates `--strict-variety`).
3. Existing decks keep working via the Phase-1 summary fallback.

## Non-goals
- No change to the ownership state-machine *logic* (roles/focus rules) — only the
  heartbeat ingestion fix in Phase 1.7.
- No transport consolidation — 3-transport redundancy is what makes file:// work.
- No second-screen auto-detection (Presentation API) — separate feature.
- No deck-side connection badge (dead code removed, not resurrected).

## Tests / verification
- mjs unit: summary extractor against real deck markup fixtures (split/why-panel/
  stats-row/terminal/table slides) — non-empty output for each.
- mjs unit: reducer ordering (stale seq dropped per kind — `slideSeq`/`timerSeq`
  independent; epoch reset on adoption; foreign-session tick filtered).
- mjs: **two-deck isolation** — deck A + deck B each with a popup on the global
  channel: B-popup `next` moves only deck B; B heartbeats don't refresh A's
  controller; B ticks don't repaint A's popup.
- mjs: popup timer passivity — `presenter=1` instance takes no wake lock, plays no
  bell, posts no ticks.
- mjs: heartbeat-over-postMessage reaches `PremiumController.recordHeartbeat`
  (file:// ownership fix).
- JSDOM: buildPopupDom structure (rail is grid child; no diag without `ppdiag=1`;
  preview clones have no duplicate ids, `aria-hidden` set).
- Existing `test-popup-e2e.mjs` (`withSlides:false` wire-content fixtures) stays
  green through Phase 2a–2c — proves backward compat.
- Browser smoke (chrome-devtools MCP): open deck file://, openPopup, jump from rail,
  assert popup counter+preview+notes all change; deck reload → popup re-syncs;
  two-deck scenario: second deck's timer ticks don't repaint first popup;
  zero console errors.
- Runtime contract + py tests stay green; rebundle 2 decks and re-verify.

## Risks
- Bundled decks embed their own copy of these scripts. Mixed combinations
  (old bundle + new popup or vice versa) only occur if a deck is half-rebundled —
  reader-side legacy-field acceptance covers it; deck-side content fields are kept
  until 2d makes removal safe.
- Preview clones of animated components (live-flow, mermaid, journey) must be
  static; `.pp-preview` scope class is the kill-switch; id-stripping protects the
  live deck DOM in the same document.
- `premium-controls.js` popup gating audit (Phase 1.5) may surface more leaked
  chrome (3D select, toasts) — treat as part of 1.5, not scope creep.
