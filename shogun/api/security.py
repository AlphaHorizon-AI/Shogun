"""Minimal desktop posture store for Office and AgentFlow node execution."""

from __future__ import annotations

from typing import Any

_DESKTOP_POSTURE: dict[str, Any] = {
    "active_tier": "ronin",
    "posture": "ronin",
    "kill_switch_active": False,
    "ide_enabled": True,
    "mado_enabled": True,
    "office_enabled": True,
    "allowed_tools": [],
}


async def _get_agent_posture() -> dict[str, Any]:
    return dict(_DESKTOP_POSTURE)


async def _save_agent_posture(posture: dict[str, Any]) -> dict[str, Any]:
    _DESKTOP_POSTURE.update(posture or {})
    return dict(_DESKTOP_POSTURE)
