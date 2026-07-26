"""Request metadata made available to Gensui audit writers."""

from __future__ import annotations

import ipaddress
from contextvars import ContextVar, Token

from fastapi import Request

from gensui.config import gensui_settings

_request_metadata: ContextVar[tuple[str | None, str | None]] = ContextVar(
    "gensui_request_metadata",
    default=(None, None),
)


def _trusted_proxy(address: str) -> bool:
    try:
        candidate = ipaddress.ip_address(address)
    except ValueError:
        return False
    for raw in gensui_settings.gensui_trusted_proxies.split(","):
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
    client_ip = direct
    forwarded = request.headers.get("x-forwarded-for")
    if direct and forwarded and _trusted_proxy(direct):
        candidate = forwarded.split(",", 1)[0].strip()
        try:
            client_ip = str(ipaddress.ip_address(candidate))
        except ValueError:
            client_ip = direct
    user_agent = request.headers.get("user-agent")
    return _request_metadata.set((client_ip, user_agent[:500] if user_agent else None))


def end_request(token: Token) -> None:
    _request_metadata.reset(token)


def current_request_metadata() -> tuple[str | None, str | None]:
    return _request_metadata.get()
