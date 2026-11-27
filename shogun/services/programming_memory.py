"""Minimal ProgrammingMemoryService shim for IDE coding nodes."""

from __future__ import annotations

from typing import Any


class ProgrammingMemoryService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def remember(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"id": "local", "stored": False}
