# Plan: Presenter View — auto-popup presenter window with notes, timer, slide jump

_Locked via grill — by Claude + Bruno. Revised after Codex Round 1._

## Goal

Add a "presenter view" (à la PowerPoint) that opens automatically in a second
browser window on the presenter's laptop screen, mirroring the deck plus
showing speaker notes, next-slide title, timer (configurable duration or
target end time), and a clickable slide-jump list. The deck window on the
projector (or Teams-shared display) becomes a fullscreen, input-locked
mirror. The popup owns all input when present; the deck falls back to
owning input if the popup is closed or unfocused.

The audience display (deck window, shared via Teams or shown on a
projector) is clean — no notes, no controls. The presenter display
(popup, on the laptop) is a fixed light-theme "instrument panel" with
large readable notes, monospace timer, and high contrast.

## Approach

### 1. Auto-open policy (revised — gated on user gesture)

Open the popup only when the presenter has signaled intent. Three opt-ins,
in priority order:

- `?presenter=auto` URL query → auto-open on first user gesture (click or
  keydown) inside the deck window. The deck binds a one-shot listener;
  the first input event calls `window.open(...)`. This satisfies Chrome's
  popup policy (a user gesture is required) without leaking presenter
  content into the audience window.
- `?presenter=off` URL query → force-disable for the rest of the session;
  the popup never opens, ⇧P is also disabled, deck-only mode.
- `localStorage["premium-presenter-auto:" + location.pathname]` is `1` →
  same one-shot gesture listener. Default: unset. (No cheap second-display
  heuristic — `outerWidth < screen.availWidth` false-positives on any
  non-maximized window on a single monitor. Upgrade to
  `window.getScreenDetails()` is a future v2, only if real-world feedback
  shows a real need.)
- Otherwise: no auto-open. ⇧P opens the popup on demand. Author-side:
  `?presenter=auto` documented in README.

**If `window.open` is blocked** (returns null), show a small
"Presenter window blocked — click here to retry" prompt in the corner
of the deck window. **No notes, no jump list, no timer pill** — the
presenter content stays presenter-only. The user can click the prompt
to retry (it triggers a fresh `window.open` from the click gesture); on
a second block, the prompt stays put. The user can also use ⇧P again
later.

### 2. Session id, channel, window name, URL (revised)

At deck init, generate `sessionId = crypto.randomUUID()`. Build a
**per-session channel name**:
`new BroadcastChannel('premium-deck:' + sessionId)`. The session id is
also written to:
- the deck's `document.documentElement.dataset.session = sessionId`
  (debug surface, see #9).
- the popup window name: `'premium-presenter:' + sessionId` (so a
  second popup of a different deck doesn't collide on the global
  window name `presenter`).
- the popup URL, built by **mutating a `new URL(location.href)`** —
  not by passing a relative string (which would drop hash/params):

```js
const popupUrl = new URL(location.href);
popupUrl.searchParams.set('presenter', '1');
popupUrl.searchParams.set('session', sessionId);
// hash and all existing search params are preserved
popup = window.open(
  popupUrl.href,
  'premium-presenter:' + sessionId,
  'width=1280,height=720,resizable=yes'
);
```

Every message posted on the channel carries `sessionId`. Listeners reject
messages whose `sessionId` doesn't match. The popup also sends
`presenter.ready` with its `sessionId` on load; the deck ignores it if
`sessionId` doesn't match its own (defense in depth — in practice they
will match because the deck built the URL).

### 3. Two-window controller model (revised — single guard)

A single `PremiumController` module owns the focus-tracker and the
controller state. The state machine is explicit:

```
states: 'deck' | 'popup' | 'none'
```

- `'deck'` — the deck window owns input. The popup listens.
- `'popup'` — the popup window owns input. The deck early-returns
  on every shortcut.
- `'none'` — neither owns input (e.g. both windows blurred). No
  shortcuts fire; safer than letting a stale `'deck'` claim fire on
  the deck after the popup opened.

