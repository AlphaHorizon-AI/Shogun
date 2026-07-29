"""Request-scoped connector identity used by governed memory retrieval."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_current_memory_routing: ContextVar[dict[str, Any] | None] = ContextVar(
    "current_memory_routing", default=None
)


def current_memory_routing() -> dict[str, Any] | None:
    value = _current_memory_routing.get()
    return dict(value) if value else None


@contextmanager
def memory_routing_scope(context: dict[str, Any] | None) -> Iterator[None]:
    token = _current_memory_routing.set(dict(context) if context else None)
    try:
        yield
    finally:
        _current_memory_routing.reset(token)
