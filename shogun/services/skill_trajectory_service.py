"""Minimal no-op SkillTrajectoryService shim for bare-bones AgentFlow."""

from __future__ import annotations

from typing import Any


class SkillTrajectoryService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def link_output(self, *args: Any, **kwargs: Any) -> None:
        return None
