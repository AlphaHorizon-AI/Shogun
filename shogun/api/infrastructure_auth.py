"""Authorization dependency for privileged infrastructure configuration routes."""

from __future__ import annotations

import hmac
import ipaddress

from fastapi import HTTPException, Request, status

from shogun.config import settings

INFRASTRUCTURE_TOKEN_HEADER = "X-Shogun-Infrastructure-Token"


def _is_loopback_client(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.casefold() == "localhost"


async def require_infrastructure_admin(request: Request) -> str:
    """Allow a local desktop admin or a server admin presenting the secret token."""

    expected = str(settings.infrastructure_admin_token or "").strip()
    supplied = request.headers.get(INFRASTRUCTURE_TOKEN_HEADER, "")
    if expected:
        if not supplied or not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="A valid infrastructure administrator token is required.",
            )
        return "token_admin"

    if settings.deployment_mode == "desktop" and _is_loopback_client(
        request.client.host if request.client else None
    ):
        return "local_primary_admin"

    if settings.deployment_mode == "server":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN must be configured in server mode.",
        )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Infrastructure configuration is restricted to the local Primary Admin.",
    )
