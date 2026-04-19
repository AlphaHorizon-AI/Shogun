"""Log and audit routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func

from shogun.api.deps import get_audit_service, get_db
from shogun.schemas.common import ApiResponse
from shogun.schemas.logs import ExecutionEventResponse
from shogun.services.audit_service import AuditService

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=ApiResponse)
async def list_logs(
    severity: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
    svc: AuditService = Depends(get_audit_service),
):
    from shogun.db.models.execution_event import ExecutionEvent
    from sqlalchemy import select, desc

    query = select(ExecutionEvent)

    if severity:
        # DB stores lowercase; accept any case from the client
        query = query.where(
            func.lower(ExecutionEvent.severity) == severity.lower()
        )
    if event_type:
        query = query.where(ExecutionEvent.event_type == event_type)

    # Newest first
    query = query.order_by(desc(ExecutionEvent.occurred_at)).limit(limit)
    result = await svc.session.execute(query)
    records = result.scalars().all()

    return ApiResponse(
        data=[ExecutionEventResponse.model_validate(r) for r in records],
        meta={"total": len(records)},
    )


@router.delete("", response_model=ApiResponse)
async def clear_logs(svc: AuditService = Depends(get_audit_service)):
    """Hard-delete all execution events (for the Download/Clear action)."""
    from shogun.db.models.execution_event import ExecutionEvent
    from sqlalchemy import delete
    await svc.session.execute(delete(ExecutionEvent))
    await svc.session.commit()
    return ApiResponse(data={"cleared": True})
