#!/usr/bin/env bash
# Re-bundle every deck that still links to ../../shared/

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
shopt -s nullglob
DECK_ROOT="$ROOT/assets/decks"

if [[ ! -d "$DECK_ROOT" ]]; then
  echo "No generated decks found under assets/decks/."
  exit 0
fi

count=0
while IFS= read -r -d '' f; do
  if grep -q '../../shared/' "$f" 2>/dev/null; then
    python3 "$ROOT/scripts/bundle_deck.py" "$f" --in-place
    count=$((count + 1))
  fi
done < <(find "$DECK_ROOT" -name '*-slides.html' -print0)

if [[ "$count" -eq 0 ]]; then
  echo "No linked decks found under assets/decks/ (all standalone or empty)."
else
  echo "Re-bundled $count deck(s)."
fi
