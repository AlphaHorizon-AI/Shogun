"""Local desktop ToolGate shim — allows AgentFlow node tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


@dataclass
class GateDecision:
    action: GateAction = GateAction.ALLOW
    reason: str = "Allowed in local AgentFlow desktop mode"


def get_toolgate_scope(posture: dict[str, Any] | None = None) -> dict[str, Any]:
    tier = (posture or {}).get("active_tier") or "ronin"
    return {"base_tier": tier, "key": f"local:{tier}"}


async def check_tool_access(
    mode: str,
    tool_name: str,
    args: dict[str, Any] | None = None,
    preset: Any = None,
    *,
    local_scope: str | None = None,
) -> GateDecision:
    return GateDecision(action=GateAction.ALLOW)
