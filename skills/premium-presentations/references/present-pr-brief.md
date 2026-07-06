# {TITLE} — PR Review Deck Brief

> Recipe-specific Content-First Brief for `/present-pr`. Mirrors the mandatory
> brief in `SKILL.md` / `slide-spec-template.md`, with PR-appropriate field
> mappings so the generated spec ships 0 placeholder strings. Fill every
> `{…}` field from real `git diff`/`git log`/touched-file content — never
> leave a placeholder in the delivered spec.

---

## Lesson Metadata (PR mapping)

| Field | Source | Value |
|-------|--------|-------|
| **Code / Title** | PR title, or branch name if no PR | {TITLE} |
| **Duration** | estimated from slide count (~1 min/slide) | {N} min |
| **Instructor** | `git log -1 --format='%an'` (commit author) | {AUTHOR} |
| **Module** | dropped — not a placeholder, deliberately absent for this recipe | — |
| **Layer** | dropped — not a placeholder, deliberately absent for this recipe | — |
| **Hook** | the PR's problem statement (what was broken/missing before) | "{HOOK}" |
| **Closing** | the shipped outcome (what is true now that wasn't before) | "{CLOSING}" |

---

## Content-First Brief

| Field | Answer |
|-------|--------|
| **Topic archetype** | code change / process (fixed for this recipe) |
| **Hero moment** | the PR's core change — the single diff hunk or behavior shift the audience must carry out |
| **Audience's wrong assumption at entry** | the misconception the change corrects (derive from the problem statement / commit messages) |
| **Exclusion list** | data-story components, historical-narrative components (pre-set — a code-change deck does not need them) |
| **Narrative arc type** | problem → solution (fixed for this recipe) |

---

## Context Sources (fill from real repo state, never invent)

| Source | Command |
|--------|---------|
| Diff | `gh pr diff` (if a PR exists for the branch); fallback `git diff <base>..HEAD` |
| Commit narrative | `git log <base>..HEAD --format='%h %s'` |
| Author | `git log -1 --format='%an'` |
| Touched-file docs | co-located `README`/module docstring for each changed path, when present |

`<base>`: `$1` if given to `/present-pr`; else `git merge-base --fork-point main HEAD`
if that resolves; else the `main`/`HEAD` merge-base if a local `main` exists and
actually diverges from `HEAD`; else `HEAD~3` if the branch has no PR ancestry;
else the repo's root commit, or a loud failure asking for an explicit base if
even `HEAD~3` is unavailable (shallow clone / brand-new repo). See
`commands/present-pr.md` step 1 (`resolve_base`) for the executable version —
both files must stay in sync.

---

## Narrative Arc (problem → solution, fixed shape)

| Act | Title | What the audience experiences |
|-----|-------|-------------------------------|
| 0 | Hook | The problem: what was broken, missing, or slow before this change |
| 1 | The Change | What the diff actually does — walk the core hunk(s) |
| 2 | Why This Way | The design tradeoff or misconception the change corrects |
| 3 | Close | The shipped outcome — what is true now |

---

## Slide Map

Populate using the same `# | Act | Type | Title | Key Content | Visual Pattern |
Why Panel | Voiceover Beat | Speaker Notes` shape as `slide-spec-template.md`.
Every Content row names one concrete component from `components.md`'s routing
table — never a bare heading + paragraph. Every row carries Speaker Notes.

---

## Evidence Data

Real diff hunks, commit messages, and file/line references — no invented
statistics. This section IS the diff/log content gathered above, distilled
into slide-ready facts.

---

*Recipe brief format: premium-presentations `/present-pr` — funnels into the
existing `new-deck.sh` → spec → generate → `deck_doctor.py` pipeline verbatim.
No diff-to-slide bypass of the spec contract.*
