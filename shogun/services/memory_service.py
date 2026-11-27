"""Minimal MemoryService shim (Archives/Qdrant omitted in bare-bones edition)."""

from __future__ import annotations

from typing import Any


class MemoryService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def search(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def recall(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def store(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"stored": False}
