#!/usr/bin/env python3
"""LAN follow-along sync server for Premium Presentations decks.

Stdlib-only (http.server, json) ThreadingHTTPServer: serves the deck's
directory statically, plus a tiny in-memory current-slide-id endpoint:

  POST /slide {"id": "<slide-id>"}   presenter write (?present=1 client)
  GET  /slide                        audience read   (?follow=1 client)

Security (documented, explicit): binds 0.0.0.0 so audience devices on the
LAN can reach it — localhost-only would defeat the feature. No auth:
acceptable for a venue LAN, single presenter, ephemeral in-memory state, no
disk persistence, no remote exposure intended. Do not run this on an
untrusted network.

Usage:
  ./scripts/lan-sync-server.py <deck-dir> <port>
"""

from __future__ import annotations

import json
import re
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# In-memory only; single presenter, single room (no disk, no multi-room state).
_current: dict[str, str | None] = {"id": None}

# Small body cap: presenter slide ids are short strings, never large payloads.
_MAX_BODY = 4096
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def make_handler(directory: str) -> type[SimpleHTTPRequestHandler]:
    class SyncHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

        def do_POST(self) -> None:
            if self.path != "/slide":
                self.send_error(404)
                return

            try:
                length = int(self.headers.get("Content-Length", ""))
                if length < 0:
                    raise ValueError("negative Content-Length")
            except ValueError:
                self.send_error(400, "Missing or invalid Content-Length")
                return

            if length > _MAX_BODY:
                self.send_error(413, "Request body too large")
                return

            try:
                raw = self.rfile.read(length) if length else b"{}"
                payload = json.loads(raw or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be a JSON object")
                slide_id = payload.get("id")
                if slide_id is not None and not (
                    isinstance(slide_id, str) and _ID_RE.match(slide_id)
                ):
                    raise ValueError("id must be null or a bounded id string")
            except (ValueError, TypeError):
                self.send_error(400, "Malformed JSON body")
                return

            _current["id"] = slide_id
            self._json({"ok": True})

        def do_GET(self) -> None:
            if self.path == "/slide":
                self._json(_current)
                return
            super().do_GET()

        def _json(self, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:  # quieter default logging
            pass

    return SyncHandler


def serve(directory: str, port: int, *, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    handler = make_handler(directory)
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: lan-sync-server.py <deck-dir> <port>", file=sys.stderr)
        return 1
    directory, port_str = argv
    if not Path(directory).is_dir():
        print(f"Not a directory: {directory}", file=sys.stderr)
        return 1
    try:
        port = int(port_str)
    except ValueError:
        print(f"Invalid port: {port_str}", file=sys.stderr)
        return 1

    httpd = serve(directory, port)
    print(f"Serving {directory} on 0.0.0.0:{port} (POST/GET /slide + static files)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
