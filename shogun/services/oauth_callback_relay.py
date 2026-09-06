"""Tiny loopback callback relay for OAuth clients with fixed redirect ports.

OpenAI's public Codex OAuth client allow-lists the loopback callbacks used by
Codex itself. Shogun receives that callback on the allow-listed port and
immediately redirects the browser to the provider-specific FastAPI callback.
"""

from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit, urlunsplit

_LOCK = threading.Lock()
_TARGETS: dict[str, tuple[str, float]] = {}
_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None


class _RelayHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
        parsed = urlsplit(self.path)
        if parsed.path != "/auth/callback":
            self.send_error(404)
            return
        try:
            if len(self.path) > 16384:
                raise ValueError
            query = parse_qs(parsed.query, max_num_fields=12)
            if len(query.get("state", [])) != 1 or any(len(value) != 1 for value in query.values()):
                raise ValueError
            state = query["state"][0]
        except ValueError:
            self.send_error(400, "Invalid OAuth callback")
            return
        with _LOCK:
            entry = _TARGETS.pop(state, None)
        if not entry or entry[1] < time.monotonic():
            self.send_error(400, "Unknown or expired OAuth state")
            return
        target = entry[0]
        target_parts = urlsplit(target)
        location = urlunsplit((target_parts.scheme, target_parts.netloc, target_parts.path, parsed.query, ""))
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def log_message(self, _format: str, *_args) -> None:
        return


def _ensure_server() -> ThreadingHTTPServer:
    global _SERVER, _THREAD
    with _LOCK:
        if _SERVER:
            return _SERVER
        last_error: OSError | None = None
        for port in (1455, 1457):
            try:
                server = ThreadingHTTPServer(("127.0.0.1", port), _RelayHandler)
                server.daemon_threads = True
                _SERVER = server
                _THREAD = threading.Thread(
                    target=server.serve_forever,
                    name="shogun-oauth-callback",
                    daemon=True,
                )
                _THREAD.start()
                return server
            except OSError as exc:
                last_error = exc
        raise RuntimeError(
            "OpenAI sign-in needs local callback port 1455 or 1457, but both are in use. "
            "Close another Codex login window and try again."
        ) from last_error


def register_callback(state: str, target_url: str) -> str:
    """Register a one-use state and return the fixed loopback redirect URI."""
    server = _ensure_server()
    with _LOCK:
        now = time.monotonic()
        for stale in [key for key, (_, expiry) in _TARGETS.items() if expiry < now]:
            _TARGETS.pop(stale, None)
        _TARGETS[state] = (target_url, now + 600)
    port = int(server.server_address[1])
    return f"http://localhost:{port}/auth/callback"


class OAuthCallbackLogFilter(logging.Filter):
    """Uvicorn must not write one-use codes or state into its access logs."""

    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if isinstance(path, str) and "/model-providers/oauth/callback" in path:
                record.args = (client, method, path.split("?", 1)[0], version, status)
        return True
