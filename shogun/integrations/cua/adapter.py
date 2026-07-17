"""Governed adapter over ALE's exact desktop and VM MCP primitives."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from shogun.integrations.cua.tool_mapping import ALE_TOOL_MAP, normalize_arguments
from shogun.integrations.mcp import MCPBridgeClient, MCPToolResult
from shogun.services.event_logger import EventLogger
from shogun.services.tool_gate import GateAction, check_tool_access

EventSink = Callable[[dict[str, Any]], Awaitable[None]]
_BLOCKED_REMOTE_PATHS = ("/.ssh", "\\.ssh", "/.aws", "\\.aws", "/.config", "\\.config")


class CUAMCPAdapter:
    """Expose only discovered ALE tools and keep every call inside the sandbox."""

    def __init__(
        self,
        *,
        desktop: MCPBridgeClient | None,
        vm: MCPBridgeClient | None,
        run_id: str,
        posture: str,
        event_sink: EventSink | None = None,
    ):
        if posture not in {"campaign", "ronin"}:
            raise ValueError("Benchmark CUA requires Campaign or Ronin posture")
        self.clients = {"desktop": desktop, "vm": vm}
        self.run_id = run_id
        self.posture = posture
        self.event_sink = event_sink
        self.available: dict[str, set[str]] = {"desktop": set(), "vm": set()}

    async def connect(self) -> dict[str, list[str]]:
        for namespace, client in self.clients.items():
            if client:
                await client.connect()
                self.available[namespace] = {tool.name for tool in await client.list_tools()}
        if "screenshot" not in self.available["desktop"]:
            raise RuntimeError("ALE CUA bridge is missing required screenshot tool")
        if not ({"run_command", "write_text"} & self.available["vm"]):
            raise RuntimeError("ALE VM bridge requires run_command or write_text")
        return {key: sorted(value) for key, value in self.available.items()}

    async def call(self, shogun_tool: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        if shogun_tool not in ALE_TOOL_MAP:
            raise ValueError(f"Unsupported CUA mapping: {shogun_tool}")
        namespace, remote_tool = ALE_TOOL_MAP[shogun_tool]
        client = self.clients.get(namespace)
        if not client or remote_tool not in self.available[namespace]:
            raise RuntimeError(f"ALE bridge does not expose {namespace}.{remote_tool}")
        safe_args = normalize_arguments(shogun_tool, arguments or {})
        self._validate_boundary(safe_args)
        mode = "ronin_desktop" if self.posture == "ronin" else "standard"
        decision = await check_tool_access(mode, "mcp_call_tool", {"tool_name": remote_tool, **safe_args})
        if decision.action == GateAction.BLOCK:
            raise PermissionError(decision.reason)
        started = time.monotonic()
        event = {
            "timestamp": time.time(),
            "type": "tool_call",
            "tool": f"cua.{remote_tool}" if namespace == "desktop" else f"vm.{remote_tool}",
            "shogun_tool": shogun_tool,
            "input": safe_args,
            "status": "started",
        }
        if self.event_sink:
            await self.event_sink(event)
        try:
            result = await client.call_tool(remote_tool, safe_args)
            event.update(
                status="failed" if result.is_error else "success",
                observation={"content": result.content, "structured_content": result.structured_content},
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            await EventLogger.emit_tool_event(
                "benchmark.cua.tool_call",
                f"Benchmark called {namespace}.{remote_tool}",
                session_id=self.run_id,
                trace_id=self.run_id,
                tool_name=shogun_tool,
                result="failure" if result.is_error else "success",
                detail=event,
            )
            if self.event_sink:
                await self.event_sink(event)
            return result
        except Exception as exc:
            event.update(status="failed", error=str(exc), duration_ms=int((time.monotonic() - started) * 1000))
            if self.event_sink:
                await self.event_sink(event)
            raise

    async def close(self) -> None:
        for client in self.clients.values():
            if client:
                await client.close()

    @staticmethod
    def _validate_boundary(arguments: dict[str, Any]) -> None:
        for key, value in arguments.items():
            if key not in {"path", "save_path", "cwd", "command"} or not isinstance(value, str):
                continue
            lowered = value.replace("\\", "/").lower()
            if any(item.replace("\\", "/") in lowered for item in _BLOCKED_REMOTE_PATHS):
                raise PermissionError("Benchmark task attempted to access a protected credential path")
            if key == "path" and lowered.endswith("/.env"):
                raise PermissionError("Benchmark task attempted to access a protected environment file")
