"""Explicit mock responses for the Lab preview; real execution is unavailable.

This component never invokes tools and does not implement a ToolGate adapter.
Fixture, replay, sandbox, tenant and live execution require future integration.
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Supported execution modes (§14.4)
SUPPORTED_EXECUTION_MODES = frozenset(
    {
        "mock",
        "denied",
    }
)

UNSUPPORTED_EXECUTION_MODES = frozenset(
    {
        "fixture",
        "replay",
        "sandbox",
        "test_tenant",
        "approved_live_read",
        "approved_live_write",
    }
)

EXECUTION_MODES = SUPPORTED_EXECUTION_MODES | UNSUPPORTED_EXECUTION_MODES


class SafeExecutor:
    """Returns labeled mock results or denies calls without invoking tools."""

    def __init__(
        self,
        execution_mode: str = "mock",
        max_tool_calls: int = 100,
        max_cost_eur: float = 5.0,
    ):
        if execution_mode in UNSUPPORTED_EXECUTION_MODES:
            raise ValueError(
                f"Execution mode {execution_mode!r} is unsupported in this environment. "
                "Only explicit mock and denied modes are implemented."
            )
        if execution_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(
                f"Unknown execution mode: {execution_mode!r}. Must be one of: {sorted(SUPPORTED_EXECUTION_MODES)}"
            )
        self.execution_mode = execution_mode
        self.max_tool_calls = max_tool_calls
        self.max_cost_eur = max_cost_eur
        self.tool_call_count = 0
        self.total_cost_eur = 0.0
        self.evidence: list[dict[str, Any]] = []

    def execute_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        *,
        policy_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a single tool call within the safe boundary.

        Returns an execution result dict with output, status, and metadata.
        """
        if self.execution_mode in UNSUPPORTED_EXECUTION_MODES or self.execution_mode not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(
                f"Execution mode {self.execution_mode!r} is unsupported. "
                "Only explicit mock and denied modes are implemented."
            )

        # Budget check
        if self.tool_call_count >= self.max_tool_calls:
            return {
                "status": "denied",
                "reason": "BUDGET_EXCEEDED",
                "tool_name": tool_name,
            }

        self.tool_call_count += 1
        start_time = time.monotonic()

        # Execution mode determines how the tool call is handled
        if self.execution_mode == "denied":
            result = self._denied(tool_name, tool_args)
        elif self.execution_mode == "mock":
            result = self._mock_execute(tool_name, tool_args)
        else:
            raise ValueError(f"Execution mode {self.execution_mode!r} is unsupported.")

        elapsed = time.monotonic() - start_time

        # Capture evidence
        evidence_entry = {
            "tool_name": tool_name,
            "tool_args_redacted": {
                k: "***" if "secret" in k.lower() or "key" in k.lower() else v for k, v in tool_args.items()
            },
            "execution_mode": self.execution_mode,
            "status": result.get("status", "unknown"),
            "latency_seconds": round(elapsed, 3),
            "call_number": self.tool_call_count,
        }
        self.evidence.append(evidence_entry)

        return result

    def get_execution_summary(self) -> dict[str, Any]:
        """Return a summary of all tool calls executed."""
        return {
            "total_tool_calls": self.tool_call_count,
            "total_cost_eur": self.total_cost_eur,
            "execution_mode": self.execution_mode,
            "evidence_count": len(self.evidence),
        }

    # ── Mode-specific executors ──────────────────────────────

    def _denied(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """DENIED mode — tool call is blocked by policy."""
        return {
            "status": "denied",
            "reason": "EXECUTION_MODE_DENIED",
            "tool_name": tool_name,
            "output": None,
        }

    def _mock_execute(self, tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
        """MOCK mode — returns a synthetic successful response."""
        return {
            "status": "completed",
            "tool_name": tool_name,
            "output": {"mock": True, "tool": tool_name},
            "execution_mode": "mock",
        }
