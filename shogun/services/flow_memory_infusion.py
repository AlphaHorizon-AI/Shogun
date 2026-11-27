"""Minimal no-op flow output memory infusion shim (Archives/Qdrant omitted)."""

from __future__ import annotations

from typing import Any


async def infuse_flow_output_memory(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"stored": False, "reason": "Memory archives disabled in AgentFlow edition"}
