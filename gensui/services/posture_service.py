"""Posture service — CRUD, assignment, and effective posture resolution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.db.models.security_posture import SecurityPosture
from gensui.db.models.global_posture import GlobalPostureState
from gensui.db.models.shogun_member import ShogunMember
from gensui.db.models.member_group import MemberGroup
from gensui.db.models.group_membership import GroupMembership


class PostureService:
    """Manages security postures and effective posture resolution."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Posture CRUD ─────────────────────────────────────────

    async def get_by_id(self, posture_id: uuid.UUID) -> SecurityPosture | None:
        """Fetch a posture by ID."""
        result = await self.session.execute(
            select(SecurityPosture).where(SecurityPosture.id == posture_id)
        )
        return result.scalars().first()

    async def get_by_name(self, name: str) -> SecurityPosture | None:
        """Fetch a posture by name."""
        result = await self.session.execute(
            select(SecurityPosture).where(SecurityPosture.name == name)
        )
        return result.scalars().first()

    async def list_postures(self) -> list[SecurityPosture]:
        """List all security postures."""
        result = await self.session.execute(
            select(SecurityPosture).order_by(SecurityPosture.level)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> SecurityPosture:
        """Create a new security posture."""
        posture = SecurityPosture(**kwargs)
        self.session.add(posture)
        await self.session.flush()
        await self.session.refresh(posture)
        return posture

    async def update(self, posture_id: uuid.UUID, **kwargs) -> SecurityPosture | None:
        """Update a security posture."""
        posture = await self.get_by_id(posture_id)
        if posture is None:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(posture, key, value)
        await self.session.flush()
        return posture

    # ── Assignment ───────────────────────────────────────────

    async def assign_to_member(
        self,
        member_id: uuid.UUID,
        posture_id: uuid.UUID,
    ) -> ShogunMember | None:
        """Assign a posture to an individual Shogun."""
        result = await self.session.execute(
            select(ShogunMember).where(ShogunMember.id == member_id)
        )
        member = result.scalars().first()
        if member is None:
            return None
        member.individual_posture_id = posture_id
        # Recalculate effective posture
        effective = await self.resolve_effective_posture(member_id)
        if effective:
            member.effective_posture_id = effective.id
        await self.session.flush()
        return member

    async def assign_to_group(
        self,
        group_id: uuid.UUID,
        posture_id: uuid.UUID,
    ) -> MemberGroup | None:
        """Assign a posture to a group."""
        result = await self.session.execute(
            select(MemberGroup).where(MemberGroup.id == group_id)
        )
        group = result.scalars().first()
        if group is None:
            return None
        group.posture_id = posture_id
        await self.session.flush()
        return group

    # ── Global Posture ───────────────────────────────────────

    async def get_global_state(self) -> GlobalPostureState | None:
        """Get the current global posture state."""
        result = await self.session.execute(select(GlobalPostureState))
        return result.scalars().first()

    async def set_global_posture(
        self,
        posture_id: uuid.UUID,
        activated_by: str,
        reason: str | None = None,
    ) -> GlobalPostureState:
        """Activate a global posture override."""
        posture = await self.get_by_id(posture_id)
        state = await self.get_global_state()

        if state is None:
            state = GlobalPostureState(
                is_active=True,
                posture_id=posture_id,
                posture_name=posture.name if posture else "UNKNOWN",
                activated_by=activated_by,
                activated_at=datetime.now(timezone.utc),
                reason=reason,
            )
            self.session.add(state)
        else:
            state.is_active = True
            state.posture_id = posture_id
            state.posture_name = posture.name if posture else "UNKNOWN"
            state.activated_by = activated_by
            state.activated_at = datetime.now(timezone.utc)
            state.reason = reason

        await self.session.flush()
        await self.session.refresh(state)
        return state

    async def clear_global_posture(self) -> GlobalPostureState | None:
        """Deactivate the global posture override."""
        state = await self.get_global_state()
        if state is None:
            return None
        state.is_active = False
        await self.session.flush()
        return state

    # ── Effective Posture Resolution ─────────────────────────

    async def resolve_effective_posture(
        self,
        member_id: uuid.UUID,
    ) -> SecurityPosture | None:
        """Resolve the effective posture for a Shogun member.

        Precedence:
        1. Global posture override (if active)
        2. Active Harakiri state → LOCKDOWN
        3. Individual posture override
        4. Highest-risk group posture
        5. Default organization posture
        """
        # 1. Check global posture
        global_state = await self.get_global_state()
        if global_state and global_state.is_active and global_state.posture_id:
            return await self.get_by_id(global_state.posture_id)

        # Get the member
        result = await self.session.execute(
            select(ShogunMember).where(ShogunMember.id == member_id)
        )
        member = result.scalars().first()
        if member is None:
            return None

        # 2. Harakiri state → LOCKDOWN
        if member.harakiri_state and member.harakiri_state != "none":
            lockdown = await self.get_by_name("LOCKDOWN")
            if lockdown:
                return lockdown

        # 3. Individual posture override
        if member.individual_posture_id:
            individual = await self.get_by_id(member.individual_posture_id)
            if individual:
                return individual

        # 4. Highest-risk group posture
        groups_result = await self.session.execute(
            select(MemberGroup).join(
                GroupMembership,
                GroupMembership.group_id == MemberGroup.id,
            ).where(
                GroupMembership.shogun_id == member_id,
                MemberGroup.posture_id.isnot(None),
            )
        )
        groups = groups_result.scalars().all()
        if groups:
            # Find the highest-level (most restrictive) group posture
            highest = None
            highest_level = -1
            for group in groups:
                if group.posture_id:
                    posture = await self.get_by_id(group.posture_id)
                    if posture and posture.level > highest_level:
                        highest = posture
                        highest_level = posture.level
            if highest:
                return highest

        # 5. Default posture
        if member.default_posture_id:
            return await self.get_by_id(member.default_posture_id)

        # Fallback: STANDARD
        return await self.get_by_name("STANDARD")

    async def get_effective_posture_with_explanation(
        self,
        member_id: uuid.UUID,
    ) -> dict:
        """Resolve effective posture and explain why."""
        posture = await self.resolve_effective_posture(member_id)
        if posture is None:
            return {"posture": None, "reason": "No posture configured"}

        # Determine the reason
        global_state = await self.get_global_state()
        if global_state and global_state.is_active:
            reason = f"Global posture override: {posture.name}"
            source = "global"
        else:
            result = await self.session.execute(
                select(ShogunMember).where(ShogunMember.id == member_id)
            )
            member = result.scalars().first()
            if member and member.harakiri_state != "none":
                reason = f"Harakiri active — forced to {posture.name}"
                source = "harakiri"
            elif member and member.individual_posture_id:
                reason = f"Individual posture assignment: {posture.name}"
                source = "individual"
            else:
                reason = f"Default posture: {posture.name}"
                source = "default"

        return {
            "posture_id": str(posture.id),
            "posture_name": posture.name,
            "level": posture.level,
            "source": source,
            "reason": reason,
            "rules": {
                "allow_external_models": posture.allow_external_models,
                "allow_local_models": posture.allow_local_models,
                "allow_tool_execution": posture.allow_tool_execution,
                "allow_mado": posture.allow_mado,
                "allow_memory_write": posture.allow_memory_write,
                "allow_memory_read": posture.allow_memory_read,
                "allow_agent_flow": posture.allow_agent_flow,
                "allow_nexus": posture.allow_nexus,
                "allow_samurai_delegation": posture.allow_samurai_delegation,
                "allow_scheduled_triggers": posture.allow_scheduled_triggers,
                "allow_autonomous_loops": posture.allow_autonomous_loops,
                "allow_external_web": posture.allow_external_web,
                "allow_file_write": posture.allow_file_write,
                "allow_external_api": posture.allow_external_api,
            },
            "tool_overrides": posture.tool_overrides_json or {},
            "advanced_controls": posture.advanced_toolgate_json or {
                "enabled": False,
                "rules": [],
            },
            "global_posture_active": bool(global_state and global_state.is_active),
        }
