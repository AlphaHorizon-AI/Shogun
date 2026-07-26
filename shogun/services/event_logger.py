"""Event Logger — NIS2/SOC2 + EU AI Act compliant central event emitter.

Every significant action in Shogun flows through this service.
Events are dual-written:
  Layer 1: SQLite operational log (fast, searchable, 90-day retention)
  Layer 2: Immutable audit chain (HMAC-chained, append-only, 7-year retention)

Usage:
    from shogun.services.event_logger import EventLogger

    # Simple emit
    await EventLogger.emit(
        category="memory",
        event_type="memory.write",
        action="Stored operator name in Archives",
        agent_id=str(agent.id),
        user_id="operator",
        detail={"title": "Operator name", "memory_type": "persona"},
    )

    # With trace correlation
    async with EventLogger.trace() as trace_id:
        await EventLogger.emit(..., trace_id=trace_id)
        await EventLogger.emit(..., trace_id=trace_id)  # linked
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from shogun.services import immutable_audit

logger = logging.getLogger(__name__)


class EventLogger:
    """NIS2/SOC2-compliant event-centric logger.

    Two-layer write:
      Layer 1: Operational log (main SQLite) — fast, searchable, 90-day retention
      Layer 2: Immutable audit log (separate SQLite) — append-only, HMAC-chained
    """

    # ── Trace Context Manager ─────────────────────────────────

    @staticmethod
    @asynccontextmanager
    async def trace(session_id: str | None = None):
        """Generate a trace_id for correlating a chain of events.

        Usage:
            async with EventLogger.trace() as trace_id:
                await EventLogger.emit(..., trace_id=trace_id)
        """
        trace_id = f"trc_{uuid.uuid4().hex[:16]}"
        yield trace_id

    # ── Core Emit ─────────────────────────────────────────────

    @staticmethod
    async def emit(
        category: str,
        event_type: str,
        action: str,
        result: str = "success",
        severity: str = "info",
        *,
        session_id: str | None = None,
        trace_id: str | None = None,
        agent_id: str | None = None,
        user_id: str | None = None,
        mission_id: str | None = None,
        model_used: str | None = None,
        provider_used: str | None = None,
        tool_name: str | None = None,
        data_classification: str = "internal",
        policy_ref: str | None = None,
        policy_decision: str | None = None,
        policy_reason: str | None = None,
        risk_score: str = "low",
        detail: dict[str, Any] | None = None,
        memory_ids: list[str] | None = None,
        ip_address: str | None = None,
        duration_ms: int | None = None,
        # EU AI Act governance fields
        confidence_score: float | None = None,
        governance_flags: dict[str, Any] | None = None,
        use_case_context: dict[str, Any] | None = None,
        db_session=None,
    ) -> str:
        """Emit an event to both operational and immutable audit layers.

        Returns the event_id for reference.
        """
        if ip_address is None:
            from shogun.services.request_context import current_client_ip

            ip_address = current_client_ip()
        event_id = f"evt_{uuid.uuid4().hex[:16]}"

        # ── Layer 1: Operational log (async SQLite via SQLAlchemy) ──
        try:
            from shogun.db.engine import async_session_factory
            from shogun.db.models.execution_event import ExecutionEvent

            async def add_operational_event(session):
                event = ExecutionEvent(
                    event_id=event_id,
                    session_id=uuid.UUID(session_id) if session_id else None,
                    trace_id=trace_id,
                    agent_id=uuid.UUID(agent_id) if agent_id else None,
                    user_id=user_id,
                    mission_id=uuid.UUID(mission_id) if mission_id else None,
                    event_category=category,
                    event_type=event_type,
                    severity=severity,
                    action=action,
                    summary=action[:2000],
                    result=result,
                    model_used=model_used,
                    provider_used=provider_used,
                    tool_name=tool_name,
                    data_classification=data_classification,
                    policy_ref=policy_ref,
                    policy_decision=policy_decision,
                    policy_reason=policy_reason,
                    risk_score=risk_score,
                    detail=detail or {},
                    payload=detail or {},
                    memory_ids=memory_ids or [],
                    ip_address=ip_address,
                    occurred_at=datetime.now(timezone.utc),
                    duration_ms=duration_ms,
                    confidence_score=confidence_score,
                    governance_flags=governance_flags or {},
                    use_case_context=use_case_context or {},
                )
                session.add(event)

            if db_session is not None:
                await add_operational_event(db_session)
            else:
                async with async_session_factory() as session:
                    await add_operational_event(session)
                    await session.commit()
        except Exception as e:
            logger.error("Operational log write failed: %s", e)

        # ── Layer 2: Immutable audit chain (sync SQLite, separate DB) ──
        try:
            immutable_audit.append(
                event_id=event_id,
                event_category=category,
                event_type=event_type,
                action=action,
                result=result,
                severity=severity,
                user_id=user_id,
                agent_id=agent_id,
                session_id=session_id,
                trace_id=trace_id,
                model_used=model_used,
                provider_used=provider_used,
                tool_name=tool_name,
                policy_ref=policy_ref,
                policy_decision=policy_decision,
                policy_reason=policy_reason,
                risk_score=risk_score,
                detail=detail,
                memory_ids=memory_ids,
            )
        except Exception as e:
            logger.error("Immutable audit write failed: %s", e)

        return event_id

    # ── Category-Specific Convenience Methods ─────────────────

    @staticmethod
    async def emit_model_event(
        event_type: str,
        action: str,
        *,
        model_used: str | None = None,
        provider_used: str | None = None,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="model",
            event_type=event_type,
            action=action,
            result=result,
            model_used=model_used,
            provider_used=provider_used,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_memory_event(
        event_type: str,
        action: str,
        *,
        memory_ids: list[str] | None = None,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="memory",
            event_type=event_type,
            action=action,
            result=result,
            memory_ids=memory_ids,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_tool_event(
        event_type: str,
        action: str,
        *,
        tool_name: str | None = None,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="tool",
            event_type=event_type,
            action=action,
            result=result,
            tool_name=tool_name,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_office_event(
        event_type: str,
        action: str,
        *,
        application: str | None = None,
        input_file: str | None = None,
        output_file: str | None = None,
        result: str = "success",
        detail: dict | None = None,
        duration_ms: int | None = None,
        **kwargs,
    ) -> str:
        """Emit an Office App Mode event (Katana).

        Event types: office.excel.open, office.excel.write_range,
        office.word.replace_placeholders, office.outlook.create_draft,
        office.config_changed, etc.
        """
        merged_detail = dict(detail or {})
        if application:
            merged_detail["application"] = application
        if input_file:
            merged_detail["input_file"] = input_file
        if output_file:
            merged_detail["output_file"] = output_file
        return await EventLogger.emit(
            category="office",
            event_type=event_type,
            action=action,
            result=result,
            detail=merged_detail,
            duration_ms=duration_ms,
            **kwargs,
        )

    @staticmethod
    async def emit_policy_event(
        event_type: str,
        action: str,
        *,
        policy_ref: str | None = None,
        policy_decision: str | None = None,
        policy_reason: str | None = None,
        risk_score: str = "low",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="policy",
            event_type=event_type,
            action=action,
            policy_ref=policy_ref,
            policy_decision=policy_decision,
            policy_reason=policy_reason,
            risk_score=risk_score,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_auth_event(
        event_type: str,
        action: str,
        *,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="auth",
            event_type=event_type,
            action=action,
            result=result,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_incident_event(
        event_type: str,
        action: str,
        *,
        severity: str = "warn",
        risk_score: str = "high",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        return await EventLogger.emit(
            category="incident",
            event_type=event_type,
            action=action,
            severity=severity,
            risk_score=risk_score,
            detail=detail,
            **kwargs,
        )

    # ── EU AI Act — Decision Provenance ───────────────────────

    @staticmethod
    async def emit_decision_event(
        event_type: str,
        action: str,
        *,
        confidence_score: float | None = None,
        detail: dict | None = None,
        governance_flags: dict | None = None,
        use_case_context: dict | None = None,
        **kwargs,
    ) -> str:
        """Emit a decision provenance event (EU AI Act Article 14/15).

        Event types: decision.context, decision.influences,
        decision.risk_escalation, decision.recommendation
        """
        return await EventLogger.emit(
            category="decision",
            event_type=event_type,
            action=action,
            confidence_score=confidence_score,
            detail=detail,
            governance_flags=governance_flags,
            use_case_context=use_case_context,
            **kwargs,
        )

    @staticmethod
    async def emit_oversight_event(
        event_type: str,
        action: str,
        *,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        """Emit a human oversight event (EU AI Act Article 14).

        Event types: oversight.review_requested, oversight.approved,
        oversight.rejected, oversight.overridden, oversight.escalated
        """
        return await EventLogger.emit(
            category="oversight",
            event_type=event_type,
            action=action,
            result=result,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_risk_event(
        event_type: str,
        action: str,
        *,
        severity: str = "warn",
        risk_score: str = "high",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        """Emit a risk escalation event (EU AI Act risk-based approach).

        Event types: risk.sensitive_data_detected, risk.high_impact_use_case,
        risk.confidence_below_threshold, risk.external_model_blocked,
        risk.bias_warning
        """
        return await EventLogger.emit(
            category="risk",
            event_type=event_type,
            action=action,
            severity=severity,
            risk_score=risk_score,
            detail=detail,
            **kwargs,
        )

    @staticmethod
    async def emit_governance_event(
        event_type: str,
        action: str,
        *,
        detail: dict | None = None,
        governance_flags: dict | None = None,
        **kwargs,
    ) -> str:
        """Emit a governance lifecycle event.

        Event types: governance.mode_changed, governance.framework_applied,
        governance.audit_exported
        """
        return await EventLogger.emit(
            category="governance",
            event_type=event_type,
            action=action,
            detail=detail,
            governance_flags=governance_flags,
            **kwargs,
        )

    # ── System Lifecycle ──────────────────────────────────────

    @staticmethod
    async def emit_system_event(
        event_type: str,
        action: str,
        *,
        result: str = "success",
        detail: dict | None = None,
        **kwargs,
    ) -> str:
        """Emit a system lifecycle event.

        Event types: system.startup, system.shutdown, system.config_changed,
        system.backup_created, system.backup_restored, system.update_installed,
        system.migration_applied
        """
        return await EventLogger.emit(
            category="system",
            event_type=event_type,
            action=action,
            result=result,
            detail=detail,
            **kwargs,
        )
