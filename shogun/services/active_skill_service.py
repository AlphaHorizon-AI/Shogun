"""Minimal no-op SkillActivationService shim for bare-bones AgentFlow."""

from __future__ import annotations

from typing import Any


class SkillActivationService:
    def __init__(self, session: Any = None) -> None:
        self.session = session

    async def activate(self, request: Any) -> dict[str, Any]:
        return {
            "active_skill_run_ids": [],
            "skills": [],
            "prompt_injection": "",
        }

    async def outcome(self, *args: Any, **kwargs: Any) -> None:
        return None
