"""Minimal AgentService shim — AgentFlow uses inline Ad-Hoc Agents."""

from __future__ import annotations

from typing import Any


class AgentService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def list_all(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    async def get_by_id(self, *args: Any, **kwargs: Any) -> Any:
        return None
