"""Member service — Shogun enrollment, identity, and status management."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.config import gensui_settings
from gensui.db.models.shogun_member import ShogunMember
from gensui.db.models.enrollment_token import EnrollmentToken


class MemberService:
    """Manages Shogun member lifecycle: enrollment, heartbeat, status."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Enrollment Tokens ────────────────────────────────────

    async def create_enrollment_token(
        self,
        label: str | None = None,
        max_uses: int = 1,
        created_by: str | None = None,
        expires_at: datetime | None = None,
    ) -> EnrollmentToken:
        """Generate a new enrollment token."""
        raw_token = f"gensui_enroll_{secrets.token_urlsafe(32)}"
        token = EnrollmentToken(
            token=f"sha256:{hashlib.sha256(raw_token.encode('utf-8')).hexdigest()}",
            label=label,
            max_uses=max_uses,
            created_by_admin_id=created_by,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        token._issued_token = raw_token
        return token

    async def validate_token(self, token_str: str) -> EnrollmentToken | None:
        """Validate an enrollment token. Returns it if valid, None otherwise."""
        token_hash = f"sha256:{hashlib.sha256(token_str.encode('utf-8')).hexdigest()}"
        result = await self.session.execute(
            select(EnrollmentToken).where(EnrollmentToken.token == token_hash)
        )
        token = result.scalars().first()
        if token is None:
            legacy = await self.session.execute(
                select(EnrollmentToken).where(EnrollmentToken.token == token_str)
            )
            token = legacy.scalars().first()
            if token is not None:
                token.token = token_hash
                await self.session.flush()
        if token is None:
            return None
        if token.is_revoked:
            return None
        if token.use_count >= token.max_uses:
            return None
        if token.expires_at and token.expires_at < datetime.now(timezone.utc):
            return None
        return token

    async def list_tokens(self) -> list[EnrollmentToken]:
        """List all enrollment tokens."""
        result = await self.session.execute(select(EnrollmentToken))
        return list(result.scalars().all())

    async def revoke_token(self, token_id: uuid.UUID) -> EnrollmentToken | None:
        """Revoke an enrollment token so it can no longer be used."""
        result = await self.session.execute(
            select(EnrollmentToken).where(EnrollmentToken.id == token_id)
        )
        token = result.scalars().first()
        if token is None:
            return None
        token.is_revoked = True
        await self.session.flush()
        return token

    # ── Enrollment ───────────────────────────────────────────

    async def enroll(
        self,
        token_str: str,
        instance_name: str,
        hostname: str | None = None,
        environment: str = "development",
        organization: str | None = None,
        owner: str | None = None,
        version: str | None = None,
        build_hash: str | None = None,
        public_key: str | None = None,
        local_os: str | None = None,
        deployment_type: str | None = None,
        metadata: dict | None = None,
    ) -> ShogunMember | None:
        """Enroll a new Shogun instance. Returns member or None if token is invalid."""
        token = await self.validate_token(token_str)
        if token is None:
            return None

        # Increment token usage
        token.use_count += 1

        # Determine initial enrollment status
        status = "pending" if gensui_settings.gensui_require_enrollment_approval else "active"

        member_token = secrets.token_urlsafe(48)
        member = ShogunMember(
            instance_name=instance_name,
            hostname=hostname,
            environment=environment,
            organization=organization,
            owner=owner,
            version=version,
            build_hash=build_hash,
            public_key=public_key,
            member_token_hash=hashlib.sha256(member_token.encode("ascii")).hexdigest(),
            local_os=local_os,
            deployment_type=deployment_type,
            enrollment_status=status,
            status="online" if status == "active" else "unknown",
            last_seen_at=datetime.now(timezone.utc) if status == "active" else None,
            metadata_json=metadata or {},
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        member._issued_member_token = member_token
        return member

    async def approve(self, member_id: uuid.UUID) -> ShogunMember | None:
        """Approve a pending enrollment."""
        result = await self.session.execute(
            select(ShogunMember).where(ShogunMember.id == member_id)
        )
        member = result.scalars().first()
        if member is None:
            return None
        member.enrollment_status = "active"
        member.status = "online"
        member.last_seen_at = datetime.now(timezone.utc)
        await self.session.flush()
        return member

    async def reject(self, member_id: uuid.UUID) -> ShogunMember | None:
        """Reject a pending enrollment."""
        result = await self.session.execute(
            select(ShogunMember).where(ShogunMember.id == member_id)
        )
        member = result.scalars().first()
        if member is None:
            return None
        member.enrollment_status = "revoked"
        await self.session.flush()
        return member

    # ── Member CRUD ──────────────────────────────────────────

    async def get_by_id(self, member_id: uuid.UUID) -> ShogunMember | None:
        """Fetch a member by ID."""
        result = await self.session.execute(
            select(ShogunMember).where(ShogunMember.id == member_id)
        )
        return result.scalars().first()

    async def list_members(
        self,
        status_filter: str | None = None,
        enrollment_filter: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[ShogunMember], int]:
        """List members with optional filters. Returns (members, total)."""
        query = select(ShogunMember)
        count_query = select(func.count()).select_from(ShogunMember)

        if status_filter:
            query = query.where(ShogunMember.status == status_filter)
            count_query = count_query.where(ShogunMember.status == status_filter)
        if enrollment_filter:
            query = query.where(ShogunMember.enrollment_status == enrollment_filter)
            count_query = count_query.where(ShogunMember.enrollment_status == enrollment_filter)

        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        result = await self.session.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def disable(self, member_id: uuid.UUID) -> ShogunMember | None:
        """Disable a member."""
        member = await self.get_by_id(member_id)
        if member is None:
            return None
        member.enrollment_status = "disabled"
        member.status = "offline"
        await self.session.flush()
        return member

    # ── Heartbeat ────────────────────────────────────────────

    async def process_heartbeat(
        self,
        shogun_id: uuid.UUID,
        version: str | None = None,
        effective_posture: str | None = None,
        harakiri_state: str | None = None,
        samurai_count: int = 0,
        active_workflow_count: int = 0,
        active_mado_sessions: int = 0,
        health: dict | None = None,
        nexus_peers: list[str] | None = None,
        external_agents: list[dict] | None = None,
    ) -> ShogunMember | None:
        """Process a heartbeat from a member Shogun."""
        member = await self.get_by_id(shogun_id)
        if member is None or member.enrollment_status != "active":
            return None

        member.status = "online"
        member.last_seen_at = datetime.now(timezone.utc)
        if version:
            member.version = version
        if harakiri_state:
            member.harakiri_state = harakiri_state
        member.samurai_count = samurai_count
        member.active_workflow_count = active_workflow_count
        member.active_mado_sessions = active_mado_sessions

        meta = dict(member.metadata_json or {})
        if health:
            meta["health"] = health
        if nexus_peers is not None:
            meta["nexus_peers"] = nexus_peers
        if external_agents is not None:
            meta["external_agents"] = external_agents
        member.metadata_json = meta

        await self.session.flush()
        return member

    # ── Statistics ────────────────────────────────────────────

    async def get_stats(self) -> dict:
        """Get fleet-wide statistics."""
        total_result = await self.session.execute(
            select(func.count()).select_from(ShogunMember)
        )
        total = total_result.scalar() or 0

        online_result = await self.session.execute(
            select(func.count()).select_from(ShogunMember).where(
                ShogunMember.status == "online",
                ShogunMember.enrollment_status == "active",
            )
        )
        online = online_result.scalar() or 0

        pending_result = await self.session.execute(
            select(func.count()).select_from(ShogunMember).where(
                ShogunMember.enrollment_status == "pending"
            )
        )
        pending = pending_result.scalar() or 0

        harakiri_result = await self.session.execute(
            select(func.count()).select_from(ShogunMember).where(
                ShogunMember.harakiri_state != "none"
            )
        )
        harakiri = harakiri_result.scalar() or 0

        samurai_result = await self.session.execute(
            select(func.coalesce(func.sum(ShogunMember.samurai_count), 0)).select_from(ShogunMember).where(
                ShogunMember.enrollment_status == "active"
            )
        )
        total_samurai = samurai_result.scalar() or 0

        workflow_result = await self.session.execute(
            select(func.coalesce(func.sum(ShogunMember.active_workflow_count), 0)).select_from(ShogunMember).where(
                ShogunMember.enrollment_status == "active"
            )
        )
        total_workflows = workflow_result.scalar() or 0

        mado_result = await self.session.execute(
            select(func.coalesce(func.sum(ShogunMember.active_mado_sessions), 0)).select_from(ShogunMember).where(
                ShogunMember.enrollment_status == "active"
            )
        )
        total_mado = mado_result.scalar() or 0

        return {
            "total_members": total,
            "online_members": online,
            "offline_members": total - online - pending,
            "pending_enrollment": pending,
            "harakiri_active": harakiri,
            "total_samurai": total_samurai,
            "total_workflows": total_workflows,
            "total_mado_sessions": total_mado,
        }
