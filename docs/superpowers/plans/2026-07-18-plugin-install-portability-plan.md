# Plugin Install Portability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make clean Claude Code and Codex installs valid, workspace-safe, documented, and continuously verified.

**Architecture:** Keep plugin assets read-only and add explicit output/asset-root interfaces for user-owned artifacts. Preserve legacy source-clone defaults, while plugin commands and skill instructions always pass workspace paths.

**Tech Stack:** Bash, Python 3.10+, Node.js 18+, Claude Code/Codex JSON manifests, GitHub Actions.

## Global Constraints

- Do not include or modify unrelated theme, presenter, LAN, graphify, or detached-worktree changes.
- Every behavioral change follows RED → GREEN with the focused test shown below.
- Existing `new-deck.sh` positional calls remain backward compatible.
- Installed plugin caches are read-only framework sources; user artifacts belong in the active project.

---

### Task 1: Valid Claude and Codex package metadata

**Files:**
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `skills/premium-presentations/scripts/tests/test_skill_layout.py`

**Interfaces:** Claude custom component paths start with `./`; marketplace identity uses `name`, not legacy `id`.

- [ ] Add assertions that the Claude commands path is `./`-relative and marketplace has no `id`; run `python3 skills/premium-presentations/scripts/tests/test_skill_layout.py` and observe failure.
- [ ] Change commands to `["./commands/"]`, remove marketplace `id`, rerun the test and `claude plugin validate --strict .` to green.
- [ ] Verify Codex metadata with the installed plugin validator or isolated `codex plugin marketplace add`/`plugin add` commands.

### Task 2: Workspace-safe deck and custom-theme output

**Files:**
- Modify: `skills/premium-presentations/scripts/new-deck.sh`
- Modify: `skills/premium-presentations/scripts/bundle_deck.py`
- Modify: `skills/premium-presentations/scripts/generate_theme.py`
- Create or modify: `skills/premium-presentations/scripts/tests/test_new_deck.py`
- Modify: `skills/premium-presentations/scripts/tests/test_bundle_deck.py`
- Modify: `skills/premium-presentations/scripts/tests/test_generate_theme.py`

**Interfaces:**
- `new-deck.sh [--output-dir DIR] [--themes-css FILE] THEME SLUG TITLE [COUNT]`
- `bundle_deck.py ... [--shared-root DIR] [--themes-css FILE]`
- `generate_theme.py ... [--themes-css FILE]`

- [ ] Write a test that copies the skill under a simulated cache, invokes `new-deck.sh --output-dir <workspace/deck>` from an unrelated cwd, and asserts deck/spec files are in the workspace and no cache `assets/decks` directory is created. Run it and observe failure.
- [ ] Add the minimal option parser and explicit shared-root handoff; rerun the focused test to green.
- [ ] Write failing bundle tests proving external decks resolve shared assets and an explicit themes CSS file; implement `--shared-root`/`--themes-css`; rerun to green.
- [ ] Write a failing theme-generator test proving `--themes-css` changes only a temporary workspace file; implement the option and rerun to green.
- [ ] Run legacy new-deck/bundle/theme tests to prove backward compatibility.

### Task 3: Portable Claude command and Codex skill recipe

**Files:**
- Modify: `commands/present-pr.md`
- Modify: `skills/premium-presentations/SKILL.md`
- Modify: `skills/premium-presentations/references/runtime.md`
- Modify: `skills/premium-presentations/scripts/tests/test_skill_layout.py`

**Interfaces:** Claude uses `${CLAUDE_PLUGIN_ROOT}` for bundled tools and `${CLAUDE_PROJECT_DIR}` for output; Codex captures a workspace root and invokes the discovered absolute skill root.

- [ ] Add failing static contract tests rejecting cwd-relative `./skills/premium-presentations` command paths and requiring both Claude root variables plus `--output-dir`.
- [ ] Update `/present-pr` to set plugin, skill, project, and deck paths explicitly and pass them to scaffold/doctor/export commands.
- [ ] Update the shared skill/runtime instructions with the provider-neutral skill-root/workspace-root flow; rerun tests to green.

### Task 4: Prerequisite bootstrap and truthful documentation

**Files:**
- Create: `skills/premium-presentations/scripts/bootstrap.py`
- Create: `skills/premium-presentations/scripts/tests/test_bootstrap.py`
- Modify: `README.md`
- Modify: `skills/premium-presentations/SKILL.md`
- Modify: `skills/premium-presentations/scripts/package.json`
- Modify: `skills/premium-presentations/scripts/package-lock.json`

**Interfaces:** `bootstrap.py --check` is read-only; `bootstrap.py --install-browser-deps` installs the Python requirement and Chromium using `sys.executable`.

- [ ] Write failing unit tests for Python/Node version checks and generated install commands; implement the smallest stdlib bootstrap to pass.
- [ ] Sync package/lock root version to 2.0.0, record Node >=18, pin/override `form-data` to a non-vulnerable release, run `npm ci` and require `npm audit` exit 0.
- [ ] Document Python >=3.10, Node >=18, Bash, macOS/Linux/WSL, plugin restart requirements, bootstrap commands, workspace-safe output examples, and source-clone legacy behavior.
- [ ] Correct the example claim to state PDF/cover/handout are reproducible but intentionally untracked.

### Task 5: CI and clean-install release gate

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:** CI uses Node 20 and Python 3.12, installs npm/Python dependencies and Chromium, validates manifests/contracts, and runs focused plus aggregate tests.

- [ ] Add CI covering `npm ci`, `npm audit`, Node tests, Python tests/validators, Claude-compatible static manifest checks, bootstrap check, and `git diff --check`.
- [ ] Run the complete local equivalent and fix only failures caused by this branch.
- [ ] In isolated temporary config roots, run real Claude marketplace install/list and Codex marketplace add/install/list from a fresh clone/archive.
- [ ] Generate an external smoke deck, run browser-backed Deck Doctor, PDF/cover/handout exports, and assert no artifact is inside either plugin cache.

### Task 6: Review, commit, and integrate

- [ ] Review `git diff --check`, `git status --short`, and the complete diff; confirm no unrelated dirty-tree files are present.
- [ ] Commit the implementation in logical commits (metadata, output contract, command/docs/bootstrap, CI) or one coherent release commit if cross-file tests require atomicity.
- [ ] Merge `codex/plugin-portability-release` into `main`, preserving the original dirty checkout files and excluding `graphify-out/`.
- [ ] Re-run the full release gate on the merged commit, then push `main` so fresh clones receive the fix.
