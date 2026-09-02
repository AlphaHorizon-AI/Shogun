"""Gensui Policy Guard — enforcement layer inside Shogun.

Checks the locally cached Gensui posture before allowing controlled actions.
Integrates with existing posture_guard.py enforcement points.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

log = logging.getLogger("shogun.gensui_policy_guard")


async def check_gensui_policy(action_type: str, context: dict | None = None) -> None:
    """Check if an action is allowed under the current Gensui posture.

    Call this at enforcement points before executing controlled actions.
    If Gensui is not enabled, this is a no-op.

    Raises HTTPException(403) if the action is blocked.
    """
    from shogun.edition import feature_available

    if not feature_available("gensui"):
        return

    try:
        from shogun.services.gensui_client import gensui_client

        if not gensui_client.enabled:
            return

        if not gensui_client.is_enrolled:
            return

        if gensui_client.is_action_allowed(action_type):
            return

        # Action is blocked by Gensui posture
        posture = gensui_client.get_effective_posture() or {}
        posture_name = posture.get("posture_name", "UNKNOWN")
        reason = posture.get("reason", "Blocked by Gensui security posture")

        log.warning(
            "[GensuiPolicyGuard] Blocked %s — posture: %s, reason: %s",
            action_type, posture_name, reason,
        )

        # Emit telemetry event
        gensui_client.buffer_telemetry({
            "event_type": "security.policy_violation",
            "event_category": "security",
            "severity": "warn",
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
            "payload": {
                "action_type": action_type,
                "posture_name": posture_name,
                "decision": "BLOCK",
                "context": context,
            },
        })

        raise HTTPException(
            status_code=403,
            detail=f"⛩️ Gensui posture [{posture_name}] blocks {action_type}. {reason}",
        )
    except HTTPException:
        raise
    except Exception as e:
        # Never block operations due to Gensui client errors
        log.debug("[GensuiPolicyGuard] Check failed (non-fatal): %s", e)


async def check_gensui_model_call() -> None:
    """Check if model calls are allowed."""
    await check_gensui_policy("MODEL_CALL")


async def check_gensui_tool_execution() -> None:
    """Check if tool execution is allowed."""
    await check_gensui_policy("TOOL_EXECUTION")


async def check_gensui_mado() -> None:
    """Check if Mado browser automation is allowed."""
    await check_gensui_policy("MADO_SESSION")


async def check_gensui_memory_write() -> None:
    """Check if memory writes are allowed."""
    await check_gensui_policy("MEMORY_WRITE")


async def check_gensui_agent_flow() -> None:
    """Check if Agent Flow execution is allowed."""
    await check_gensui_policy("AGENT_FLOW")


async def check_gensui_samurai_delegation() -> None:
    """Check if Samurai delegation is allowed."""
    await check_gensui_policy("SAMURAI_DELEGATION")
