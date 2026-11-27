"""Lightweight Mado hardening shim for bare-bones AgentFlow browser nodes."""

from __future__ import annotations

from typing import Any, Awaitable, Callable


class _RuntimeRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}

    def register(self, session_id: str, **meta: Any) -> None:
        self._sessions[session_id] = dict(meta)

    def discard(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class _PermissionGuard:
    async def check(self, action: str, **kwargs: Any) -> bool:
        return True


runtime_registry = _RuntimeRegistry()
permission_guard = _PermissionGuard()


async def governed_action(
    session_id: str,
    action_type: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    *,
    detail: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await operation()
