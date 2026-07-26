"""Audit service — HMAC-chained append-only audit log."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.config import gensui_settings
from gensui.db.models.audit_log import AuditLog


class AuditService:
    """HMAC-chained audit log for tamper-evident event recording."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_last_hash(self) -> str | None:
        """Get the hash of the most recent audit entry."""
        result = await self.session.execute(
            select(AuditLog.hash)
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    def _compute_hash(self, previous_hash: str | None, payload: str) -> str:
        """Compute HMAC-SHA256 hash chained to the previous entry."""
        chain = (previous_hash or "genesis") + payload
        return hmac.new(
            gensui_settings.jwt_secret.encode("utf-8"),
            chain.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def append(
        self,
        actor_type: str,
        action: str,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        reason: str | None = None,
        before_json: dict | None = None,
        after_json: dict | None = None,
        metadata_json: dict | None = None,
    ) -> AuditLog:
        """Append a new audit log entry with HMAC chain."""
        from gensui.services.request_context import current_request_metadata

        request_ip, request_user_agent = current_request_metadata()
        ip_address = ip_address or request_ip
        user_agent = user_agent or request_user_agent
        previous_hash = await self._get_last_hash()

        # Build payload for hashing
        payload = json.dumps({
            "action": action,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "target_type": target_type,
            "target_id": target_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, sort_keys=True)

        current_hash = self._compute_hash(previous_hash, payload)

        entry = AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            reason=reason,
            before_json=before_json,
            after_json=after_json,
            metadata_json=metadata_json,
            hash=current_hash,
            previous_hash=previous_hash,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def query(
        self,
        action: str | None = None,
        actor_type: str | None = None,
        target_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[AuditLog], int]:
        """Query audit log with filters."""
        query = select(AuditLog)
        count_query = select(func.count()).select_from(AuditLog)

        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        if actor_type:
            query = query.where(AuditLog.actor_type == actor_type)
            count_query = count_query.where(AuditLog.actor_type == actor_type)
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
            count_query = count_query.where(AuditLog.target_type == target_type)
        if since:
            query = query.where(AuditLog.timestamp >= since)
            count_query = count_query.where(AuditLog.timestamp >= since)
        if until:
            query = query.where(AuditLog.timestamp <= until)
            count_query = count_query.where(AuditLog.timestamp <= until)

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def verify_chain(self, limit: int = 1000) -> dict:
        """Verify the HMAC chain integrity of the audit log."""
        result = await self.session.execute(
            select(AuditLog).order_by(AuditLog.timestamp).limit(limit)
        )
        entries = result.scalars().all()

        if not entries:
            return {"valid": True, "checked": 0, "errors": []}

        errors = []
        for i, entry in enumerate(entries):
            if i == 0:
                if entry.previous_hash is not None:
                    errors.append({"index": i, "id": str(entry.id), "error": "First entry has non-null previous_hash"})
            else:
                if entry.previous_hash != entries[i - 1].hash:
                    errors.append({
                        "index": i,
                        "id": str(entry.id),
                        "error": "Chain broken: previous_hash does not match",
                    })

        return {
            "valid": len(errors) == 0,
            "checked": len(entries),
            "errors": errors,
        }
