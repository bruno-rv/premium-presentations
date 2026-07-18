# Task 5 report: CI and clean-install release gate

## RED

Added workflow and README contract assertions to `test_skill_layout.py` before
creating the release gate. The focused test failed as intended because the
workflow and `## CI release gate` documentation did not yet exist:

```text
FAIL: missing CI release-gate workflow
FAIL: '## CI release gate' not found in README.md
```

## GREEN

Created `.github/workflows/ci.yml` with a single Ubuntu release-gate job:

- Node.js 20 and Python 3.12 setup with dependency caches.
- `npm ci`, Python requirements, and managed Chromium installation.
- Focused static manifest/bootstrap contracts and `bootstrap.py --check`.
- Focused presenter, popup, and theme-visual Node tests plus aggregate Node
  tests.
- Aggregate Python discovery from the scripts directory (required for the
  test modules' imports).
- Runtime/contrast validators, `npm audit`, and `git diff --check`.

The workflow deliberately contains no Claude or Codex CLI install commands;
provider marketplace checks require isolated local configuration roots. README
now documents this boundary and the equivalent source-checkout commands.

## Verification

- `python3.11 skills/premium-presentations/scripts/tests/test_skill_layout.py`
  — 14 tests passed.
- `npm --prefix skills/premium-presentations/scripts ci` — 60 packages
  installed, 0 vulnerabilities reported.
- `npm audit --prefix skills/premium-presentations/scripts --audit-level=high`
  — 0 vulnerabilities.
- Temporary Python 3.11 venv requirements and Chromium installation — passed.
- Bootstrap contract/checks — passed; managed Chromium detected.
- Focused Node tests (`test:presenter`, `test:popup`, `test:theme-visuals`) —
  passed.
- Aggregate Node tests — 46 passed.
- Full Python discovery from `skills/premium-presentations/scripts`, with the
  venv interpreter explicitly first on `PATH` — 269 tests passed, 1 skipped in
  433.547 seconds, under the 10-minute CI job timeout.
- `git diff --check` — passed.

## Concerns

- The Python aggregate suite is browser-backed and takes about 7 minutes on
  this host; the workflow timeout is intentionally 10 minutes. CI's pinned
  Python 3.12 avoids the host's PEP 668 and system-`python3` mismatch.
- The aggregate must retain its scripts-directory working directory; running
  discovery from the repository root produces import-order failures in legacy
  modules.
- Real provider marketplace installs and the external smoke-deck/export gate
  remain local isolated-release exercises and are not attempted in CI.
