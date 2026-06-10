# Plan Review Log: Presenter view refactor (PLAN-PRESENTER.md)
Started 2026-06-10. MAX_ROUNDS=5. Reviewer: Codex (read-only). Builder: Claude.

## Round 1 — Codex
VERDICT: REVISE. 11 findings:

- **P0 heartbeat transport gap**: controller records heartbeats only from BroadcastChannel; `onDeckMessage()` no-ops them → ownership dead on file://. Fix: forward to `recordHeartbeat()` from all transports.
- **P0 startup race**: premium-presenter.js loads before slide-engine.js; `buildPopupDom()` renders before `PremiumDeckControls` exists. Fix: pure DOM extractors or ready signal.
- **P1 deck chrome leaks into popup**: hide-CSS targets stale `.progress-bar/.counter/.hints`; real classes `.deck-progress/.deck-counter/.deck-hints`; controls shell/timer pill/3D/toasts unhandled.
- **P1 timer ticks lack sessionId** → cross-deck bleed with two decks open; popup's local PremiumTimer could post authoritative ticks.
- **P1 no message ordering**: 3 transports, no seq → stale state can overwrite fresh. Fix: stateSeq + epoch.
- **P1 `?presenter=diag` breaks popup detection** (`isInPopup()` tests `presenter==='1'`). Fix: separate `ppdiag=1`.
- **P1 audience badge is dead code**: `showDeckBadge`/`updateDeckBadge` scoped inside `init()`, called from module scope inside try/catch → never renders. Plan's "permanent badge" diagnosis was wrong.
- **P1 preview cloning under-specified**: hidden-unless-`.visible` slides, duplicate ids from live-flow/SVG. Fix: sanitize clones (id-strip, force visible, aria-hidden, no events).
- **P1 dropping content fields breaks `test-popup-e2e.mjs` `withSlides:false` fixtures**. Fix: keep sender fields until fixtures migrate.
- **P2 `speaker-notes` spec field doesn't exist** in template/generator. Fix: add across template+generator+validator together.
- **P2 phasing too big**: land local-content compat layer first, split modules last.

### Claude's response
All 11 accepted — each verified against source before adoption (script order premium-base.html:50-51, stale CSS selectors premium-extras.css:264 vs premium-deck.css:78, tick payload premium-timer.js post(), badge scoping presenter.js:776 vs :200). Notable correction: original plan claimed audience badge "shows forever" — actually never shows (scope bug); diagnosis D3 rewritten, badge path now deleted not faded. Plan restructured: Phase 1 gains heartbeat-forwarding (1.7) + chrome-leak fix (1.5) + ppdiag param (1.1); Phase 2 split into 2a compat layer → 2b ordering/identity (stateSeq, session-stamped ticks, popup timer broadcast gate) → 2c layout/previews (with clone sanitization spec) → 2d module split + payload slimming gated on fixture migration; Phase 3 explicitly adds Speaker Notes to spec template + generator. Nothing rejected.

## Round 2 — Codex
VERDICT: REVISE. 6 findings:

- **P1 session filter must cover ALL message types**, not just ticks — `handleControl()` skips session checks, `onPopupMessage()` accepts everything; two decks open → popup controls/heartbeats land on both. Fix: one shared peer/session filter with adoption exceptions + two-deck tests.
- **P1 stateSeq underspecified across modules** — slide-engine and premium-timer publish independently; single counter + single cursor drops valid messages. Fix: central `nextStateSeq()` allocator or per-kind cursors.
- **P1 load-order hole remains** — extractors "refactored out of SlideEngine.prototype" can't live in slide-engine.js (loads after presenter.js). Fix: new module loaded before presenter, `window.PremiumSlideContent`.
- **P1 hiding "3D frame" blanks previews** — `.slide-3d-frame` wraps slide content; hide it and preview clones are empty. Fix: hide `.premium-bg-3d`/toasts/shell only; flatten frame transforms.
- **P2 popup timer side effects beyond postTick** — session restore, RAF, wake lock, bell audio still run in popup. Fix: timer fully passive under `presenter=1`.
- **P2 summary extractor must strip `aside.notes`/`.slide__notes`** or authored notes get duplicated in summaries.

