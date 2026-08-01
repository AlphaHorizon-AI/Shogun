"""ToolGate Confirmation Registry — in-memory human-in-the-loop gate.

When ToolGate returns a CONFIRM decision, the SSE stream pauses
and waits for the operator to approve or deny the tool call.

This module manages the pending confirmation state using asyncio.Event
objects. Since Shogun is single-process, in-memory state is sufficient.

Flow:
    1. SSE handler calls request_confirmation(confirm_id) → blocks
    2. Frontend shows a confirmation card with Approve/Deny buttons
    3. User clicks → POST /api/v1/security/toolgate/confirm
    4. API handler calls resolve_confirmation(confirm_id, approved)
    5. asyncio.Event is set → request_confirmation() returns the result
    6. SSE handler proceeds (execute or block the tool)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("shogun.toolgate_confirm")

# Default timeout in seconds before auto-denying
CONFIRMATION_TIMEOUT_SECONDS = 60


@dataclass
class PendingConfirmation:
    """Represents a tool call waiting for human approval."""

    confirm_id: str
    tool_name: str
    args: dict[str, Any]
    risk_level: str
    reason: str
    event: asyncio.Event = field(default_factory=asyncio.Event)
    approved: bool = False
    created_at: float = field(default_factory=time.time)


# ── In-Memory Registry ──────────────────────────────────────────────

_pending: dict[str, PendingConfirmation] = {}


async def request_confirmation(
    confirm_id: str,
    tool_name: str,
    args: dict[str, Any],
    risk_level: str,
    reason: str,
    timeout: float = CONFIRMATION_TIMEOUT_SECONDS,
) -> bool:
    """Block until the operator approves/denies, or timeout expires.

    Returns True if approved, False if denied or timed out.
    """
    register_confirmation(
        confirm_id=confirm_id,
        tool_name=tool_name,
        args=args,
        risk_level=risk_level,
        reason=reason,
    )
    return await wait_for_confirmation(confirm_id, timeout=timeout)


def register_confirmation(
    confirm_id: str,
    tool_name: str,
    args: dict[str, Any],
    risk_level: str,
    reason: str,
) -> None:
    """Register a confirmation synchronously before its SSE event is emitted."""
    _pending[confirm_id] = PendingConfirmation(
        confirm_id=confirm_id,
        tool_name=tool_name,
        args=args,
        risk_level=risk_level,
        reason=reason,
    )
    log.info(
        "Confirmation requested: %s for tool '%s' (risk=%s)",
        confirm_id, tool_name, risk_level,
    )


async def wait_for_confirmation(
    confirm_id: str,
    timeout: float = CONFIRMATION_TIMEOUT_SECONDS,
) -> bool:
    """Wait for a previously registered confirmation to resolve."""
    entry = _pending.get(confirm_id)
    if not entry:
        log.warning("Confirmation %s was not registered before waiting", confirm_id)
        return False

    try:
        await asyncio.wait_for(entry.event.wait(), timeout=timeout)
        log.info(
            "Confirmation %s resolved: %s",
            confirm_id, "approved" if entry.approved else "denied",
        )
        return entry.approved
    except asyncio.TimeoutError:
        log.warning(
            "Confirmation %s timed out after %.0fs — auto-denied",
            confirm_id, timeout,
        )
        return False
    finally:
        _pending.pop(confirm_id, None)


def resolve_confirmation(confirm_id: str, approved: bool) -> bool:
    """Resolve a pending confirmation. Returns True if found, False if not.

    Called by the REST endpoint when the operator clicks Approve/Deny.
    """
    entry = _pending.get(confirm_id)
    if not entry:
        log.warning("Confirmation %s not found (expired or already resolved)", confirm_id)
        return False

    entry.approved = approved
    entry.event.set()
    return True


def get_pending_count() -> int:
    """Return the number of pending confirmations (for dashboard/status)."""
    return len(_pending)


def list_pending_confirmations() -> list[dict[str, Any]]:
    """Return serializable pending confirmations for the ToolGate control page."""
    return [
        {
            "confirm_id": entry.confirm_id,
            "tool_name": entry.tool_name,
            "args": entry.args,
            "risk_level": entry.risk_level,
            "reason": entry.reason,
            "created_at": entry.created_at,
        }
        for entry in sorted(_pending.values(), key=lambda item: item.created_at)
        if not entry.event.is_set()
    ]


def cleanup_expired(max_age: float = CONFIRMATION_TIMEOUT_SECONDS * 2) -> int:
    """Remove stale entries that somehow weren't cleaned up. Returns count removed."""
    now = time.time()
    expired = [k for k, v in _pending.items() if now - v.created_at > max_age]
    for k in expired:
        entry = _pending.pop(k, None)
        if entry and not entry.event.is_set():
            entry.approved = False
            entry.event.set()
    return len(expired)
