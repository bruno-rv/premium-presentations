# Plan Review Log: Presenter View — auto-popup presenter window

Act 1 (grill) complete — plan locked with the user. MAX_ROUNDS=5.

## Act 2 — Codex adversarial review

### Round 1 — Codex

**Material Flaws**

1. **Auto-open popup blocked by browser rules.** `window.open` on first load (no user gesture) is silently blocked by Chrome's popup policy. Fallback overlay would leak notes onto the audience. Fix: open on first user gesture (any click/key in the deck window), OR require explicit `?presenter=auto` query.
2. **Second-display heuristic false-positives.** `outerWidth < screen.availWidth` is true for any non-maximized window on a single monitor. Fix: remove cheap heuristic in v1; require explicit opt-in (`?presenter=auto`) OR upgrade to `getScreenDetails()` with permission.
3. **BroadcastChannel is origin-wide, unauthenticated.** Any same-origin tab can send `jump`/`timer`/`curtain` controls. Fix: per-session random channel name + nonce, reject messages without the session id.
4. **No initial-state handshake.** `currentSlideIdx` starts at 0; popup shows slide 1 until the next navigation. Fix: popup sends `presenter.ready`, deck replies with full snapshot (current index, all slide titles, timer state).
5. **No `window.PremiumDeckControls` API.** `new SlideEngine()` is anonymous; `next`/`prev`/`goTo`/titles not exposed. Fix: add `window.PremiumDeckControls = { next, prev, goTo, getTitles, getState }`.
6. **`data-controller` guard isn't enforced today.** Handlers scattered across 6 modules; clicker dispatches synthetic keydowns. Fix: centralize input through a single controller guard, route clicker actions through the API not synthetic events.
7. **`popup.closed` isn't enough presence detection.** Fails for manually-opened/reloaded presenter URLs; can leave deck stuck in presenter mode. Fix: heartbeat/lease messages, clear presenter mode after missed heartbeats.
8. **Timer config precedence is split.** Meta defaults wired to `premium-controls.js`, session restore lives in `premium-timer.js` — overwrites can race. Fix: move all precedence into `premium-timer.js`: session restore > per-deck override > meta default > built-in default.
9. **End-time mode stores `HH:MM` once, breaks delayed starts + midnight/DST.** Fix: store absolute target timestamp; recompute remaining from wall clock each tick.
10. **Timer tick broadcasts 60 Hz.** Popup doesn't need that resolution; expensive DOM updates. Fix: throttle cross-window broadcasts to 500 ms; immediate only on start/pause/reset/config changes.
11. **Timer control schema ambiguous.** `{ payload: { setMinutes, setEndAt, start, pause, reset } }` allows conflicting commands; no id. Fix: discriminated commands `{ action: 'timer.setMinutes', value, commandId }`, dedupe by id.
12. **`window.opener.PremiumTimer.setMinutes` is fragile.** Fix: route all control through the nonce-protected channel.
13. **Popup URL construction drops query/hash, reuses global window name `presenter`.** Fix: use `new URL(location.href)`, preserve hash/params, session-specific window name.
14. **Plan ignores standalone bundles.** Editing `shared/` doesn't update `*-slides.html`; bundler script order independent. Fix: re-bundle 4 decks with `--force` after implementation.
15. **Test plan misses failure cases.** Popup blocked while sharing, multi-deck channel collision, opening on a non-first slide, invalid timer input, opener-null, bundle parity. Fix: add browser-level tests for these.
16. **Observability too thin.** `console.warn` doesn't help during a live talk. Fix: small debug surface in popup showing presenter connected, controller owner, session id, last heartbeat.

**VERDICT: REVISE**

### Claude's response — Round 1

All 16 findings incorporated. Highlights:

- **#1, #2** — removed cheap second-display heuristic; auto-open is now
  gated on `?presenter=auto` query or persisted localStorage opt-in, and
  the actual `window.open` is wrapped in a one-shot user-gesture listener
  to satisfy Chrome's popup policy.
- **#3, #4, #7, #11, #12, #13** — full sync-protocol rewrite: per-session
  random channel name (`premium-deck:<uuid>`), `sessionId` in every
  message, `presenter.ready` → `snapshot` handshake, 1s `presenter.heartbeat`
  with 2.5s lease, discriminated `{action, commandId}` control messages
  (deduped by id), popup URL built with `new URL(...)` to preserve
  hash/params, session-specific `window.name`.