### Claude's response
All 6 accepted. Plan edits: Phase 2b rewritten — single shared receive-path filter for all types w/ discover/hereIam adoption exceptions + epoch reset; central seq allocator + per-kind reducer cursors (slideSeq/timerSeq); heartbeat forwarding reuses controller's session check. Phase 2a — extractors moved to new `premium-slide-content.js` (window.PremiumSlideContent) loaded before presenter.js, wired into templates + scripts/_common.py bundler order; SlideEngine delegates. Phase 1.5 — never hide `.slide-3d-frame` (wraps content), hide `.premium-bg-3d`/toasts/shell, flatten transforms in popup/preview scopes. Phase 2b — timer fully passive in popup (no wake lock/bell/RAF/session restore). Phase 1.3 — strip aside.notes/.slide__notes from summary clone. Tests: added two-deck isolation suite + timer passivity assertions. Nothing rejected.

## Round 3 — Codex
VERDICT: APPROVED. "No material blockers remain." 3 tighten-before-coding nits:

- **P2 preview id sanitization**: bare strip/prefix insufficient — journey references ids via `data-journey-gradient` + SVG `url(#…)`, live-flow via `data-flow-phases` JSON. Fix: old→new rename map rewriting IDREFs/url()/JSON, or static fallback for dynamic layers.
- **P3 new module missing from runtime docs**: add `premium-slide-content.js` to `references/runtime.md` + runtime contract, not just templates/_common.py.
- **P3 "info-level warn" ambiguous**: validate_deck.py has only errors/warnings buckets. Fix: call it a warning explicitly.

### Claude's response
All 3 folded into the plan (preview id rename-map spec in 2c; runtime.md + validate_runtime_contract.py registration in 2a; Phase 3.2 reworded to warnings bucket, never gates --strict-variety). Loop converged in 3 rounds.

---
**Final: APPROVED after 3 rounds. 20 findings total (11+6+3), all accepted, zero rejected. Key corrections the argument produced: ownership broken on file:// (heartbeat/BC gap), audience badge was dead code not pollution, .slide-3d-frame must never be hidden, session filtering needed for ALL message types (two-deck bleed), extractors need a pre-presenter load slot.**

## Code Review Round 1 — Codex (implementation)
VERDICT: REVISE. 8 findings, all verified real by Claude before fixing:

