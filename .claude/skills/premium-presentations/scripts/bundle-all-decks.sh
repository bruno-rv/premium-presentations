#!/usr/bin/env bash
# Re-bundle every bundled example deck that still links to ../../shared/

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DECKS="$ROOT/assets/decks"
shopt -s nullglob

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
