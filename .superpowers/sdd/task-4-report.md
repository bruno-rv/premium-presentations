# Task 4 report: prerequisite bootstrap and truthful documentation

## RED

Added `test_bootstrap.py` before creating the production helper. The focused
test command failed because the requested script did not exist:

```text
python3 skills/premium-presentations/scripts/tests/test_bootstrap.py
FFFFF
FAILED (failures=5)
... bootstrap.py has not been implemented
```

The tests cover Python 3.10 and Node 18 gates, interpreter-bound install
commands, read-only check mode, and ordered install execution.

## GREEN

Created the stdlib-only `bootstrap.py` with:

- Python >=3.10 and Node >=18 checks plus Bash and Playwright/managed Chromium
  prerequisite reporting.
- `--check` inspection with no install calls or writes.
- `--install-browser-deps` commands built from `sys.executable`:
  `-m pip install -r requirements.txt`, then `-m playwright install chromium`.
- Clear failures for unsupported Python and failed subprocesses.

Focused tests pass under the available supported interpreter:

```text
python3.11 skills/premium-presentations/scripts/tests/test_bootstrap.py
.....
Ran 5 tests ...
OK
```

The local Python 3.11 environment does not have Playwright installed, so the
real read-only check reports that prerequisite as missing and exits 1 (the
expected pre-install result):

```text
python3.11 skills/premium-presentations/scripts/bootstrap.py --check
OK: Python 3.11.15 (requires >= 3.10)
OK: Node.js 25.9.0 (requires >= 18)
OK: Bash found at /bin/bash
MISSING: Playwright is not installed
```

The system `python3` is 3.9 and is correctly rejected by both modes; README
now tells users to substitute a supported executable such as `python3.11`.

## Package and documentation checks

- Updated package/lock roots to version 2.0.0 with Node >=18 metadata.
- Added the narrow `form-data` 4.0.6 override (the prior 4.0.5 advisory is
  resolved without broad dependency upgrades).
- Documented Python/Node/Bash, macOS/Linux/WSL, plugin restart requirements,
  bootstrap commands, workspace-safe output, source-clone legacy output, and
  intentionally untracked PDF/cover/handout artifacts.

Fresh verification:

```text
python3.11 skills/premium-presentations/scripts/tests/test_skill_layout.py
..........
Ran 10 tests ...
OK

npm --prefix skills/premium-presentations/scripts ci
added 60 packages, and audited 61 packages ...
found 0 vulnerabilities

npm --prefix skills/premium-presentations/scripts audit --audit-level=high
found 0 vulnerabilities

python3.11 -m py_compile skills/premium-presentations/scripts/bootstrap.py \
  skills/premium-presentations/scripts/tests/test_bootstrap.py
git diff --check
```

## Self-review and concerns

- The diff is limited to the six requested task files plus this report; no
  unrelated reliability changes were imported.
- Install subprocesses use argument lists (no shell), and the check path never
  invokes them.
- An actual Playwright install was not run in the local Python 3.11 environment
  because it is intentionally absent; CI or a user can run the explicit install
  mode after selecting a supported interpreter.

## Commit

Task commit: `feat: add prerequisite bootstrap and release docs` (hash reported
by the agent handoff; the report intentionally avoids a self-referential hash).
