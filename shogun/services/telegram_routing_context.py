"""Request-scoped Telegram chat/topic routing for inbound-to-outbound replies."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_current_telegram_routing: ContextVar[dict[str, Any] | None] = ContextVar("current_telegram_routing", default=None)


def current_telegram_routing() -> dict[str, Any] | None:
    context = _current_telegram_routing.get()
    return dict(context) if context else None


@contextmanager
def telegram_routing_scope(context: dict[str, Any] | None) -> Iterator[None]:
    token = _current_telegram_routing.set(dict(context) if context else None)
    try:
        yield
    finally:
        _current_telegram_routing.reset(token)
