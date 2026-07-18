---
name: present-pr
description: Turn the current branch's PR/diff into a validated premium deck.
argument-hint: "[base-ref]"
allowed-tools: Bash, Read, Write, Edit
---

Turn the current branch's PR (or commit range) into a `deck_doctor`-green
premium deck grounded in the real diff — no invented content, no placeholder
slides. This funnels into the **existing** `premium-presentations` skill
pipeline verbatim: `new-deck.sh` → spec → generate → `deck_doctor.py`. Do
**not** emit slides directly and do **not** bypass the spec contract.

## 0. Set provider paths

Claude Code keeps the installed plugin immutable. Capture its bundled skill
from `CLAUDE_PLUGIN_ROOT`, and write every generated artifact beneath the
active project in `CLAUDE_PROJECT_DIR`:

```bash
plugin_root="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$plugin_root" ]; then
  echo "present-pr: CLAUDE_PLUGIN_ROOT is required" >&2
  exit 1
fi
skill_root="$plugin_root/skills/premium-presentations"
project_root="${CLAUDE_PROJECT_DIR}"
if [ -z "$project_root" ]; then
  echo "present-pr: CLAUDE_PROJECT_DIR is required" >&2
  exit 1
fi
deck_root="$project_root/assets/decks"
themes_css="$project_root/assets/shared/premium-themes.css"
if [ ! -f "$themes_css" ]; then
  themes_css="$skill_root/assets/shared/premium-themes.css"
fi
cd "$project_root"
```

The `cd` is deliberately after both roots are captured. All subsequent
commands use these absolute paths; do not substitute cwd-relative
`skills/premium-presentations` paths.

## 1. Determine the base ref

Resolve one `base` commit and reuse it for every diff/log below — never
inline a literal `main` in the git commands themselves, since `main` may
not exist locally (worktrees, orphan branches, shallow clones).

```bash
resolve_base() {
  # 1. Explicit argument always wins.
  if [ -n "$1" ]; then
    echo "$1"
    return 0
  fi
  # 2. Real PR ancestry: where this branch forked from main.
  local fork_point
  fork_point="$(git merge-base --fork-point main HEAD 2>/dev/null)"
  if [ -n "$fork_point" ]; then
    echo "$fork_point"
    return 0
  fi
  # 3. main exists locally and actually diverges from HEAD (not just a
  #    missing fork-point cache entry, e.g. a shallow clone).
  if git show-ref --verify --quiet refs/heads/main; then
    local mb head
    mb="$(git merge-base main HEAD 2>/dev/null)"
    head="$(git rev-parse HEAD)"
    if [ -n "$mb" ] && [ "$mb" != "$head" ]; then
      echo "$mb"
      return 0
    fi
  fi
  # 4. No usable main (orphan branch, worktree without main, or HEAD==main):
  #    the same synthetic stand-in the skill's own test fixtures use.
  if git rev-parse --verify --quiet HEAD~3 >/dev/null 2>&1; then
    echo "HEAD~3"
    return 0
  fi
  # 5. History too short even for HEAD~3 (shallow clone, brand-new repo):
  #    fall back to the root commit, or fail loudly rather than guess.
  local root
  root="$(git rev-list --max-parents=0 HEAD 2>/dev/null | tail -1)"
  if [ -n "$root" ] && [ "$root" != "$(git rev-parse HEAD)" ]; then
    echo "$root"
    return 0
  fi
  echo "present-pr: cannot resolve a comparison base — no main branch, no fork-point, and fewer than 3 commits of history. Pass an explicit base ref: /present-pr <base>" >&2
  return 1
}

base="$(resolve_base "$1")" || exit 1
```

## 2. Gather real repo context (never invent facts)

```bash
gh pr diff 2>/dev/null || git diff "$base"..HEAD
git log "$base"..HEAD --format='%h %s'
git log -1 --format='%an'   # commit author -> Instructor field
```

For every changed path, check for a co-located `README` or a module
docstring — read it if present; it grounds the "why" behind the change.

## 3. Fill the recipe Content-First Brief

Copy `$skill_root/references/present-pr-brief.md` and fill
every `{…}` field from the content gathered in step 2:

- **Topic archetype:** code change / process (fixed).
- **Hero moment:** the PR's core change — the single diff hunk or behavior
  shift the audience must carry out.
- **Audience's wrong assumption at entry:** the misconception the change
  corrects — derive from the problem statement / commit messages, not a
  generic guess.
- **Narrative arc:** problem → solution (fixed).
- **Exclusion list:** data-story / historical-narrative components
  (pre-set — a code-change deck does not need them).
- **Code/Title:** the PR title, or the branch name if there is no open PR.
- **Instructor:** `git log -1 --format='%an'`.
- **Module / Layer:** omit — dropped for this recipe, not a placeholder.
- **Duration:** estimate from slide count (~1 minute/slide).
- **Hook / Closing:** the PR's problem statement / the shipped outcome.

The filled brief must ship **zero** `{…}` placeholder strings before moving
to step 4.

## 4. Run the existing pipeline (do not skip any step)

```bash
slug="<slug>"
title="<title>"
count="<count>"
deck_dir="$deck_root/$slug"

"$skill_root/scripts/new-deck.sh" \
  --output-dir "$deck_dir" \
  --themes-css "$themes_css" \
  <theme> "$slug" "$title" "$count"
```

Use the filled brief to author the slide spec content (Narrative Arc, Slide
Map, Evidence Data) exactly as any other deck build would, following
`SKILL.md`'s Content-First Brief → spec → generate workflow. Then gate:

```bash
python3 "$skill_root/scripts/deck_doctor.py" \
  "$deck_dir/${slug}-slides.html" \
  "$deck_dir/${slug}-slide-spec.md"
```

`deck_doctor.py` must exit **0** before the deck is delivered. Non-zero exit
→ fix the reported issues (deck or spec), re-bundle if the fix touched
`assets/shared/` or `assets/templates/`, re-run — same standard as any other
deck build, no exception for this recipe.

## Notes

- If `gh` is unavailable or the branch has no open PR, the `git diff`
  fallback is not a degraded path — it is the primary mechanism for local
  review decks.
- This command produces exactly one deliverable: a gate-passing deck under
  `$project_root/assets/decks/<slug>/`. It never modifies the plugin's shared
  runtime, themes, or validators. If the user asks for exports, pass the same
  absolute deck path to the bundled scripts:

  ```bash
  python3 "$skill_root/scripts/export_pdf.py" "$deck_dir/${slug}-slides.html"
  python3 "$skill_root/scripts/og_cover.py" "$deck_dir/${slug}-slides.html"
  python3 "$skill_root/scripts/export_handout.py" "$deck_dir/${slug}-slides.html"
  ```
