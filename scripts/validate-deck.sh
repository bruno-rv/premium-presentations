#!/usr/bin/env bash
# Validate a Premium Presentations HTML deck (and optional slide spec).
# Usage: ./scripts/validate-deck.sh <deck.html> [slide-spec.md]
# Exit 0 = pass, 1 = failures

set -euo pipefail

HTML="${1:-}"
SPEC="${2:-}"

if [[ -z "$HTML" || ! -f "$HTML" ]]; then
  echo "Usage: $0 <deck.html> [slide-spec.md]" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export VALIDATE_HTML="$HTML"
export VALIDATE_SPEC="$SPEC"
exec python3 "$ROOT/scripts/validate_deck.py"
