"""Transport-neutral MCP bridge data shapes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class MCPConnectionConfig:
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    timeout_seconds: float = 45.0

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> MCPConnectionConfig:
        return cls(
            transport=str(value.get("transport", "stdio")),
            command=str(value.get("command", "")),
            args=[str(item) for item in value.get("args", [])],
            env={str(key): str(item) for key, item in value.get("env", {}).items()},
            cwd=str(value["cwd"]) if value.get("cwd") else None,
            timeout_seconds=float(value.get("timeout_seconds", 45.0)),
        )


@dataclass(slots=True)
class MCPToolSpec:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MCPToolResult:
    tool: str
    content: list[dict[str, Any]] = field(default_factory=list)
    structured_content: dict[str, Any] | None = None
    is_error: bool = False
    raw: dict[str, Any] = field(default_factory=dict)
