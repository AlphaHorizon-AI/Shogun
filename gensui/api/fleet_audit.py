"""Fleet Audit API — fleet-wide audit, analytics, governance evidence, and export."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, require_role
from gensui.services.fleet_audit_service import FleetAuditService

router = APIRouter(prefix="/fleet-audit", tags=["fleet-audit"])


@router.get("/stats")
async def fleet_audit_stats(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin", "auditor")),
):
    """Get fleet-wide audit statistics."""
    svc = FleetAuditService(db)
    return await svc.get_fleet_audit_stats()


@router.get("/members")
async def member_audit_summary(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin", "auditor")),
):
    """Get per-member audit event breakdown."""
    svc = FleetAuditService(db)
    return {"members": await svc.get_member_audit_summary()}


@router.get("/telemetry")
async def telemetry_analytics(
    shogun_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin", "auditor")),
):
    """Get telemetry analytics (optionally filtered by member)."""
    svc = FleetAuditService(db)
    sid = uuid.UUID(shogun_id) if shogun_id else None
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    return await svc.get_telemetry_analytics(
        shogun_id=sid, since=since_dt, until=until_dt,
    )


@router.get("/compliance")
async def compliance_report(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "auditor")),
):
    """Generate a governance-evidence summary; this does not establish conformity."""
    svc = FleetAuditService(db)
    return await svc.get_compliance_report()


@router.get("/export")
async def export_audit(
    since: str | None = None,
    until: str | None = None,
    limit: int = Query(10000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "auditor")),
):
    """Export the audit log as a CSV file."""
    svc = FleetAuditService(db)
    since_dt = datetime.fromisoformat(since) if since else None
    until_dt = datetime.fromisoformat(until) if until else None
    csv_data = await svc.export_audit_csv(since=since_dt, until=until_dt, limit=limit)

    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gensui_audit_export.csv"},
    )
