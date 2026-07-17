"""Generic Model Context Protocol clients used by governed integrations."""

from .client import MCPBridgeClient
from .types import MCPConnectionConfig, MCPToolResult, MCPToolSpec

__all__ = ["MCPBridgeClient", "MCPConnectionConfig", "MCPToolResult", "MCPToolSpec"]
