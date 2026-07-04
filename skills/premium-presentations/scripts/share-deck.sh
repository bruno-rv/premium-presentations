#!/usr/bin/env bash
# Publish a bundled Premium Presentations deck and print a shareable URL.
# Usage: ./scripts/share-deck.sh <deck.html>
#
# Primary: deploys via `vercel` CLI (if installed and logged in).
# Fallback: serves the deck's directory over LAN via python3 -m http.server.
#
# ponytail: single file, one provider (Vercel), no auth management —
#           upgrade path: multi-file decks, other providers, scripted login.

set -euo pipefail

SRC="${1:-}"

usage() {
  sed -n '2,6p' "$0" | tail -n +2
  exit 1
}

[[ -z "$SRC" ]] && usage
[[ ! -f "$SRC" ]] && { echo "Not found: $SRC" >&2; exit 1; }
[[ "$SRC" != *.html ]] && { echo "Must be a .html file: $SRC" >&2; exit 1; }

SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"

serve_lan_fallback() {
  DIR="$(dirname "$SRC")"
  FILE="$(basename "$SRC")"
  IP="$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || hostname)"

  PORT=""
  for candidate in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010; do
    if ! python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.2); sys.exit(0 if s.connect_ex(('127.0.0.1', int(sys.argv[1]))) else 1)" "$candidate"; then
      continue
    fi
    PORT="$candidate"
    break
  done
  if [[ -z "$PORT" ]]; then
    echo "No free port in range 8000-8010 on localhost." >&2
    exit 1
  fi

  echo "Serving $DIR on your local network."
  echo "Share this URL (same Wi-Fi only): http://$IP:$PORT/$FILE"
  echo "Press Ctrl-C to stop."
  cd "$DIR" && exec python3 -m http.server "$PORT"
}

if command -v vercel >/dev/null 2>&1; then
  TMPDIR="$(mktemp -d)"
  trap 'rm -rf "$TMPDIR"' EXIT
  cp "$SRC" "$TMPDIR/index.html"

  echo "Deploying via Vercel..."
  if ! OUTPUT="$(vercel deploy "$TMPDIR" --yes 2>&1)"; then
    if grep -qi "not currently logged in\|not authorized\|no existing credentials" <<<"$OUTPUT"; then
      echo "Not logged in to Vercel. Run: vercel login" >&2
    else
      echo "$OUTPUT" >&2
    fi
    echo "Falling back to local network sharing." >&2
    serve_lan_fallback
  fi

  URL="$(grep -Eo 'https://[a-zA-Z0-9.-]+\.vercel\.app' <<<"$OUTPUT" | tail -1)"
  if [[ -z "$URL" ]]; then
    echo "$OUTPUT" >&2
    echo "Deploy succeeded but no URL was found in output." >&2
    exit 1
  fi
  echo "Deck published: $URL"
  exit 0
fi

echo "vercel CLI not found; falling back to local network sharing."
serve_lan_fallback
