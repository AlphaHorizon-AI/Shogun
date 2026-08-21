"""Operational-log and HMAC-chain routes for governance evidence.

Provides:
  - Category-filtered event listing
  - Trace correlation reconstruction
  - Audit chain integrity verification
  - Evidence export for audit and compliance assessment
  - Operational log management (clear)
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select, desc, and_

from shogun.api.deps import get_audit_service, get_db
from shogun.schemas.common import ApiResponse
from shogun.schemas.logs import ExecutionEventResponse, AuditVerificationResponse
from shogun.services.audit_service import AuditService

router = APIRouter(prefix="/logs", tags=["Logs"])


# ── List Events (filterable) ─────────────────────────────────

@router.get("", response_model=ApiResponse)
async def list_logs(
    event_id: str | None = Query(None, description="Exact event ID"),
    severity: str | None = None,
    event_type: str | None = None,
    category: str | None = Query(None, description="Comma-separated: auth,memory,tool,model,policy,incident"),
    trace_id: str | None = Query(None, description="Trace ID for workflow reconstruction"),
    agent_id: str | None = None,
    date_from: str | None = Query(None, description="ISO datetime"),
    date_to: str | None = Query(None, description="ISO datetime"),
    limit: int = 200,
    svc: AuditService = Depends(get_audit_service),
):
    """List operational events using governance-oriented filters."""
    from shogun.db.models.execution_event import ExecutionEvent

    query = select(ExecutionEvent)
    filters = []

    if event_id:
        filters.append(ExecutionEvent.event_id == event_id)
    if severity:
        filters.append(func.lower(ExecutionEvent.severity) == severity.lower())
    if event_type:
        filters.append(ExecutionEvent.event_type == event_type)
    if category:
        cats = [c.strip() for c in category.split(",")]
        if len(cats) == 1:
            filters.append(ExecutionEvent.event_category == cats[0])
        else:
            filters.append(ExecutionEvent.event_category.in_(cats))
    if trace_id:
        filters.append(ExecutionEvent.trace_id == trace_id)
    if agent_id:
        from shogun.db.base import GUID
        import uuid
        filters.append(ExecutionEvent.agent_id == uuid.UUID(agent_id))
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            filters.append(ExecutionEvent.occurred_at >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to)
            filters.append(ExecutionEvent.occurred_at <= dt)
        except ValueError:
            pass

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(desc(ExecutionEvent.occurred_at)).limit(limit)
    result = await svc.session.execute(query)
    records = result.scalars().all()

    return ApiResponse(
        data=[ExecutionEventResponse.model_validate(r) for r in records],
        meta={"total": len(records)},
    )


# ── Event Categories Summary ─────────────────────────────────

@router.get("/categories", response_model=ApiResponse)
async def event_categories(
    svc: AuditService = Depends(get_audit_service),
):
    """Get event count by category for the dashboard."""
    from shogun.db.models.execution_event import ExecutionEvent

    result = await svc.session.execute(
        select(
            ExecutionEvent.event_category,
            func.count(ExecutionEvent.id).label("count"),
        ).group_by(ExecutionEvent.event_category)
    )
    categories = {row[0]: row[1] for row in result.all()}
    total = sum(categories.values())

    return ApiResponse(
        data={"categories": categories, "total": total},
    )


# ── Trace Reconstruction ─────────────────────────────────────

@router.get("/trace/{trace_id}", response_model=ApiResponse)
async def reconstruct_trace(
    trace_id: str,
    svc: AuditService = Depends(get_audit_service),
):
    """Reconstruct a full event chain by trace_id.

    Returns all events linked to a workflow in chronological order.
    This is the core NIS2 incident reconstruction capability.
    """
    from shogun.db.models.execution_event import ExecutionEvent

    result = await svc.session.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.trace_id == trace_id)
        .order_by(ExecutionEvent.occurred_at.asc())
    )
    records = result.scalars().all()

    return ApiResponse(
        data=[ExecutionEventResponse.model_validate(r) for r in records],
        meta={
            "trace_id": trace_id,
            "event_count": len(records),
            "chain_complete": len(records) > 0,
        },
    )


# ── Audit Chain Verification ─────────────────────────────────

@router.get("/audit/verify", response_model=ApiResponse)
async def verify_audit_chain():
    """Check the append-only audit log's HMAC-chain consistency.

    Walks the available HMAC chain and reports covered-field mismatches. This
    does not prove record completeness or establish compliance.
    """
    from shogun.services import immutable_audit

    result = immutable_audit.verify_chain()

    # If chain is broken, emit an incident
    if not result.get("chain_intact", True):
        try:
            from shogun.services.event_logger import EventLogger
            import asyncio
            asyncio.ensure_future(EventLogger.emit_incident_event(
                "incident.chain_broken",
                "AUDIT CHAIN CONSISTENCY VIOLATION: mismatch detected",
                severity="critical", risk_score="critical",
                detail=result,
            ))
        except Exception:
            pass

    return ApiResponse(data=result)


# ── Audit Export ──────────────────────────────────────────────

@router.get("/audit/export")
async def export_audit_log(
    category: str | None = None,
    trace_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    format: str = Query("json", description="json or csv"),
    limit: int = 10000,
):
    """Export HMAC-chained audit records for assessment or investigation.

    Downloads from the separate append-only audit log, not the operational log.
    Includes HMAC hashes for verification. The export does not prove record
    completeness or establish compliance.
    """
    from shogun.services import immutable_audit

    records = immutable_audit.export_records(
        category=category,
        trace_id=trace_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    if format == "csv":
        import csv
        import io
        output = io.StringIO()
        if records:
            writer = csv.DictWriter(output, fieldnames=records[0].keys())
            writer.writeheader()
            writer.writerows(records)
        content = output.getvalue()
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=shogun_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    else:
        content = json.dumps(records, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=shogun_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )


# ── Clear Operational Logs ────────────────────────────────────

@router.delete("", response_model=ApiResponse)
async def clear_logs(svc: AuditService = Depends(get_audit_service)):
    """Clear operational logs only; this route leaves the audit-chain DB intact.

    Operators with host or database access remain responsible for protecting,
    retaining, backing up, and independently verifying the separate evidence.
    """
    from shogun.db.models.execution_event import ExecutionEvent
    from sqlalchemy import delete

    result = await svc.session.execute(
        select(func.count()).select_from(ExecutionEvent)
    )
    count = result.scalar() or 0

    await svc.session.execute(delete(ExecutionEvent))
    await svc.session.commit()

    # Record the clearing action in the separate append-only audit log.
    from shogun.services import immutable_audit
    immutable_audit.append(
        event_id=f"evt_clear_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        event_category="system",
        event_type="logs.cleared",
        action=f"Operational logs cleared ({count} records)",
        severity="warn",
        risk_score="medium",
    )

    # Also emit a system event (will be recorded in the NEXT operational log)
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_system_event(
            "system.logs_cleared", f"Operational logs cleared ({count} records)",
            detail={"records_removed": count},
        )
    except Exception:
        pass

    return ApiResponse(data={"cleared": True, "records_removed": count})
