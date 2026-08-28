# Roadmap — Premium Presentations

## Vision

**Not a slide editor. A deck compiler + presenter toolkit for coding agents.**

The agent writes the deck from real context (repo, PR, docs, notes). The output is a
single portable HTML file the user owns. Delivery gets Keynote-grade presenter tools,
fully offline. We occupy the corner Gamma structurally cannot: local-first, file-based,
agent-native, validator-gated quality.

Three pillars:

| Pillar | Meaning | Today |
|--------|---------|-------|
| **Compile** | Spec → validated deck; deck doctor is a hard gate | Strong (v2.2.0) |
| **Deliver** | Presenter popup, rehearsal, timer, annotations | Strong |
| **Own** | Single file, no CDN, offline, share anywhere | Strong |

## Non-goals (anti-Gamma guardrails)

- No cloud accounts, no hosted backend, no SaaS analytics.
- No WYSIWYG editor — editing goes through the agent + spec.
- No collaboration/comments, no template marketplace.
- Litmus test: a feature that requires a persistent server is the wrong feature.
  LAN or file-based only.

## Shipped

- **v1.2** — Playwright PDF export (replaces `window.print()`), OG cover, Markdown handout export, kitchen-sink example deck in the package.
- **v1.3.0** — Rehearsal coach (persisted runs, pace deltas, suggested per-slide budgets), teleprompter mode, spec-aware partial regeneration.
- **v2.0.0** — `/present-pr`; brand-kit theme generator (`scripts/generate_theme.py`); LAN audience follow-along (`premium-follow.js`).
- **v2.1.0** — `/present-architecture` and `/present-postmortem` recipes.
- **v2.2.0** — current plugin version.

## Known limitations

- **Layout sweep bypasses the runtime theme-change event.** `validate_layout.py`
  sets `data-theme` directly instead of dispatching `premium-theme-change`,
  because that event re-renders Mermaid and rebuilds search per theme — a
  multi-fold sweep cost. Consequence: event-reactive modules (e.g.
  `premium-red-chrome.js` mounting `.red-brand-bar`) do not re-run per theme, so
  a red deck swept under a non-red theme can report a false-positive overlap.
  Revisit when: a deck bundles `premium-red-chrome.js`, a second
  event-reactive module appears, or a real false positive is reported. Any fix
  must ship a fixture with an event-reactive module, correct per-theme
  lifecycle, Mermaid readiness, and a measured perf comparison — dispatching
  the event is not automatically the right implementation.

## Process

Each version goes through the AgentSpec cycle: brainstorm → define → design → build →
ship, with deck doctor green and Codex adversarial review on non-trivial features
(established standard: presenter view, glossary).
