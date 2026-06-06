#!/usr/bin/env bash
# Refresh generated harness skill packages from the canonical skill/ directory.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SOURCE="$ROOT/skill"
SKILL_NAME="premium-presentations"

if [[ ! -f "$SOURCE/SKILL.md" ]]; then
  echo "Missing canonical skill package: $SOURCE/SKILL.md" >&2
  exit 1
fi

sync_one() {
  local target_root="$1"
  local dest="$ROOT/$target_root/skills/$SKILL_NAME"

  mkdir -p "$(dirname "$dest")"
  rsync -a --delete \
    --exclude 'scripts/node_modules/' \
    --exclude '.DS_Store' \
    "$SOURCE/" "$dest/"

  echo "Synced $target_root/skills/$SKILL_NAME"
}

sync_one ".claude"
sync_one ".cursor"
sync_one ".agents"
sync_one ".codex"
