"""Encryption helpers for model-provider credentials stored in JSON config."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.services.email_service import decrypt_password, encrypt_password

_SENSITIVE_KEYS = {
    "api_key",
    "api-key",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "secret",
}
_MASKED_VALUES = {"********", "••••••••"}


def protect_provider_config(
    config: dict[str, Any] | None,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Encrypt provider credentials while retaining masked existing values."""

    def protect(value: Any, previous: Any = None, key: str = "") -> Any:
        if isinstance(value, dict):
            old = previous if isinstance(previous, dict) else {}
            return {name: protect(item, old.get(name), name) for name, item in value.items()}
        if isinstance(value, list):
            return [protect(item) for item in value]
        if key.casefold() not in _SENSITIVE_KEYS or not isinstance(value, str) or not value:
            return value
        if value in _MASKED_VALUES and isinstance(previous, str):
            return previous
        if value.startswith("enc:"):
            return value
        return "enc:" + encrypt_password(value)

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
