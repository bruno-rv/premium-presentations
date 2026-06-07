#!/usr/bin/env bash
# Re-bundle every local generated deck that still links to ../../shared/

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECKS="$ROOT/assets/decks"
shopt -s nullglob

if [[ ! -d "$DECKS" ]]; then
  echo "No assets/decks/ directory found. Generate a deck first with scripts/new-deck.sh."
  exit 0
fi

count=0
while IFS= read -r -d '' f; do
  if grep -q '../../shared/' "$f" 2>/dev/null; then
    python3 "$ROOT/scripts/bundle_deck.py" "$f" --in-place
    count=$((count + 1))
  fi
done < <(find "$DECKS" -name '*-slides.html' -print0)

if [[ "$count" -eq 0 ]]; then
  echo "No linked decks found under assets/decks/ (all standalone or empty)."
else
  echo "Re-bundled $count deck(s)."
fi
