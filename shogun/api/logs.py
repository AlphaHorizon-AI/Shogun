"""Log and audit routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from shogun.api.deps import get_audit_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.logs import ExecutionEventResponse
from shogun.services.audit_service import AuditService

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("", response_model=ApiResponse)
async def list_logs(
    severity: str | None = None,
    event_type: str | None = None,
    svc: AuditService = Depends(get_audit_service),
):
    filters = []
    if severity:
        from shogun.db.models.execution_event import ExecutionEvent
        filters.append(ExecutionEvent.severity == severity)
    if event_type:
        from shogun.db.models.execution_event import ExecutionEvent
        filters.append(ExecutionEvent.event_type == event_type)

    records, total = await svc.get_all(filters=filters, limit=100)
    return ApiResponse(
        data=[ExecutionEventResponse.model_validate(r) for r in records],
        meta={"total": total},
    )