- **High** presenter.js:195 — `presenter.ready`/`presenter.closing`/`control` bypass the shared session filter (only heartbeat got it); foreign popups can connect/close/drive a deck.
- **High** presenter.js:795 — session adoption (hereIam) doesn't reset slideSeq/timerSeq cursors → reloaded deck's fresh seq stream (restarting at 1) dropped as stale.
- **High** slide-engine.js:593 + premium-timer.js:439 — global BC listeners (TTS-follow re-broadcast, timer slidechange hook) accept foreign-session messages.
- **Med** presenter.js:300 — preview rename-map incomplete: clone root id not renamed; url(#…) in style/presentation attrs, data-journey-gradient, data-flow-phases JSON, for/ARIA refs not rewritten; no aria-hidden.
- **Med** premium-extras.css:380 — fixed 0.2 preview scale, `.reveal`/non-`.visible` slides not forced visible → next-preview blank (deck CSS has `.slide{opacity:0}` unless `.visible`).
- **Med** premium-slide-content.js:190 — summary lacks last-resort title fallback required by plan Phase 1.3.
- **Med** premium-timer.js:430 — popup passivity gates init() only; exported mutators (start/reset/…) can still RAF/wake-lock/bell in popup.
- **Med** scripts/package.json — new tests not wired into npm scripts; test-popup-bc/postmessage/timer fail (renamed timer control ids; bc fixture reads data-session before DOMContentLoaded → popup gets session=undefined and the new — correct — filter drops the snapshot; old code passed only because it accepted everything).

### Claude's response
All accepted → fix pass dispatched (Sonnet). Fixture handshake repaired rather than weakening the filter.

## Code Review Round 2 — Claude (own review, after Codex)
Independent verification of the fix pass + live browser smoke (file://, rebundled rag-vector-graph):

**Suites re-run independently**: theme-quality 8/8 · popup chain 63/63 (bc 4, e2e 4, postmessage 8, storage 3, timer 3, presenter-seq 13, slide-content 28) · presenter-smoke 9/9 · python 28/28 · runtime contract OK · verify_bundle exit 0.

**Code reading**: shared session filter ordering correct (rememberPopupSource only after gate; discover/hereIam bypass); adoption resets slideSeq/timerSeq/popupTimerState before sendReady.

**Found + fixed during this round (3 residual issues)**:
1. Fix-agent CSS comment said "Reveal.js" → bundled into deck → validate_deck FAIL (external-Reveal check). Comment reworded.
2. Deck-specific body chrome (.term-popup glossary card) leaked into popup — enumerated hide-list can't cover deck-specific markup. Added catch-all: hide all body children except .premium-presenter + #deck.
3. .premium-presenter__timer-settings[hidden] beaten by display:flex → settings row peeked at bottom. Added [hidden]{display:none!important} guard. Also: footer session label went stale after hereIam adoption — now refreshed each heartbeat.

**Browser smoke (all pass, zero console errors both windows)**: popup instrument panel renders (current+next previews with renamed ids slide-N-ppX, computed scale 0.28, aria-hidden); notes pane shows extracted summary (table content); rail drawer closed by default, 14 items, jump syncs deck→#slide-5; keyboard next in popup → 6/14 both windows; deck goTo(8) → popup follows 9/14 incl. preview; deck reload → popup adopts new session (label live); deck chrome display:none in popup; #deck offscreen visibility:hidden (clone source); diag absent without ppdiag; audience window has no badge/diag; aside.notes hidden from audience; validate_deck OK (2 warnings: playwright missing, 12 slides without notes — expected for pre-Phase-3 deck).

**Known polish items (not blocking)**: preview row uses ~25% of panel height (plan sketch wanted ~55%); summary for dense split-table slides can be thin ("Lexical"); beautify-smoke demo deck has pre-existing untracked mermaid error (predates this work).

---

# Increment 2: Shared Glossary Component (promotion from deck-local hack)

Built by Sonnet agent: premium-glossary.js (JSON dict via script#glossary, lazy-injected #term-popup modal, window.PremiumGlossary API), shared CSS, conditional bundling (wants_premium_glossary), snippet + generation docs + spec-template Glossary section, validate_deck warnings, presenter popup Terms section, rag-vector-graph migrated (22 terms verbatim, inline style/modal/IIFE removed).

## Glossary Review Round 1 — Codex
VERDICT: REVISE. 4 findings, all verified then fixed by Sonnet agent:
- **High**: presenter=1 guard installed no-op API → presenter .pp-notes-terms could never populate. Fixed: dict parsed before guard; read API real, open/close no-ops, no modal.
- **Med**: modal lacked Tab trap; Arrow/Space reached deck nav while open. Fixed: capture-phase keydown active only while open (Tab wraps to close btn; nav keys preventDefault+stopImmediatePropagation; Esc stops propagation only while open).
- **Med**: wants_premium_glossary evaluated AFTER inline_stylesheets — ".term-link" in shared CSS → glossary bundled into EVERY deck. Same pre-existing flaw confirmed for flow/journey matchers. Fixed: use_* booleans captured from original html pre-inlining; matchers tag-aware (data-term=/id="glossary"/class= patterns). 11 new bundling tests.
- **Med**: malformed script#glossary JSON silently swallowed by validator. Fixed: warnings for parse failure / non-object root / entries missing title|body.

## Glossary Review Round 2 — Codex
VERDICT: REVISE. 1 residual: dict validation gated on term-links existing — deck with dict but zero links passed a malformed dict silently. Fixed directly by Claude: script#glossary parsed/validated whenever present; cross-checks stay link-gated. +2 tests (54 py total).

## Glossary Review Round 3 — Codex
VERDICT: APPROVED. "Findings: none."

## Claude's own review (after Codex)
- Code read: dictionary values rendered via textContent (no XSS); capture-phase stopPropagation correctly blocks document bubble-phase deck handlers; lazy modal injection.
- Suites independently re-run: js 97 (8 theme + 13+28+47 popup chain incl. glossary + 9 smoke), py 54, runtime contract OK, verify_bundle OK, both decks validate OK.
- Browser smoke (file://, rebundled rag deck): term chips inherit 80px display font; modal absent until first open; open('RAG') → styled card, focus on close btn; ArrowRight WHILE open → hash unchanged (consumed); Esc closes; ArrowRight after close → #slide-2 (nav restored); 22 terms in API; presenter popup shows Terms section (RAG + LLM definitions) under notes, no modal in popup.
- Bundling proofs: rag-vector-graph has inlined premium-glossary.js; beautify-smoke does not (its single "premium-glossary.js" string is a CSS comment, matcher unaffected).
