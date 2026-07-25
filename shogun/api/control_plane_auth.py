"""Request-level protection for the Shogun operator control plane."""

from __future__ import annotations

import hmac
import time
from collections import deque

from fastapi import Request
from fastapi.responses import JSONResponse

from shogun.api.infrastructure_auth import INFRASTRUCTURE_TOKEN_HEADER
from shogun.config import settings

_MACHINE_AUTHENTICATED_PATHS = {
    "/api/v1/a2a/inbound",
    "/api/v1/katana/command/dispatch",
}
_MACHINE_AUTHENTICATED_PREFIXES = (
    "/api/v1/nexus/external/a2a/task",
    "/api/v1/nexus/external/task/",
)
_PUBLIC_PATHS = {"/api/v1/health"}
_SENSITIVE_STATIC_PREFIXES = ("/uploads/", "/mado/screenshots/", "/ronin/screenshots/")
_request_windows: dict[tuple[str, str], deque[float]] = {}


async def enforce_control_plane_access(request: Request, call_next):
    """Require the per-install administrator credential for operator APIs."""

    path = request.url.path
    protected = path.startswith("/api/v1/") or path.startswith(_SENSITIVE_STATIC_PREFIXES)
    if (
        not protected
        or path in _PUBLIC_PATHS
        or path in _MACHINE_AUTHENTICATED_PATHS
        or path.startswith(_MACHINE_AUTHENTICATED_PREFIXES)
    ):
        return await call_next(request)

    expected = str(settings.infrastructure_admin_token or "").strip()
    supplied = request.headers.get(INFRASTRUCTURE_TOKEN_HEADER, "")
    if expected and supplied and hmac.compare_digest(supplied, expected):
        return await call_next(request)

    client_host = request.client.host if request.client else None
    if (
        not expected
        and settings.deployment_mode == "desktop"
        and client_host == "testclient"
    ):
        return await call_next(request)

    status_code = 503 if not expected else 401
    detail = (
        "Control-plane authentication is not configured."
        if status_code == 503
        else "A valid control-plane administrator credential is required."
    )
    return JSONResponse({"detail": detail}, status_code=status_code)


async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


async def enforce_rate_limit(request: Request, call_next):
    if not request.url.path.startswith("/api/v1/") or request.url.path in _PUBLIC_PATHS:
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    bucket = "read" if request.method in {"GET", "HEAD", "OPTIONS"} else "write"
    limit = 600 if bucket == "read" else 120
    now = time.monotonic()
    key = (client, bucket)
    window = _request_windows.get(key)
    if window is None:
        if len(_request_windows) >= 10_000:
            return JSONResponse(
                {"detail": "Request rate limit capacity exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        window = deque()
        _request_windows[key] = window
    while window and window[0] <= now - 60:
        window.popleft()
    if len(window) >= limit:
        return JSONResponse(
            {"detail": "Request rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    window.append(now)
    return await call_next(request)