- **#5** — explicit `window.PremiumDeckControls = { next, prev, goTo,
  getTitles, getNotes, getState, on }` surface in `slide-engine.js`.
- **#6** — single 500ms focus-tracker writes `data-controller`;
  all shortcut handlers audit-passed to early-return on `'other'`.
  Clicker routes through `PremiumDeckControls`, not synthetic keydowns.
- **#8, #9, #10** — `premium-timer.js` becomes the single owner of timer
  config (session restore > per-deck override > meta > built-in default);
  `setEndAt` takes an **absolute target timestamp** (validates finite,
  future), not `HH:MM`; `tick` broadcasts throttled to 500ms with
  immediate flush on lifecycle events.
- **#14** — `scripts/bundle_deck.py --force` re-bundle of all 4 production
  decks called out as a required final step; CI smoke added.
- **#15** — test plan grew from 4 paths to 13 cases (popup-blocked,
  multi-deck collision, non-first slide open, invalid timer, opener-null,
  bundle parity, pause/resume no double-count, end-time across midnight,
  heartbeat loss, deck reload).
- **#16** — bottom-left status surface in popup shows presenter
  connected / controller owner / session id / last heartbeat.

Round 1 → Round 2.

### Round 2 — Codex

**Remaining Findings**

1. **Fallback overlay still leaks notes.** Auto-popup blocked → fallback
   overlay shows notes in the deck window (audience sees them). Fix: the
   fallback is a small "popup blocked — click to retry" prompt with NO
   notes content. Notes are a presenter-only artifact, period.
2. **`new URL('?...', location.href)` drops hash + params** (Codex
   verified with Node). Fix: `const u = new URL(location.href); u.searchParams.set('presenter', '1'); u.searchParams.set('session', sessionId); popup = window.open(u.href, 'premium-presenter:' + sessionId, features)`.
3. **Controller state machine is inconsistent.** Plan says write
   `'popup' | 'deck'` but handlers return on `'other'`; popup guidance
   says it "should never be the controller" while being the main owner.
   Fix: model is `'deck' | 'popup' | 'none'`. Handlers check
   `dataset.controller !== 'deck'` on the deck side and
   `!== 'popup'` on the popup side. Single helper:
   `PremiumController.isLocalOwner(role)` for clarity.
4. **Outdated "no race conditions" tradeoff** remains; new architecture
   (heartbeat, dedupe, owner transitions) contradicts the line. Fix:
   replace with the actual race controls: heartbeat lease, command
   dedupe, explicit owner transitions.
5. **Popup notes sourcing impossible as written.** `PremiumDeckControls`
   lives in the deck window; `slide-engine.js` exits early on
   `?presenter=1` to stop the re-init loop, so the popup never has a
   SlideEngine instance. Fix: deck pushes notes in every `slidechange`
   payload + the `snapshot` payload. Popup renders notes exclusively
   from those. `PremiumDeckControls.getNotes` is for in-deck consumers.
6. **End-time mode is contradictory.** Sample `setEndAt` stores only
   `totalMs`; prose says each tick derives remaining from
   `target - Date.now()`. Fix: store `{ mode: 'endAt', targetEndAtMs }`
   in timer state; `getState()` returns `remainingMs: targetEndAtMs -
   Date.now()` when `mode === 'endAt'`, `totalMs - elapsed` otherwise.
7. **Bundle parity test references a non-existent `bundle.txt`.** Fix:
   smoke test greps standalone HTML for the inlined marker
   `/* --- premium-presenter.js --- */` and a known-new string
   introduced in the implementation.

**Prior Findings Addressed**

The revision does address the biggest Round 1 issues: no cheap display
heuristic, user-gesture popup gating, session-scoped channel, initial
snapshot, heartbeat lease, discriminated commands with `commandId`,
`PremiumDeckControls`, timer precedence moving into `premium-timer.js`,
tick throttling, no `window.opener` control path, debug status, and
broader tests.

**VERDICT: REVISE**

### Claude's response — Round 2

All 7 accepted:

- **#1** — fallback rewritten: a non-notes "popup blocked" prompt only.
- **#2** — popup URL construction now mutates a `new URL(location.href)`,
  preserving hash/params, and uses session-specific window name.
- **#3** — state machine is `'deck' | 'popup' | 'none'`; helper
  `PremiumController.isLocalOwner(role)`.
- **#4** — tradeoff prose rewritten around heartbeat lease, command
  dedupe, owner transitions.
- **#5** — notes always come from channel payloads; `getNotes` is an
  in-deck API.
- **#6** — timer state carries `{ mode, targetEndAtMs }`; `getState()`
  branches on `mode`.
- **#7** — bundle smoke uses inlined script markers + a known-new string,
  no `bundle.txt`.

Round 2 → Round 3.

### Round 3 — Codex

**Findings**

1. **Popup-blocked path still inconsistent.** Main plan says small retry
   prompt with no presenter content; tests still expect a fallback
   overlay; risks still mention `openFallback`. Fix: update test #4 +
   risk section to reference only the non-notes retry prompt. Remove
   `openFallback` from active risk list (deprecated; kept in code for
   the manual non-shared case if ever reactivated, but not part of
   the popup-blocked path).
2. **Popup notes still references `PremiumDeckControls.getNotes`.**
   Contradicts channel-only popup model. Fix: popup notes rendering
   uses `snapshot.notes[index]` / `slidechange.notes` only.
3. **Keyboard section still says "popup should never be the controller."**
   Contradicts the explicit `'popup'` owner state. Fix: popup handlers
   guard with `PremiumController.isLocalOwner('popup')`.
4. **Test plan still references `bundle.txt`.** Fix: update test #9 to
   grep the four production standalone HTML files for the inlined
   marker and a known-new string.
5. **New controller-state bug.** Deck ownership disabled whenever
   popup heartbeat is fresh → if popup is open-but-unfocused and deck
   has focus, neither window owns input. Contradicts the "deck falls
   back when popup closed or unfocused" goal. Fix: heartbeat carries
   popup's `hasFocus`; deck owns input when
   `deck.hasFocus() && !popupFocused` (or popup heartbeat stale).

**Round 2 status**: 2, 4, 6 materially addressed; 1, 3, 5, 7 had
stale contradictory text in subsections — fixed this round.

**VERDICT: REVISE**

### Claude's response — Round 3

All 5 accepted:

- **#1** — test #4 + risk section now reference only the non-notes retry
  prompt. `openFallback` removed from active risk list; noted as
  deprecated code-kept for manual non-shared use.
- **#2** — popup notes rendering line rewritten: "from `snapshot.notes`
  / `slidechange.notes` only."
- **#3** — keyboard section popup guards rewritten to
  `PremiumController.isLocalOwner('popup')`.
- **#4** — test #9 rewritten: grep the four production HTML files for
  the inlined marker and a known-new string.
- **#5** — heartbeat payload extended with `popupFocused: boolean`; deck
  owner predicate updated. Goal statement unchanged.

Round 3 → Round 4.

### Round 4 — Codex

**Finding**

1. **Stale presenter-mode on auto-open in flight.** `data-presenter-
   display="on"` is set as soon as auto-open is in flight, so if
   `window.open` returns null the deck may remain in presenter-mode
   with controls hidden / pointer-events disabled even though no
   presenter window exists. Fix: use a separate transient
   `data-presenter-opening` state; set `data-presenter-display="on"`
   only after receiving a valid `presenter.ready`. Add a blocked-
   popup assertion that `data-presenter-display` is absent.

**Round 3 status**: all 5 materially addressed.

**VERDICT: REVISE**

### Claude's response — Round 4

- **#1** — auto-open path now uses `data-presenter-opening` (controls
  still visible, deck still active) until a valid `presenter.ready`
  arrives. Only then is `data-presenter-display="on"` set. The
  blocked-popup test asserts that `data-presenter-display` is absent
  when `window.open` returns null.

Round 4 → Round 5.

### Round 5 — Codex

No material issues found. Round 4 fix confirmed.

**VERDICT: APPROVED**

---

## Resolution

**APPROVED** — survived 5 rounds of adversarial Codex review.

Final plan: `/Users/bruno/Dev/presentations/PLAN.md`
Review log: `/Users/bruno/Dev/presentations/PLAN-REVIEW-LOG.md`

**What two acts improved:**
- **Act 1 (grill, 10 questions)** — locked the open questions that
  would have killed the build: two-window model (not single CSS toggle),
  popup over iframe, per-deck URL timer override, popup-as-controller
  with deck fallback, light-theme popup.
- **Act 2 (Codex, 4 REVISE rounds)** — surfaced 30+ specific flaws
  across 4 rounds: blocked `window.open`, BroadcastChannel auth, no
  initial handshake, no `PremiumDeckControls` API, timer precedence
  split, end-time as `HH:MM`, 60 Hz tick spam, ambiguous control schema,
  fragile `window.opener` calls, hash-dropping URL construction, bundle
  parity, popup-blocked tests, controller state-machine contradictions,
  popup focus dead-state, presenter-mode on auto-open in flight.

**Grilled + survived 5 rounds of Codex. Implement it now?**

## Act 1 — Grill

- **Q1.** Presenting setup → A: laptop + projector.
- **Q2.** Control location → A1: laptop is presenter, projector is dumb mirror.
- **Q3.** Where the deck lives → Option 1b: deck in one Chrome window, presenter popup in a second, only the deck shared in Teams.
- **Q4.** Two-screen layout → Display 1 (shared) = deck fullscreen, Display 2 (laptop) = presenter notes fullscreen.
- **Q5.** Auto-open behavior → B + C: detect second display (cheap heuristic, no permission), respect `?presenter=auto` / `?presenter=off`, remember last choice in localStorage per deck.
- **Q6.** Popup contents → current slide title + slide number, next slide title, large notes, jump-list, timer pill, timer controls. Skip visual previews.
- **Q7.** Timer override → C: per-deck default (meta tag) + per-session override (popup UI).
- **Q8.** Timer start time → C: both modes, toggle in popup (duration | target end time).
- **Q9.** Popup theme → B: fixed light theme, no theme tokens.
- **Q10.** Controller model → B with A fallback: popup owns input when present, deck falls back if popup closed/unfocused. Crash-safe.
