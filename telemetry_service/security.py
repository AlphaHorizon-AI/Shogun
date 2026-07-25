"""Pseudonymous key derivation and restricted dashboard authentication."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException

from telemetry_service.config import settings


def installation_key(raw_identifier: str) -> str:
    return hmac.new(
        settings.hmac_secret.encode("utf-8"),
        raw_identifier.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def nonce_key(raw_nonce: str) -> str:
    return hmac.new(
        settings.hmac_secret.encode("utf-8"),
        f"nonce:{raw_nonce}".encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def require_identity_proxy(
    x_auth_request_email: str | None = Header(default=None),
    x_auth_request_groups: str | None = Header(default=None),
    x_auth_request_mfa: str | None = Header(default=None),
    x_telemetry_identity_proxy_secret: str | None = Header(default=None),
) -> str:
    """Require an upstream EU-hosted SSO proxy assertion with MFA."""
    expected = settings.identity_proxy_secret
    if not expected or not x_telemetry_identity_proxy_secret or not hmac.compare_digest(
        x_telemetry_identity_proxy_secret, expected
    ):
        raise HTTPException(401, "Trusted identity proxy required")
    groups = {item.strip() for item in (x_auth_request_groups or "").split(",")}
    if settings.allowed_admin_group not in groups:
        raise HTTPException(403, "Telemetry dashboard group membership required")
    if (x_auth_request_mfa or "").casefold() != "true":
        raise HTTPException(403, "Multi-factor authentication required")
    if not x_auth_request_email:
        raise HTTPException(401, "Named administrator identity required")
    return x_auth_request_email[:255]
