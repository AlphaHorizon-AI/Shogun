"""Outbound destination policy for Nexus callbacks and dispatch."""

from __future__ import annotations

from shogun.config import settings
from shogun.services.ssrf_guard import ValidatedDestination, validate_outbound_url


def validate_nexus_destination(url: str) -> ValidatedDestination:
    """Require Nexus destinations to be explicitly allowlisted."""

    return validate_outbound_url(
        url,
        policy="allowlist_only",
        allowlist=settings.outbound_allowlist,
        allow_http_on_private_network=settings.allow_http_on_private_network,
        allow_http_on_public_network=settings.allow_http_on_public_network,
    )
