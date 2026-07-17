"""Persistent stdio MCP client with discovery, timeouts, and reconnects."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from shogun.integrations.mcp.types import MCPConnectionConfig, MCPToolResult, MCPToolSpec


class MCPBridgeClient:
    """Connect to a benchmark-provided MCP server without using Katana state."""

    def __init__(self, config: MCPConnectionConfig):
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._process and self._process.returncode is None:
            return
        if self.config.transport != "stdio":
            raise ValueError(f"Unsupported benchmark MCP transport: {self.config.transport}")
        if not self.config.command:
            raise ValueError("MCP stdio command is required")
        command = (
            sys.executable if self.config.command in {"python", "python.exe", "shogun-python"} else self.config.command
        )
        env = os.environ.copy()
        env.update(self.config.env)
        self._process = await asyncio.create_subprocess_exec(
            command,
            *self.config.args,
            cwd=self.config.cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "shogun-benchmark", "version": "1.0"},
            },
        )
        await self._notify("notifications/initialized")

    async def list_tools(self) -> list[MCPToolSpec]:
        response = await self._request_with_reconnect("tools/list")
        return [
            MCPToolSpec(
                name=str(item.get("name", "")),
                description=str(item.get("description", "")),
                input_schema=dict(item.get("inputSchema") or {}),
            )
            for item in response.get("tools", [])
            if item.get("name")
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        response = await self._request_with_reconnect(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return MCPToolResult(
            tool=name,
            content=list(response.get("content") or []),
            structured_content=response.get("structuredContent"),
            is_error=bool(response.get("isError", False)),
            raw=response,
        )

    async def close(self) -> None:
        process = self._process
        self._process = None
        if not process or process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=2)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def _request_with_reconnect(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(2):
            try:
                await self.connect()
                return await self._request(method, params)
            except (BrokenPipeError, ConnectionError, TimeoutError):
                await self.close()
                if attempt:
                    raise
        raise RuntimeError("MCP reconnect failed")

    async def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._lock:
            request_id = self._next_id
            self._next_id += 1
            await self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
            while True:
                message = await self._receive()
                if message.get("id") != request_id:
                    continue
                if message.get("error"):
                    error = message["error"]
                    raise RuntimeError(str(error.get("message") or error))
                return dict(message.get("result") or {})

    async def _notify(self, method: str) -> None:
        await self._send({"jsonrpc": "2.0", "method": method, "params": {}})

    async def _send(self, value: dict[str, Any]) -> None:
        process = self._require_process()
        assert process.stdin is not None
        process.stdin.write((json.dumps(value, separators=(",", ":")) + "\n").encode())
        await process.stdin.drain()

    async def _receive(self) -> dict[str, Any]:
        process = self._require_process()
        assert process.stdout is not None
        raw = await asyncio.wait_for(process.stdout.readline(), timeout=self.config.timeout_seconds)
        if not raw:
            detail = ""
            if process.stderr:
                try:
                    detail = (await asyncio.wait_for(process.stderr.read(2000), timeout=0.2)).decode(errors="replace")
                except Exception:
                    pass
            raise ConnectionError(f"MCP server exited before responding. {detail}".strip())
        return json.loads(raw.decode())

    def _require_process(self) -> asyncio.subprocess.Process:
        if not self._process:
            raise ConnectionError("MCP server is not connected")
        return self._process

    async def __aenter__(self) -> MCPBridgeClient:
        await self.connect()
        return self

    async def __aexit__(self, *_args: Any) -> None:
        await self.close()
