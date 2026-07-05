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
| **Compile** | Spec → validated deck; deck doctor is a hard gate | Strong (v1.1.1) |
| **Deliver** | Presenter popup, rehearsal, timer, annotations | Strong, keep deepening |
| **Own** | Single file, no CDN, offline, share anywhere | Strong, distribution rough |

## Non-goals (anti-Gamma guardrails)

- No cloud accounts, no hosted backend, no SaaS analytics.
- No WYSIWYG editor — editing goes through the agent + spec.
- No collaboration/comments, no template marketplace.
- Litmus test: a feature that requires a persistent server is the wrong feature.
  LAN or file-based only.

## v1.2 — Fix foundations

Close the gaps the product audit surfaced. No new surface area.

1. **Real PDF export** — Playwright (already a validator dep) renders each slide
   headless and merges. Replaces `window.print()`. Also migrates `og-cover.sh` off
   the separate system-Chrome requirement → one browser path for the whole skill.
2. **Kitchen-sink example deck shipped in the plugin package** — today the package
   contains zero inspectable decks; onboarding relies entirely on scaffolding.
3. **Handout export** — deck + mandatory speaker notes → single markdown/PDF
   leave-behind. Cheap; notes already exist on every slide.

## v1.3 — Deepen the presenter moat

4. **Rehearsal coach** — persist rehearsal runs across sessions, pace deltas vs
   plan, write suggested per-slide time budgets back into the spec.
5. **Teleprompter mode** — auto-scrolling notes in the presenter popup, sized for
   distance reading.
6. **Deck diffing / partial regeneration** — spec change → regenerate only affected
   slides. Editing is the weakest story in every AI deck tool; the spec-driven
   architecture makes it uniquely tractable here.

## v2 — Agent-native differentiators

7. **Deck recipes** — `/present-pr`, `/present-architecture`, `/present-postmortem`:
   one command, deck from live repo context. The feature a cloud editor can never build.
8. **Brand-kit theme generator** — productize the design-power theme composer:
   logo/site → theme tokens, validator enforces contrast. 4 themes → infinite.
9. **LAN audience follow-along** — `share-deck.sh` LAN mode grows slide-sync so
   audience devices track the presenter. Local-first, no SaaS.

## Process

Each version goes through the AgentSpec cycle: brainstorm → define → design → build →
ship, with deck doctor green and Codex adversarial review on non-trivial features
(established standard: presenter view, glossary).
