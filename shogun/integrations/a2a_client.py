"""A2A (Agent-to-Agent) protocol client.

Handles outbound authenticated HTTP calls to remote Shogun A2A endpoints.
Uses HMAC-SHA256 signatures so the receiving Shogun can verify the sender.

Envelope format:
    {
        "from_name": str,
        "from_url":  str,          # sender's own /api/v1/a2a/inbound URL
        "workspace_id": str,
        "message_type": str,
        "content": str,
        "metadata": dict,
        "ts": int,                 # unix timestamp
        "sig": str                 # HMAC-SHA256 hex of canonical payload
    }
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from shogun.config import settings
from shogun.services.ssrf_guard import (
    SSRFValidationError,
    ValidatedDestination,
    log_blocked_outbound_request,
    validate_outbound_url,
)

logger = logging.getLogger(__name__)


# ── Signature helpers ─────────────────────────────────────────

def _canonical(payload: dict) -> bytes:
    """Produce a stable, sorted JSON bytes representation for signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_envelope(payload: dict, secret: str) -> str:
    """Return HMAC-SHA256 hex digest of the canonical payload."""
    return hmac.new(
        secret.encode(),
        _canonical(payload),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload: dict, sig: str, secret: str) -> bool:
    """Verify an incoming envelope's HMAC signature."""
    expected = sign_envelope(payload, secret)
    return hmac.compare_digest(expected, sig)


# ── Envelope builder ──────────────────────────────────────────

def build_envelope(
    *,
    from_name: str,
    from_url: str,
    workspace_id: str,
    message_type: str,
    content: str,
    metadata: dict | None = None,
    secret: str,
) -> dict[str, Any]:
    """Build and sign a complete A2A message envelope."""
    ts = int(time.time())
    body = {
        "from_name": from_name,
        "from_url": from_url,
        "workspace_id": workspace_id,
        "message_type": message_type,
        "content": content,
        "metadata": metadata or {},
        "ts": ts,
    }
    body["sig"] = sign_envelope(body, secret)
    return body


# ── Outbound HTTP client ──────────────────────────────────────

class A2AClient:
    """Sends authenticated A2A messages to remote Shogun peers."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    @staticmethod
    def _allowed_ports() -> set[int] | None:
        ports = {
            int(item.strip())
            for item in settings.a2a_allowed_ports.split(",")
            if item.strip()
        }
        return ports or None

    @staticmethod
    def _validate(url: str, *, endpoint_type: str) -> ValidatedDestination:
        try:
            return validate_outbound_url(
                url,
                policy=settings.a2a_destination_policy,
                allowlist=settings.outbound_allowlist,
                allow_http_on_private_network=settings.allow_http_on_private_network,
                allow_http_on_public_network=settings.allow_http_on_public_network,
                allowed_ports=A2AClient._allowed_ports(),
            )
        except SSRFValidationError as exc:
            log_blocked_outbound_request(
                exc,
                endpoint_type=endpoint_type,
                destination_policy=settings.a2a_destination_policy,
            )
            raise

    @staticmethod
    def _inbound_url(peer_url: str) -> str:
        inbound_url = peer_url.rstrip("/")
        if inbound_url.endswith("/a2a/inbound"):
            return inbound_url
        if inbound_url.endswith("/api/v1"):
            inbound_url = inbound_url[: -len("/api/v1")]
        return inbound_url.rstrip("/") + "/api/v1/a2a/inbound"

    @staticmethod
    def _identity_url(peer_url: str) -> str:
        base = peer_url.rstrip("/")
        for suffix in ("/a2a/inbound", "/a2a"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return base.rstrip("/") + "/api/v1/a2a/identity"

    def validate_peer_url(self, peer_url: str) -> None:
        """Validate a peer before any database state or background work is created."""
        self._validate(self._identity_url(peer_url), endpoint_type="a2a_invite")

    async def send(
        self,
        peer_url: str,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        """POST an envelope to a remote peer's /api/v1/a2a/inbound.

        Returns the peer's acknowledgment dict, or raises on failure.
        """
        # Normalise: peer_url may be a base URL — append the path if needed
        inbound_url = self._inbound_url(peer_url)

        destination = self._validate(inbound_url, endpoint_type="a2a_send")

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            resp = await client.post(  # lgtm[py/full-ssrf]
                destination.pinned_url,
                json=envelope,
                headers={
                    "Content-Type": "application/json",
                    "Host": destination.host_header,
                },
                extensions=destination.request_extensions,
            )
            resp.raise_for_status()
            return resp.json()

    async def ping(self, peer_url: str) -> dict[str, Any] | None:
        """Check whether a remote Shogun peer is reachable.

        Calls GET /api/v1/a2a/identity on the remote.
        Returns identity dict or None if unreachable.
        """
        identity_url = self._identity_url(peer_url)
        try:
            destination = self._validate(identity_url, endpoint_type="a2a_ping")
            async with httpx.AsyncClient(
                timeout=5.0,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                resp = await client.get(  # lgtm[py/full-ssrf]
                    destination.pinned_url,
                    headers={"Host": destination.host_header},
                    extensions=destination.request_extensions,
                )
                resp.raise_for_status()
                return resp.json()
        except SSRFValidationError as exc:
            logger.warning("A2A ping blocked for %s: %s", exc.host or "unknown-host", exc)
            return None
        except Exception as exc:
            logger.debug("A2A ping failed for %s: %s", peer_url, exc)
            return None

    async def send_invitation(
        self,
        peer_url: str,
        *,
        workspace_id: str,
        workspace_name: str,
        from_name: str,
        from_url: str,
        secret: str,
    ) -> dict[str, Any]:
        """Send a workspace join invitation to a remote peer."""
        envelope = build_envelope(
            from_name=from_name,
            from_url=from_url,
            workspace_id=workspace_id,
            message_type="invitation",
            content=f"You have been invited to collaborate on workspace: {workspace_name}",
            metadata={"workspace_name": workspace_name},
            secret=secret,
        )
        return await self.send(peer_url, envelope)


# ── Singleton ─────────────────────────────────────────────────

_client: A2AClient | None = None


def get_a2a_client() -> A2AClient:
    global _client
    if _client is None:
        _client = A2AClient()
    return _client
