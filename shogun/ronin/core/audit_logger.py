"""Ronin Audit Logger — wraps EventLogger for Ronin-specific events.

Every Ronin action is logged to both Layer 1 (operational SQLite) and
Layer 2 (immutable HMAC-chained audit chain) via the central EventLogger.
Ronin events include before/after screenshots, app trust level, environment
type, capability metadata, and approval status.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("shogun.ronin.audit")


class RoninAuditLogger:
    """Ronin-specific audit event emitter."""

    @staticmethod
    async def log_action(
        *,
        event_type: str,
        action: str,
        agent_id: str | None = None,
        session_id: str | None = None,
        action_type: str | None = None,
        target: str | None = None,
        result: str = "success",
        severity: str = "info",
        risk_level: str = "low",
        app_trust: str | None = None,
        environment_type: str | None = None,
        screenshot_before: str | None = None,
        screenshot_after: str | None = None,
        approval_status: str | None = None,
        confidence: float | None = None,
        verified: bool = False,
        duration_ms: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        """Emit a Ronin audit event to both log layers.

        Returns the event_id for reference.
        """
        try:
            from shogun.services.event_logger import EventLogger

            merged_detail = {
                "ronin_action_type": action_type,
                "ronin_target": target,
                "ronin_app_trust": app_trust,
                "ronin_environment": environment_type,
                "ronin_screenshot_before": screenshot_before,
                "ronin_screenshot_after": screenshot_after,
                "ronin_approval_status": approval_status,
                "ronin_confidence": confidence,
                "ronin_verified": verified,
                **(detail or {}),
            }

            event_id = await EventLogger.emit(
                category="ronin",
                event_type=event_type,
                action=action,
                result=result,
                severity=severity,
                risk_score=risk_level,
                agent_id=agent_id,
                session_id=session_id,
                duration_ms=duration_ms,
                detail=merged_detail,
            )
            return event_id
        except Exception as exc:
            log.error("Ronin audit log failed: %s", exc)
            return ""

    # ── Convenience Methods ──────────────────────────────────────

    @staticmethod
    async def log_session_start(
        session_id: str,
        agent_id: str | None = None,
        environment_type: str | None = None,
        posture: str | None = None,
    ) -> str:
        return await RoninAuditLogger.log_action(
            event_type="ronin.desktop.session_started",
            action=f"Ronin desktop session started (posture={posture})",
            agent_id=agent_id,
            session_id=session_id,
            environment_type=environment_type,
            detail={"posture": posture},
        )

    @staticmethod
    async def log_session_close(
        session_id: str,
        agent_id: str | None = None,
        reason: str = "normal",
    ) -> str:
        return await RoninAuditLogger.log_action(
            event_type="ronin.desktop.session_stopped",
            action=f"Ronin desktop session closed ({reason})",
            agent_id=agent_id,
            session_id=session_id,
            detail={"close_reason": reason},
        )

    @staticmethod
    async def log_action_blocked(
        action_type: str,
        reason: str,
        agent_id: str | None = None,
        session_id: str | None = None,
        app_trust: str | None = None,
        risk_level: str = "medium",
    ) -> str:
        return await RoninAuditLogger.log_action(
            event_type="ronin.desktop.action_blocked",
            action=f"Ronin action blocked: {action_type} — {reason}",
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            result="blocked",
            severity="warn",
            risk_level=risk_level,
            app_trust=app_trust,
        )

    @staticmethod
    async def log_approval_requested(
        action_type: str,
        reason: str,
        approval_id: str,
        agent_id: str | None = None,
        session_id: str | None = None,
        risk_level: str = "high",
    ) -> str:
        return await RoninAuditLogger.log_action(
            event_type="ronin.desktop.approval_requested",
            action=f"Ronin approval requested: {action_type}",
            agent_id=agent_id,
            session_id=session_id,
            action_type=action_type,
            severity="warn",
            risk_level=risk_level,
            approval_status="pending",
            detail={"approval_id": approval_id, "reason": reason},
        )

    @staticmethod
    async def log_approval_response(
        approval_id: str,
        decision: str,  # "approved" | "denied"
        agent_id: str | None = None,
    ) -> str:
        return await RoninAuditLogger.log_action(
            event_type="ronin.desktop.approval_granted" if decision == "approved" else "ronin.desktop.approval_rejected",
            action=f"Ronin approval {decision}: {approval_id}",
            agent_id=agent_id,
            severity="warn" if decision == "denied" else "info",
            approval_status=decision,
            detail={"approval_id": approval_id},
        )

    @staticmethod
    async def log_komainu_event(
        level: int,
        reason: str,
        session_id: str | None = None,
    ) -> str:
        """Log a Komainu (guardian) intervention event."""
        level_names = {1: "pause", 2: "terminate", 3: "harakiri"}
        level_name = level_names.get(level, "unknown")
        severity = "warn" if level <= 2 else "critical"
        risk = "medium" if level == 1 else "high" if level == 2 else "critical"

        return await RoninAuditLogger.log_action(
            event_type=f"incident.komainu_{level_name}",
            action=f"Komainu Level {level}: {reason}",
            session_id=session_id,
            result="komainu_triggered",
            severity=severity,
            risk_level=risk,
            detail={"komainu_level": level, "trigger": reason},
        )

    @staticmethod
    async def log_harakiri(reason: str = "manual") -> str:
        """Log a Ronin-initiated Harakiri event."""
        return await RoninAuditLogger.log_action(
            event_type="incident.ronin_harakiri",
            action=f"Ronin Harakiri: {reason}",
            result="harakiri",
            severity="critical",
            risk_level="critical",
            detail={"trigger": reason},
        )
