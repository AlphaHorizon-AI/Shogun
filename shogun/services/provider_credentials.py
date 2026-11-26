"""Encryption helpers for model-provider credentials stored in JSON config."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings

_SENSITIVE_KEYS = {
    "api_key",
    "api-key",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "secret",
    "client_secret",
    "oauth_client_secret",
}
_MASKED_VALUES = {"********", "••••••••"}


def _get_fernet(key: str | None = None) -> Fernet:
    """Derive a 32-byte URL-safe base64 key from settings.vault_encryption_key."""
    key_bytes = (key or settings.vault_encryption_key).encode("utf-8")
    hashed = hashlib.sha256(key_bytes).digest()
    fernet_key = base64.urlsafe_b64encode(hashed)
    return Fernet(fernet_key)


def encrypt_password(password: str) -> str:
    return _get_fernet().encrypt(password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted: str) -> str:
    payload = encrypted.encode("utf-8")
    try:
        return _get_fernet().decrypt(payload).decode("utf-8")
    except InvalidToken:
        legacy_key = "change-me-to-a-fernet-base64-key"
        if settings.vault_encryption_key == legacy_key:
            raise
        return _get_fernet(legacy_key).decrypt(payload).decode("utf-8")


def protect_provider_config(
    config: dict[str, Any] | None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Encrypt provider credentials while retaining masked existing values."""

    def protect(value: Any, previous: Any = None, key: str = "") -> Any:
        if isinstance(value, dict):
            old = previous if isinstance(previous, dict) else {}
            protected = {name: protect(item, old.get(name), name) for name, item in value.items()}
            for name, old_value in old.items():
                if name in protected:
                    continue
                retained = retain_secrets(old_value, name)
                if retained is not None:
                    protected[name] = retained
            return protected
        if isinstance(value, list):
            return [protect(item) for item in value]
        if key.casefold() not in _SENSITIVE_KEYS or not isinstance(value, str) or not value:
            return value
        if value in _MASKED_VALUES and isinstance(previous, str):
            return previous
        if value.startswith("enc:"):
            return value
        return "enc:" + encrypt_password(value)

    def retain_secrets(value: Any, key: str = "") -> Any:
        if key.casefold() in _SENSITIVE_KEYS and isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            retained = {
                name: secret
                for name, item in value.items()
                if (secret := retain_secrets(item, name)) is not None
            }
            return retained or None
        if isinstance(value, list):
            retained_items = [secret for item in value if (secret := retain_secrets(item)) is not None]
            return retained_items or None
        return None

    return protect(dict(config or {}), dict(existing or {}))


def reveal_provider_secret(value: Any) -> str | None:
    """Return a usable secret from encrypted or legacy plaintext storage."""
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("enc:"):
        return decrypt_password(value.removeprefix("enc:"))
    return value


def provider_api_key(config: dict[str, Any] | None) -> str | None:
    config = config or {}
    return reveal_provider_secret(
        config.get("api_key")
        or config.get("api-key")
        or config.get("access_token")
        or config.get("token")
    )


async def migrate_provider_credentials(session: AsyncSession) -> int:
    """Encrypt legacy plaintext provider credentials in place."""
    from shogun.db.models.model_provider import ModelProvider

    providers = (await session.execute(select(ModelProvider))).scalars().all()
    changed = 0
    for provider in providers:
        protected = protect_provider_config(provider.config)
        if protected != provider.config:
            provider.config = protected
            changed += 1
    if changed:
        await session.flush()
    return changed
