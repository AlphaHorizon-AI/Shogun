"""Fleet Audit Service — multi-instance analytics and governance evidence.

Extends the base AuditService with fleet-wide views:
- Per-member event breakdown
- Category/severity/action statistics
- Fleet governance-evidence dashboard data
- Audit chain verification per member
- CSV export support
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, case, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.db.models.audit_log import AuditLog
from gensui.db.models.telemetry_event import TelemetryEvent
from gensui.db.models.shogun_member import ShogunMember
from gensui.services.audit_service import AuditService


class FleetAuditService:
    """Fleet-wide audit analytics and governance-evidence summaries."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._audit = AuditService(session)

    # ── Fleet Dashboard Stats ────────────────────────────────

    async def get_fleet_audit_stats(self) -> dict:
        """Get aggregate audit statistics across the fleet."""
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)
        last_30d = now - timedelta(days=30)

        # Total audit entries
        total_result = await self.session.execute(
            select(func.count()).select_from(AuditLog)
        )
        total = total_result.scalar() or 0

        # Last 24h
        day_result = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.timestamp >= last_24h)
        )
        last_24h_count = day_result.scalar() or 0

        # Last 7d
        week_result = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.timestamp >= last_7d)
        )
        last_7d_count = week_result.scalar() or 0

        # By action category (group by action prefix)
        action_result = await self.session.execute(
            select(AuditLog.action, func.count())
            .group_by(AuditLog.action)
            .order_by(func.count().desc())
            .limit(20)
        )
        by_action = {row[0]: row[1] for row in action_result.all()}

        # By actor type
        actor_result = await self.session.execute(
            select(AuditLog.actor_type, func.count())
            .group_by(AuditLog.actor_type)
        )
        by_actor = {row[0]: row[1] for row in actor_result.all()}

        # Security-critical events
        critical_actions = [
            "harakiri.%", "policy.global%", "enrollment.reject%",
            "token.revoke%", "posture.%",
        ]
        critical_count = 0
        for pattern in critical_actions:
            r = await self.session.execute(
                select(func.count()).select_from(AuditLog)
                .where(AuditLog.action.like(pattern))
                .where(AuditLog.timestamp >= last_30d)
            )
            critical_count += (r.scalar() or 0)

        # Chain integrity
        chain_status = await self._audit.verify_chain(limit=500)

        return {
            "total_entries": total,
            "last_24h": last_24h_count,
            "last_7d": last_7d_count,
            "by_action": by_action,
            "by_actor_type": by_actor,
            "security_critical_30d": critical_count,
            "chain_integrity": {
                "valid": chain_status["valid"],
                "checked": chain_status["checked"],
                "errors": len(chain_status.get("errors", [])),
            },
        }

    # ── Per-Member Audit View ────────────────────────────────

    async def get_member_audit_summary(self) -> list[dict]:
        """Get audit event counts per fleet member."""
        # Get all members
        member_result = await self.session.execute(
            select(ShogunMember.id, ShogunMember.instance_name, ShogunMember.enrollment_status)
        )
        members = member_result.all()

        summaries = []
        for member_id, name, status in members:
            mid = str(member_id)

            # Count audit events targeting this member
            audit_count_r = await self.session.execute(
                select(func.count()).select_from(AuditLog)
                .where(AuditLog.target_id == mid)
            )
            audit_count = audit_count_r.scalar() or 0

            # Count telemetry events from this member
            telem_count_r = await self.session.execute(
                select(func.count()).select_from(TelemetryEvent)
                .where(TelemetryEvent.shogun_id == member_id)
            )
            telem_count = telem_count_r.scalar() or 0

            # Last event timestamp
            last_event_r = await self.session.execute(
                select(func.max(TelemetryEvent.timestamp))
                .where(TelemetryEvent.shogun_id == member_id)
            )
            last_event = last_event_r.scalar()

            # Critical events for this member
            critical_r = await self.session.execute(
                select(func.count()).select_from(TelemetryEvent)
                .where(TelemetryEvent.shogun_id == member_id)
                .where(TelemetryEvent.severity.in_(["error", "critical"]))
            )
            critical_count = critical_r.scalar() or 0

            summaries.append({
                "member_id": mid,
                "instance_name": name,
                "enrollment_status": status,
                "audit_events": audit_count,
                "telemetry_events": telem_count,
                "critical_events": critical_count,
                "last_event_at": last_event.isoformat() if last_event else None,
            })

        return sorted(summaries, key=lambda x: x["telemetry_events"], reverse=True)

    # ── Telemetry Analytics ──────────────────────────────────

    async def get_telemetry_analytics(
        self,
        shogun_id: uuid.UUID | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        """Get telemetry analytics (optionally filtered by member)."""
        now = datetime.now(timezone.utc)
        if not since:
            since = now - timedelta(days=7)
        if not until:
            until = now

        base = select(TelemetryEvent).where(
            TelemetryEvent.timestamp.between(since, until)
        )
        count_base = select(func.count()).select_from(TelemetryEvent).where(
            TelemetryEvent.timestamp.between(since, until)
        )

        if shogun_id:
            base = base.where(TelemetryEvent.shogun_id == shogun_id)
            count_base = count_base.where(TelemetryEvent.shogun_id == shogun_id)

        # Total count
        total_r = await self.session.execute(count_base)
        total = total_r.scalar() or 0

        # By category
        cat_q = (
            select(TelemetryEvent.event_category, func.count())
            .where(TelemetryEvent.timestamp.between(since, until))
            .group_by(TelemetryEvent.event_category)
        )
        if shogun_id:
            cat_q = cat_q.where(TelemetryEvent.shogun_id == shogun_id)
        cat_r = await self.session.execute(cat_q)
        by_category = {row[0]: row[1] for row in cat_r.all()}

        # By severity
        sev_q = (
            select(TelemetryEvent.severity, func.count())
            .where(TelemetryEvent.timestamp.between(since, until))
            .group_by(TelemetryEvent.severity)
        )
        if shogun_id:
            sev_q = sev_q.where(TelemetryEvent.shogun_id == shogun_id)
        sev_r = await self.session.execute(sev_q)
        by_severity = {row[0]: row[1] for row in sev_r.all()}

        # By event type (top 20)
        type_q = (
            select(TelemetryEvent.event_type, func.count())
            .where(TelemetryEvent.timestamp.between(since, until))
            .group_by(TelemetryEvent.event_type)
            .order_by(func.count().desc())
            .limit(20)
        )
        if shogun_id:
            type_q = type_q.where(TelemetryEvent.shogun_id == shogun_id)
        type_r = await self.session.execute(type_q)
        by_type = {row[0]: row[1] for row in type_r.all()}

        # By member (if not filtered)
        by_member = {}
        if not shogun_id:
            mem_q = (
                select(TelemetryEvent.shogun_id, func.count())
                .where(TelemetryEvent.timestamp.between(since, until))
                .group_by(TelemetryEvent.shogun_id)
                .order_by(func.count().desc())
            )
            mem_r = await self.session.execute(mem_q)
            by_member = {str(row[0]): row[1] for row in mem_r.all()}

        return {
            "total": total,
            "period": {"since": since.isoformat(), "until": until.isoformat()},
            "by_category": by_category,
            "by_severity": by_severity,
            "by_event_type": by_type,
            "by_member": by_member,
        }

    # ── Governance Evidence (legacy compliance endpoint) ─────

    async def get_compliance_report(self) -> dict:
        """Summarize governance evidence relevant to selected frameworks.

        The legacy endpoint name remains for API compatibility. Its output is
        evidence for human assessment, not a compliance determination.
        """
        now = datetime.now(timezone.utc)
        last_30d = now - timedelta(days=30)

        # Total members
        member_count_r = await self.session.execute(
            select(func.count()).select_from(ShogunMember)
        )
        total_members = member_count_r.scalar() or 0

        active_r = await self.session.execute(
            select(func.count()).select_from(ShogunMember)
            .where(ShogunMember.enrollment_status == "active")
        )
        active_members = active_r.scalar() or 0

        # Harakiri events in last 30 days
        harakiri_r = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action.like("harakiri%"))
            .where(AuditLog.timestamp >= last_30d)
        )
        harakiri_count = harakiri_r.scalar() or 0

        # Posture changes in last 30 days
        posture_r = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action.like("policy%"))
            .where(AuditLog.timestamp >= last_30d)
        )
        posture_changes = posture_r.scalar() or 0

        # Enrollment events
        enroll_r = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action.like("enrollment%"))
            .where(AuditLog.timestamp >= last_30d)
        )
        enrollment_events = enroll_r.scalar() or 0

        # Token revocations
        revoke_r = await self.session.execute(
            select(func.count()).select_from(AuditLog)
            .where(AuditLog.action.like("token.revoke%"))
            .where(AuditLog.timestamp >= last_30d)
        )
        revocations = revoke_r.scalar() or 0

        # Telemetry critical events
        telem_crit_r = await self.session.execute(
            select(func.count()).select_from(TelemetryEvent)
            .where(TelemetryEvent.severity.in_(["error", "critical"]))
            .where(TelemetryEvent.timestamp >= last_30d)
        )
        critical_telemetry = telem_crit_r.scalar() or 0

        # Chain integrity
        chain = await self._audit.verify_chain(limit=5000)

        return {
            "report_generated_at": now.isoformat(),
            "period": "last_30_days",
            "report_purpose": "governance_evidence",
            "assessment_notice": (
                "This summary can support a human NIS2, SOC 2, or EU AI Act "
                "assessment. It does not establish conformity or prove that "
                "every relevant event was captured."
            ),
            "fleet": {
                "total_members": total_members,
                "active_members": active_members,
            },
            "security_events": {
                "harakiri_activations": harakiri_count,
                "posture_changes": posture_changes,
                "enrollment_events": enrollment_events,
                "token_revocations": revocations,
                "critical_telemetry": critical_telemetry,
            },
            "chain_integrity": {
                "valid": chain["valid"],
                "entries_verified": chain["checked"],
                "chain_breaks": len(chain.get("errors", [])),
            },
            "compliance_frameworks": ["NIS2", "SOC2", "EU AI Act"],
        }

    # ── CSV Export ────────────────────────────────────────────

    async def export_audit_csv(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 10000,
    ) -> str:
        """Export audit log as CSV string."""
        entries, _ = await self._audit.query(
            since=since, until=until, limit=limit,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "timestamp", "actor_type", "actor_id", "action",
            "target_type", "target_id", "reason", "ip_address",
            "hash", "previous_hash",
        ])

        for e in entries:
            writer.writerow([
                str(e.id),
                e.timestamp.isoformat() if e.timestamp else "",
                e.actor_type or "",
                e.actor_id or "",
                e.action or "",
                e.target_type or "",
                e.target_id or "",
                e.reason or "",
                e.ip_address or "",
                e.hash or "",
                e.previous_hash or "",
            ])

        return output.getvalue()
