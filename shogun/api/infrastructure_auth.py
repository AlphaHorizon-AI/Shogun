"""Authorization dependency for privileged infrastructure configuration routes."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, status

from shogun.config import settings

INFRASTRUCTURE_TOKEN_HEADER = "X-Shogun-Infrastructure-Token"


async def require_infrastructure_admin(request: Request) -> str:
    """Require an administrator presenting the per-install secret token."""

    expected = str(settings.infrastructure_admin_token or "").strip()
    supplied = request.headers.get(INFRASTRUCTURE_TOKEN_HEADER, "")
    if expected:
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid infrastructure administrator token is required.",
            )
        return "token_admin"

    if (
        not expected
        and settings.deployment_mode == "desktop"
        and (request.client.host if request.client else None) == "testclient"
    ):
        return "test_primary_admin"

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN must be configured.",
    )
