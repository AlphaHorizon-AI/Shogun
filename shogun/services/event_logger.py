"""Lightweight structured logging shim for AgentFlow execution events."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger("shogun.events")


class EventLogger:
    """Minimal no-DB event logger keeping AgentFlow trace calls non-blocking."""

    @staticmethod
    async def log(
        event_type: str = "",
        summary: str = "",
        *,
        severity: str = "info",
        category: str = "agent_flow",
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        level = getattr(logging, str(severity).upper(), logging.INFO)
        _log.log(level, "[%s/%s] %s", category, event_type, summary)

    @staticmethod
    async def emit(*args: Any, **kwargs: Any) -> None:
        _log.info("event: %s %s", args[:2], kwargs.get("event_type", ""))

    @staticmethod
    async def emit_governance_event(*args: Any, **kwargs: Any) -> None:
        _log.info("governance: %s", kwargs.get("event_type", ""))

    @staticmethod
    async def emit_incident_event(*args: Any, **kwargs: Any) -> None:
        _log.warning("incident: %s %s", kwargs.get("event_type", ""), kwargs.get("summary", ""))

    @staticmethod
    async def record(*args: Any, **kwargs: Any) -> None:
        return None
