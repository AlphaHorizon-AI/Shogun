"""Authorization dependency for privileged infrastructure configuration routes."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status

from shogun.config import settings

INFRASTRUCTURE_TOKEN_HEADER = "X-Shogun-Infrastructure-Token"


async def require_infrastructure_admin(request: Request) -> str:
    """Allow local desktop loopback access directly; require admin token in server/remote mode."""
    client_host = request.client.host if request.client else None
    if settings.deployment_mode == "desktop" and client_host in {"127.0.0.1", "::1", "localhost", "testclient"}:
        return "local_desktop_admin"

    expected = str(settings.infrastructure_admin_token or "").strip()
    supplied = request.headers.get(INFRASTRUCTURE_TOKEN_HEADER, "")
    if not supplied and request.method in {"GET", "HEAD"}:
        supplied = (
            request.query_params.get("infrastructure_token")
            or request.query_params.get("token")
            or ""
        )
    if expected:
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid infrastructure administrator token is required.",
            )
        return "token_admin"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN must be configured.",
    )
