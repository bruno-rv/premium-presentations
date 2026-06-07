#!/usr/bin/env bash
# Bundle a deck into a single standalone HTML file (inline assets/shared CSS/JS).
# Usage: ./scripts/bundle-deck.sh <deck.html> [--in-place]

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/bundle_deck.py" "$@"
