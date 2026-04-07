"""Agent service."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.samurai_profile import SamuraiProfile
from shogun.services.base_service import BaseService


class AgentService(BaseService[Agent]):
    def __init__(self, session: AsyncSession):
        super().__init__(Agent, session)

    async def get_by_slug(self, slug: str) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(Agent.slug == slug, Agent.is_deleted == False)
        )
        return result.scalars().first()

    async def get_primary_shogun(self) -> Agent | None:
        result = await self.session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        return result.scalars().first()

    async def get_active_samurai(self) -> list[Agent]:
        result = await self.session.execute(
            select(Agent).where(
                Agent.agent_type == "samurai",
                Agent.status.in_(["active", "idle", "running"]),
                Agent.is_deleted == False,
            )
        )
        return list(result.scalars().all())

    async def suspend(self, agent_id: uuid.UUID) -> Agent | None:
        return await self.update(agent_id, status="suspended")

    async def resume(self, agent_id: uuid.UUID) -> Agent | None:
        return await self.update(agent_id, status="active")

    async def update_samurai_profile(
        self, agent_id: uuid.UUID, **kwargs
    ) -> SamuraiProfile | None:
        result = await self.session.execute(
            select(SamuraiProfile).where(SamuraiProfile.agent_id == agent_id)
        )
        profile = result.scalars().first()

        if profile is None:
            profile = SamuraiProfile(agent_id=agent_id, **kwargs)
            self.session.add(profile)
        else:
            for key, value in kwargs.items():
                if value is not None:
                    setattr(profile, key, value)

        await self.session.flush()
        await self.session.refresh(profile)
        return profile
