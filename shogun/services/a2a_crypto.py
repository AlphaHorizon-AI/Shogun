"""Domain-separated encryption for persisted A2A peer secrets."""

from __future__ import annotations

import base64
import hashlib
import hmac

from cryptography.fernet import Fernet

from shogun.config import settings

_PREFIX = "a2a:v1:"


def _fernet() -> Fernet:
    root = settings.a2a_encryption_key or hmac.new(
        settings.vault_encryption_key.encode("utf-8"),
        b"shogun:a2a:peer-secrets:v1",
        hashlib.sha256,
    ).hexdigest()
    key = base64.urlsafe_b64encode(hashlib.sha256(root.encode("utf-8")).digest())
    return Fernet(key)


def protect_peer_secret(secret: str) -> str:
    return _PREFIX + _fernet().encrypt(secret.encode("utf-8")).decode("ascii")


def reveal_peer_secret(protected: str) -> str:
    if protected.startswith(_PREFIX):
        token = protected.removeprefix(_PREFIX)
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")

    # Compatibility with records encrypted by the general credential vault.
    if protected.startswith("enc:"):
        from shogun.services.email_service import decrypt_password

        return decrypt_password(protected.removeprefix("enc:"))
    return protected