The focus-tracker runs at 500 ms intervals (and on
`focus`/`blur`/`visibilitychange`) and writes
`document.documentElement.dataset.controller` based on the local
window's `document.hasFocus()` and the most recent heartbeat (popup
side only). Both windows compute their own role independently:
- The deck is the controller iff `document.hasFocus()` AND
  (`lastHeartbeatTs` is absent OR `now - lastHeartbeatTs > 2500` OR
  the most recent heartbeat's `popupFocused === false`).
- The popup is the controller iff `document.hasFocus()` AND
  `now - lastHeartbeatTs <= 2500` AND
  `lastHeartbeat.popupFocused === true` (i.e. popup itself).

The deck is the **fallback** when the popup is closed, unresponsive,
or open-but-unfocused. The popup's heartbeat carries
`popupFocused: boolean` so the deck can take over even while the
popup is still alive. This avoids the "popup open, deck has focus,
neither owns input" dead state.

Exposed helper for handlers:
```js
window.PremiumController = {
  isLocalOwner(role) {  // role: 'deck' | 'popup'
    return document.documentElement.dataset.controller === role;
  },
  getState() { return document.documentElement.dataset.controller; },
};
```

Every shortcut handler — in `slide-engine.js`, `premium-controls.js`,
`premium-clicker.js`, `premium-search.js`, `premium-tts.js`, and the new
`premium-presenter.js` — early-returns on
`!window.PremiumController.isLocalOwner('deck')` (deck-side handlers)
or `!window.PremiumController.isLocalOwner('popup')` (popup-side
handlers). Centralizing the check is the plan; current scattered code
will be made consistent in the implementation pass.

The clicker calls `window.PremiumDeckControls.next/prev` (real API, see
#5), not synthetic keydowns.

When the popup is **closed or unresponsive** (no heartbeat for >2.5s,
see #6), the deck flips its local state to `'deck'` and re-enables
input. The popup reloads with a "deck reloaded" banner if it comes
back and the session id mismatches.

### 4. Sync protocol additions (revised)

Channel: `BroadcastChannel('premium-deck:' + sessionId)`.

**Outbound (deck → popup):**
- `slidechange` — `{ type, sessionId, index, total, title, notes, nextTitle, nextNotes }`
  (already exists in `slide-engine.js`; extend payload to include
  current `notes` and `nextNotes` — the popup cannot read them locally
  because it has no SlideEngine instance).
- `snapshot` — `{ type, sessionId, index, total, titles, notes, timer }`
  full state, sent once on `presenter.ready` and once on debounced deck
  changes (50 ms coalesce). The popup renders notes exclusively from
  these payloads; `PremiumDeckControls.getNotes` is an in-deck API only.
- `tick` — `{ type, sessionId, elapsedMs, remainingMs, running, state,
  mode, targetEndAtMs }` **throttled to 500 ms** in `premium-timer.js`;
  immediate for start/pause/reset/config-change events only. (60 Hz is
  wasteful; the popup doesn't need that resolution.)
- `bell` — existing.

**Inbound (popup → deck) — discriminated, with `commandId`:**
- `{ type: 'control', sessionId, commandId, action: 'next' }`
- `{ type: 'control', sessionId, commandId, action: 'prev' }`
- `{ type: 'control', sessionId, commandId, action: 'jump', index }`
- `{ type: 'control', sessionId, commandId, action: 'timer.start' }`
- `{ type: 'control', sessionId, commandId, action: 'timer.pause' }`
- `{ type: 'control', sessionId, commandId, action: 'timer.reset' }`
- `{ type: 'control', sessionId, commandId, action: 'timer.setMinutes', value }`
- `{ type: 'control', sessionId, commandId, action: 'timer.setEndAt', value }`
  where `value` is an absolute target timestamp (see #8).
- `{ type: 'control', sessionId, commandId, action: 'curtain' }`

The deck ignores messages with mismatched `sessionId` and dedupes by
`commandId` (Set, max 64 entries). All control goes through the channel —
**no `window.opener.PremiumTimer.setMinutes` calls**.

The popup sends `presenter.ready` on DOMContentLoaded; the deck replies
with a `snapshot` (initial-state handshake). The popup also sends
`presenter.heartbeat` every 1s with payload
`{ sessionId, popupFocused: document.hasFocus(), seq }`; deck tracks
`lastHeartbeatTs` and clears `data-presenter-display="on"` after 2.5s
of silence. `popupFocused` is included so the deck can take over input
even while the popup is still alive-but-unfocused.

### 5. Global `window.PremiumDeckControls` API (revised)

`slide-engine.js` exposes a stable surface for in-deck consumers
(clicker, future embed mode, popup-blocking fallback retry). The
popup does NOT use this API — the popup is a separate window with
no SlideEngine instance; it renders notes and titles from channel
payloads (`slidechange`, `snapshot`).
```js
window.PremiumDeckControls = {
  next(),
  prev(),
  goTo(index),
  getTitles(),        // [string, ...]   — in-deck only
  getNotes(index),    // string | null   — in-deck only
  getState(),         // { index, total } — in-deck only
  on(type, handler),  // 'slidechange' | 'tick' (re-emit of channel)
};
```
Clicker routes through these — not synthetic keydowns.

### 6. Presence: heartbeat + lease, not `popup.closed` (revised)

The deck tracks `lastHeartbeatTs`. If `now - lastHeartbeatTs > 2500ms` and
`data-presenter-display === 'on'`, the deck removes the attribute and
takes over input. The popup window is allowed to be reloaded, navigated
away, or even crash — the deck recovers. `popup.closed` is still
consulted for fast-exit (X button) but is no longer authoritative.

### 7. Deck goes "presenter-mode"

`html[data-presenter-display="on"]` set **only after the deck receives
a valid `presenter.ready` carrying a matching `sessionId`**. Until
that handshake completes, the deck is in `html[data-presenter-opening="true"]`
— a transient state where the deck is still actively rendering and
controls are still visible (because the user has not yet confirmed
presenter view is actually working). If `window.open` returns null
during auto-open, the deck never leaves `'opening'` and the retry
prompt is the only user-visible presenter artifact.

CSS in `premium-extras.css`:
- `data-presenter-display="on"`: hides controls/dots/hints/timer/3D bg;
  slide content goes `pointer-events: none`.
- `data-presenter-opening="true"`: hides only the timer pill and the
  3D bg; controls/dots/hints remain visible so the presenter can act if
  the popup doesn't appear.

When the deck takes over (popup closed, heartbeat lost, or
`popupFocused === false` for >2.5s), `data-presenter-display` is
removed and the deck resumes normal input. The `data-presenter-opening`
state is cleared on the first `presenter.ready` OR on the first
`window.open` failure.

### 8. Timer config — all precedence in `premium-timer.js` (revised)

Move every timer-config read into `premium-timer.js`. Precedence (highest
wins), evaluated at `init()`:

1. `sessionStorage["premium-timer"]` — session restore (the running
   talk's accumulated state). This is the top because a paused-and-resumed
   timer must keep its remaining time.
2. `localStorage["premium-timer-override:" + location.pathname]` — per-deck
   URL override written by the popup.
3. `<meta name="premium-timer" content="N">` in the deck's `<head>` —
   per-deck default.
4. Built-in default: 30 min.

`premium-timer.js.init()` reads all three, picks the highest, applies it.
The popup's "duration" / "end time" UI write to localStorage (#2) and
post a `control` message — they do not touch the session-storage
restore directly. The deck, on receiving the `control` message, calls
`PremiumTimer.setMinutes(N)` (or `setEndAt(timestamp)`) which then
re-saves session state. This eliminates the race between
`premium-controls.js` reading the meta and `premium-timer.js` reading
session restore.

**End-time mode** — store the mode and an absolute target timestamp
in the timer state. Two state fields, not one:
```js
let mode = 'duration';          // 'duration' | 'endAt'
let totalMs = 30 * 60 * 1000;   // used in 'duration' mode
let targetEndAtMs = 0;          // used in 'endAt' mode

function setEndAt(timestampMs) {
  if (!Number.isFinite(timestampMs) || timestampMs <= Date.now()) {
    throw new Error('Invalid end timestamp: must be a finite future timestamp');
  }
  mode = 'endAt';
  targetEndAtMs = timestampMs;
  reset();
}

function getState() {
  if (mode === 'endAt') {
    const remainingMs = Math.max(0, targetEndAtMs - Date.now());
    const elapsedMs = ...;  // wall-clock elapsed since last reset
    return { running, mode, totalMs: targetEndAtMs - startOfTalk,
             elapsedMs, remainingMs, targetEndAtMs };
  }
  // 'duration' mode — totalMs is fixed at config time
  if (!running) return { running: false, mode, totalMs, elapsedMs: elapsedAtPause, remainingMs: totalMs - elapsedAtPause };
  const elapsed = elapsedAtPause + (performance.now() - startTs);
  return { running: true, mode, totalMs, elapsedMs: elapsed, remainingMs: totalMs - elapsed };
}
```

The popup's `<input type="time">` parses `HH:MM` to a future timestamp
relative to the deck's wall clock, posts the absolute value via
`timer.setEndAt`. Each tick recomputes remaining from
`targetEndAtMs - Date.now()` — no midnight/DST/delayed-start bugs.
Switching back to duration mode is `setMinutes(N)`, which sets
`mode = 'duration'`.

**Throttled broadcasts** — wrap `post('tick', ...)` so it fires at most
once per 500 ms; immediate for start/pause/reset/setMinutes/setEndAt
events.

### 9. Popup content (light theme, fixed)

- Top bar: deck title + `slide N / total` + duration badge.
- Middle: next slide title (h2, monospace fallback) — pulled from
  `premium-deck:state.slidechange.nextTitle` or "End of deck" if last.
- Right rail: clickable slide-jump list — click → `control.action: 'jump'`.
- Bottom panel (60% height): current slide's notes — read from
  `snapshot.notes[index]` and updated on every `slidechange.notes`
  payload. Large 18-20px body, generous line-height, `<aside
  class="notes">` HTML rendered. The popup never calls
  `PremiumDeckControls.getNotes` — the popup window has no
  SlideEngine instance.
- Floating bottom-right: timer pill (consumes `tick` messages; flash on
  `slidechange`).
- Floating top-right: timer controls — duration input (number, minutes),
  end-time input (time, optional), Start/Pause/Reset, Mode toggle
  (Duration | End time). 400 ms debounce on input.
- **Status surface (bottom-left, dev/debug)** — small monospace row:
  `presenter: connected` (or `lost 2.3s ago`), `controller: popup`,
  `session: 019e98…`, `last heartbeat: 0.8s`. Always on; small and
  unobtrusive. This is the observability Codex flagged as missing.

### 10. Keyboard

- `Esc` closes popup.
- `Space` next, `←/→` prev/next.
- `T` start/pause timer.
- `B` curtain.
- `D` toggle presenter display (blackout the deck) — sends
  `control.action: 'curtain'`.
- `⇧P` (deck) — open popup (manual fallback).
- All popup keyboard handlers early-return unless
  `window.PremiumController.isLocalOwner('popup')` is true. Same for
  the deck side: every deck handler early-returns unless
  `isLocalOwner('deck')` is true. The `'none'` state (neither focused)
  is the explicit quiescent state — no shortcuts fire.

### 11. Visual + interaction polish

- Popup: 1280×720 default, resizable, draggable (browser default).
- Distinct `<title>` for Teams window-picker:
  - Popup: `Presenter — <deck title>`
  - Deck: `Audience — <deck title>`
  (Default: just the deck title. Set on `?presenter=auto` or popup open.)

### 12. Standalone bundle parity (revised)

Editing `shared/premium-presenter.js` alone will not update
`decks/*/...-slides.html`. After implementation, run
`python3 scripts/bundle_deck.py --force` for all 4 production decks
(`rag-vector-graph`, `graph-databases`, `vector-databases`,
`vector-vs-graph`). Add a CI smoke that greps each standalone HTML for
the inlined marker `/* --- premium-presenter.js --- */` and a
known-new string introduced in the implementation (e.g. a magic
constant in the new heartbeat handler). Test fails if either marker
is missing from a deck that uses premium-presenter.

## Key decisions & tradeoffs

- **Two-window over single-window with a CSS toggle.** Single-window
  would need `?presenter=view` to flip the deck into a "dual pane" mode
  — but then Teams shares both panes, defeating the purpose. Two real
  OS windows is the only way to keep the audience's view truly clean.
- **Popup over iframe.** The popup is a second `window.open` so the OS
  treats it as a separate draggable/resizable window. Drag it to the
  second display, fullscreen it. Iframes can't be fullscreened across
  displays.
- **Per-session channel name + nonce over plain `BroadcastChannel`.**
  Origin-wide channels are unauthenticated — any same-origin tab can
  inject controls. Per-session random channel name + `sessionId` carried
  in every message makes injection impractical for the popup-attack
  threat model.
- **Initial handshake + heartbeat over `popup.closed` polling.**
  `popup.closed` is unreliable for reloaded/manually-opened popups and
  adds zero presence signal. A handshake gives the popup a known-good
  initial state; heartbeats give liveness.
- **Throttled tick over per-frame tick.** 60 Hz broadcasts of a clock
  nobody reads at 60 Hz. 500 ms is fine for a human eye on a timer pill
  and cuts messages by 120×.
- **Per-deck URL localStorage over global.** A 25-min talk and a 90-min
  workshop on the same laptop should not share timer overrides.
- **Light theme popup over themed.** The popup is an instrument panel,
  not content. High contrast, monospace where it helps, no theme tokens
  competing with the deck.
- **B with A fallback over C (both always accept input).** C would
  require deduplication of every event. B's model — explicit
  `'deck' | 'popup' | 'none'` owner state, a single focus-tracker,
  per-window heartbeat lease, discriminated commands with `commandId`
  dedupe, and explicit owner transitions on `presenter.ready` /
  `presenter.heartbeat` / heartbeat loss — handles the common cases
  (popup focused, deck focused, popup closed) without the duplication
  cost. The trade is correctness comes from the combination of
  controls, not from any single one — focus-only is racy, heartbeat-only
  is laggy, dedupe-only is fragile.
- **Stable `window.PremiumDeckControls` API over direct SlideEngine
  calls.** Clicker / popup / tests all need a single integration point.
  Anonymous `new SlideEngine()` is a refactor smell that the
  implementation will fix.
- **Discriminated commands with `commandId` over payload blobs.**
  `setMinutes` + `start` in the same payload is ambiguous; `commandId`
  gives idempotency. Cheap to add, hard to retrofit.

## Risks / open questions

- **WebHID / clicker pairing**: WebHID is per-origin, and the popup is
  the same origin as the deck. If the clicker pairs with the deck
  window first, the popup may need to re-pair. Document this in the
  clicker module; the clicker's first action after a popup open is a
  re-pair attempt.
- **Teams screen-share window targeting**: Teams "share a window" is
  per-OS-window. If both Chrome windows have the same icon, users may
  select the wrong one. Mitigate by giving the popup a distinct
  `<title>` (see #11).
- **Reload of the deck window while the popup is open**: deck
  re-initializes with a new `sessionId`, popup's URL no longer matches.
  Mitigate: popup detects channel silence + popup URL still has the
  old sessionId → popup shows a "deck reloaded — close me and reopen
  with ⇧P" banner.
- **Bundle parity CI**: building it is simple; running it on every PR
  is the part that needs buy-in. Will mention in PR description.
- **Mobile / tablet companion**: not in this scope. Pure browser-only.
- **The popup duplicates the existing `renderPresenterLayout` in
  `premium-presenter.js`**: that code currently does dual-pane
  (current+next visual previews). We're replacing it with a single-pane
  notes layout. The visual-preview style is deprecated. The popup-blocked
  fallback is a non-notes retry prompt only — no `openFallback` /
  presenter overlay. `openFallback` is removed from the active code path
  (may remain in source for future reactivation, but is not part of
  this feature's behavior).

## Out of scope

- Mobile/tablet companion (requires a local web server).
- Cloud sync of timer presets across devices.
- Speaker cue cards ("smile", "pause") — can be added later as bullet
  points in `<aside class="notes">`.
- Recording / playback.
- Multi-presenter collaboration (two people driving the same deck).
- Audio cue tones beyond the existing speaker-timer bells.
- `getScreenDetails()` based second-display detection (v2).

## Test plan (revised — failure cases too)

Browser-level smoke tests via a headless runner (Playwright) added to
`scripts/`:

1. **Single display, no popup**: deck works as before, ⇧P opens popup.
2. **Dual display (mocked with `?presenter=auto`)**: popup opens on
   first user gesture (simulated click).
3. **Teams-share scenario**: deck fullscreen, popup fullscreen on
   second display, only deck's content shown in audience (assert popup
   window is not in `screen.share` candidates — out of test scope, but
   assert titles differ).
4. **Popup blocked**: `window.open` mocked to return null → a small
   "Presenter window blocked — click to retry" prompt appears in the
   corner of the deck window. **No notes, no jump list, no timer pill
   in the prompt.** Assert that the deck's DOM does not contain
   presenter-only elements (no `.premium-presenter`, no notes overlay).
   Click on the prompt triggers a fresh `window.open` from a real
   gesture. Assert that `document.documentElement.dataset
   .presenterDisplay` is **absent** (and
   `data-presenter-opening` is also cleared) — the deck never went
   into presenter-mode.
5. **Multi-deck channel collision**: open deck A, open deck B, send
   `control.action: 'jump'` to A — assert B is unaffected (channel
   name includes sessionId).
6. **Opening on a non-first slide**: load deck with `#slide-5` hash
   → popup `snapshot` shows index 5, not 0.
7. **Invalid timer input**: `setEndAt(NaN)` / negative / past → throw,
   timer unchanged, popup shows error.
8. **Opener-null**: deck's `window.opener` is null (popup opened
   manually to the same URL) → assert no errors, popup is treated as
   a third-party tab and ignored (channel sessionId mismatch).
9. **Bundle parity**: after touching `shared/premium-presenter.js`,
   grep each of the four production standalone HTML files
   (`decks/rag-vector-graph/rag-vector-graph-slides.html`,
   `decks/graph-databases/graph-databases-slides.html`,
   `decks/vector-databases/vector-databases-slides.html`,
   `decks/vector-vs-graph/vector-vs-graph-slides.html`) for the
   inlined marker `/* --- premium-presenter.js --- */` AND for a
   known-new string introduced in the implementation (e.g. a magic
   constant in the new heartbeat handler). Test fails if either
   marker is missing from a deck that uses premium-presenter.
10. **Pause/resume no double-count**: timer 5:00 → pause 3s → resume
    → remaining should be 4:57 (not 4:54).
11. **End-time across midnight**: `setEndAt(tomorrow 00:30)` at 23:55
    → remaining 35 min, not `-∞`.
12. **Heartbeat loss**: kill popup → deck removes `data-presenter-display`
    within 2.5s, takes over input.
13. **Reload of deck**: assert popup shows "deck reloaded" banner
    (manual, with a console probe).
