# Reliability, Portability, and Theme Homage Implementation Plan

> Execution mode: three parallel implementation agents with non-overlapping ownership, followed by root integration and an independent review.

**Goal:** Guarantee embedded homage visuals for every theme, fix the audited security and portability defects, and make the repository validate cleanly in Claude Code and Codex.

**Architecture:** Introduce a single Python theme-registry contract shared by generation, bundling, and validation. Harden the two runtime transport boundaries independently: browser presenter messaging and LAN synchronization. Make scaffolding transactional, then make tests and CI exercise the same public commands users run.

**Stack:** Python 3.12, POSIX shell, browser JavaScript, Node test runner, Playwright, Claude Code plugin validator.

---

### Task 1: Atomic theme registry and safe scaffolding

**Files:**

- Create: `scripts/theme_visuals.py`
- Create: `scripts/render_template.py`
- Create: `scripts/test_theme_visuals_contract.py`
- Create: `scripts/test_new_deck.py`
- Modify: `scripts/generate_theme.py`
- Modify: `scripts/bundle_deck.py`
- Modify: `scripts/validate_runtime_contract.py`
- Modify: `scripts/new-deck.sh`
- Modify: `scripts/test_generate_theme.py`
- Modify: `scripts/test_bundle_deck.py`
- Modify: theme visual tests that assume exactly four themes

**Step 1: Write failing contract tests**

Cover CSS/manifest parity, missing and duplicate roles, unsafe basenames, missing files, invalid WebP bytes, special-character deck titles, rollback after failure, and bundler rejection of assets outside the deck/shared roots.

**Step 2: Run focused tests and capture the expected failures**

```bash
python3 -m unittest scripts.test_theme_visuals_contract scripts.test_generate_theme scripts.test_new_deck scripts.test_bundle_deck
```

**Step 3: Implement the shared registry contract**

Expose functions equivalent to:

```python
def load_and_validate_registry(css_dir: Path, visuals_dir: Path, manifest_path: Path) -> dict[str, dict[str, str]]: ...
def validate_webp(path: Path) -> None: ...
def install_theme_atomic(..., hero_image: Path, map_image: Path, ...) -> None: ...
```

Require exact theme-set parity and exact `hero`/`map` roles. Remove runtime filename guessing.

**Step 4: Implement escaped, transactional scaffolding**

Render literal placeholders with `html.escape(value, quote=True)`, build inside a staging directory, run bundle/spec/doctor there, and rename only after success. Ensure signal and error traps remove the staging directory.

**Step 5: Constrain local bundler reads**

Resolve symlinks and accept local CSS/JS only when the final path is under the deck directory or `assets/shared`.

**Step 6: Run focused and contract verification**

```bash
python3 -m unittest scripts.test_theme_visuals_contract scripts.test_generate_theme scripts.test_new_deck scripts.test_bundle_deck
python3 scripts/validate_runtime_contract.py
node scripts/test_theme_visuals.mjs
```

### Task 2: Presenter, LAN, and portability hardening

**Files:**

- Create: `scripts/validate_portability.py`
- Create or modify: portability validator tests
- Modify: `assets/shared/premium-presenter.js`
- Modify: `assets/shared/premium-follow.js`
- Modify: `scripts/share-deck.sh`
- Modify: `scripts/lan-sync-server.py`
- Modify: `scripts/deck_doctor.py`
- Modify: presenter/postMessage/popup/follower/LAN/diagram validator tests

**Step 1: Write failing security regressions**

Add tests for a wrong origin, wrong source window, missing session, malicious note HTML, missing/incorrect LAN token, directory disclosure, remote/relative media references, and a literal early `</script>`.

**Step 2: Run the focused suites and capture failures**

```bash
node scripts/test_presenter_postmessage.mjs
node scripts/test_presenter_popup.mjs
node scripts/test_follow.mjs
python3 -m unittest scripts.test_lan_sync_server scripts.test_deck_doctor
```

**Step 3: Enforce presenter peer identity**

Carry transport metadata into the receiver. For direct window traffic, require a matching origin, expected peer source, and established session; permit only the initial opener adoption handshake. Use a concrete target origin on HTTP(S). Sanitize remote notes before using `innerHTML`.

**Step 4: Tokenize and isolate LAN sharing**

Serve a temporary directory containing only `index.html`. Generate `secrets.token_urlsafe(32)`, require it on `/slide`, and propagate `room` through follower polling.

**Step 5: Enforce offline portability and structural scripts**

Reject fetchable HTML/CSS references after bundling. Integrate the validator into the doctor. Replace the impossible inline-script check with a structural opening/closing tag check that catches injected literal closing tags.

**Step 6: Run focused verification**

```bash
node scripts/test_presenter_postmessage.mjs
node scripts/test_presenter_popup.mjs
node scripts/test_follow.mjs
python3 -m unittest scripts.test_lan_sync_server scripts.test_deck_doctor
```

### Task 3: Claude/Codex metadata, aggregate tests, dependencies, and CI

**Files:**

- Create: `.github/workflows/ci.yml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `scripts/test_skill_layout.py`
- Modify: `scripts/test_3d_modes.mjs`

**Step 1: Add failing metadata and script-coverage tests**

Assert schema-safe Claude paths, resolvable Claude and Codex entry points, matching package/lock versions, aggregate suite coverage, and the five current 3D modes.

**Step 2: Run and capture failures**

```bash
python3 -m unittest scripts.test_skill_layout
node --test scripts/test_3d_modes.mjs
npm run test:bundle
claude plugin validate . --strict
```

**Step 3: Correct metadata and public scripts**

Use `"commands": ["./commands/"]`, remove unsupported marketplace keys, give `test:bundle` its example deck argument, register the 3D suite, and create `test:all`.

**Step 4: Refresh dependencies and metadata**

Synchronize the lockfile at version 2.0.0 and override the vulnerable development-only `form-data` version to a patched release without changing production behavior.

**Step 5: Add a complete CI gate**

Install Node 20, Python 3.12, project requirements, Playwright Chromium, and Claude Code. Run aggregate tests, theme/runtime validators, strict Claude validation, Codex manifest validation, audit, and whitespace checks.

**Step 6: Verify**

```bash
npm run test:all
npm audit
claude plugin validate . --strict
python3 $HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

### Task 4: Integration, documentation, and independent review

**Files:**

- Modify: `README.md`
- Modify: `SKILL.md`
- Modify: `references/runtime.md`
- Modify: any command documentation affected by the implementation

**Step 1: Review all agent diffs for overlap and contract consistency**

Verify that the theme generator, bundler, runtime contract, scaffolder, and docs describe the same fail-closed behavior.

**Step 2: Update public documentation**

Document required theme homage assets, atomic theme generation, safe LAN URLs, portability failures, Claude/Codex validation, and the aggregate test command.

**Step 3: Run complete verification from a clean temporary deck**

```bash
npm run test:all
python3 scripts/validate_runtime_contract.py
python3 scripts/test_theme_visuals.py
claude plugin validate . --strict
python3 $HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
npm audit
git diff --check
```

Create a deck with a hostile/special-character title, inspect the resulting embedded data URIs, and use Playwright to switch through every discovered theme while checking image dimensions and console output.

**Step 4: Dispatch an independent read-only reviewer**

Ask the reviewer to inspect requirements, security boundaries, portability, compatibility, test completeness, and documentation. Address technically valid findings and rerun affected verification.
