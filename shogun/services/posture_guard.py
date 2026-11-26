"""Local desktop posture guard shim — permits all AgentFlow node operations."""

from __future__ import annotations

from typing import Any


async def get_posture_permissions(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {
        "active_tier": "ronin",
        "posture": "ronin",
        "kill_switch_active": False,
        "ide_enabled": True,
        "mado_enabled": True,
        "office_enabled": True,
        "allowed_tools": [],
        "allow_shell": True,
        "allow_filesystem": True,
        "allow_network": True,
        "allow_browser": True,
    }


async def get_posture_tool_filter(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return await get_posture_permissions()


def filter_tools_by_posture(
    tools: list[dict[str, Any]],
    posture: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return list(tools), []


async def check_mado_access(*args: Any, **kwargs: Any) -> bool:
    return True


def check_mado_browser_mode(browser_mode: str = "headless", posture: dict[str, Any] | None = None) -> bool:
    return True


async def check_mado_session_limit(*args: Any, **kwargs: Any) -> bool:
    return True
