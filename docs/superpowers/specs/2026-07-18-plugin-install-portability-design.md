# Plugin Install Portability Design

**Status:** Approved for implementation by the user's 2026-07-18 request to proceed with the audited fixes and merge them.

## Goal

Make the public repository installable and safely usable from normal Claude Code and Codex plugin caches while preserving the existing source-clone workflow.

## Chosen approach

Treat the installed plugin as an immutable framework source. Scripts may read bundled templates, shared runtime files, and references from the skill root, but generated decks, specifications, custom theme files, and exports must be written to an explicit user-workspace path. Source-clone callers that omit the new options retain the existing `assets/decks/<slug>` behavior.

Alternatives rejected:

- Copying the full plugin into every project duplicates a large runtime and creates update drift.
- Continuing to write into the plugin cache and merely documenting backup steps risks silent data loss on upgrades.

## Interfaces

- `new-deck.sh --output-dir <directory> <theme> <slug> <title> [count]` writes the deck and optional spec only beneath `<directory>`. Without `--output-dir`, it keeps the legacy skill-local destination.
- `bundle_deck.py --shared-root <directory>` resolves bundled shared assets from an explicit read-only framework root when the deck is outside the skill tree.
- `generate_theme.py --themes-css <path>` mutates an explicit workspace-owned theme registry when supplied; the default remains the bundled registry for source-clone development.
- `new-deck.sh --themes-css <path>` accepts that workspace registry so generated decks can use custom themes without modifying the plugin cache.
- Claude `/present-pr` resolves tools through `${CLAUDE_PLUGIN_ROOT}` and writes beneath `${CLAUDE_PROJECT_DIR}`. The shared skill gives Codex the equivalent skill-root/workspace-root procedure.
- `scripts/bootstrap.py --check` reports prerequisites without mutation; `--install-browser-deps` installs Playwright and managed Chromium into the active Python environment.

## Safety and compatibility

- All explicit output paths are resolved and created without writing to the skill root.
- Existing positional `new-deck.sh` calls remain valid.
- Python 3.10+, Node 18+, Bash, and macOS/Linux are documented. Windows users use WSL for shell workflows.
- Plugin installation itself remains dependency-light. Browser validation/export has an explicit one-shot bootstrap.

## Verification

- Regression tests run scripts from a simulated plugin cache and assert outputs land only in a temporary workspace.
- Claude strict validation and an isolated real install must pass.
- Codex isolated marketplace add/install/list must pass.
- Node/Python suites, browser-backed Deck Doctor, exports, `npm audit`, CI syntax, and `git diff --check` must pass.
