"""Request metadata for Shogun operational audit events."""

from __future__ import annotations

import ipaddress
from contextvars import ContextVar, Token

from fastapi import Request

from shogun.config import settings

_client_ip: ContextVar[str | None] = ContextVar("shogun_client_ip", default=None)


def _trusted_proxy(address: str) -> bool:
    try:
        candidate = ipaddress.ip_address(address)
    except ValueError:
        return False
    for raw in settings.trusted_proxies.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            if candidate in ipaddress.ip_network(raw, strict=False):
                return True
        except ValueError:
            continue
    return False


def begin_request(request: Request) -> Token:
    direct = request.client.host if request.client else None
    resolved = direct
    forwarded = request.headers.get("x-forwarded-for")
    if direct and forwarded and _trusted_proxy(direct):
        candidate = forwarded.split(",", 1)[0].strip()
        try:
            resolved = str(ipaddress.ip_address(candidate))
        except ValueError:
            resolved = direct
    return _client_ip.set(resolved)


def end_request(token: Token) -> None:
    _client_ip.reset(token)


def current_client_ip() -> str | None:
    return _client_ip.get()
