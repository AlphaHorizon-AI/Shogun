"""Bushido service — jobs, recommendations, and schedules."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.bushido import BushidoJob, BushidoRecommendation, BushidoSchedule
from shogun.services.base_service import BaseService


class BushidoJobService(BaseService[BushidoJob]):
    def __init__(self, session: AsyncSession):
        super().__init__(BushidoJob, session)


class BushidoRecommendationService(BaseService[BushidoRecommendation]):
    def __init__(self, session: AsyncSession):
        super().__init__(BushidoRecommendation, session)

    async def get_pending(self) -> list[BushidoRecommendation]:
        result = await self.session.execute(
            select(BushidoRecommendation).where(BushidoRecommendation.status == "pending")
        )
        return list(result.scalars().all())


class BushidoScheduleService(BaseService[BushidoSchedule]):
    def __init__(self, session: AsyncSession):
        super().__init__(BushidoSchedule, session)

    async def get_enabled(self) -> list[BushidoSchedule]:
        """Return all enabled schedule definitions."""
        result = await self.session.execute(
            select(BushidoSchedule).where(BushidoSchedule.is_enabled == True)
        )
        return list(result.scalars().all())

    async def get_presets(self) -> list[BushidoSchedule]:
        """Return the 4 built-in preset schedules."""
        result = await self.session.execute(
            select(BushidoSchedule).where(BushidoSchedule.is_preset == True)
        )
        return list(result.scalars().all())

    async def get_by_job_type(self, job_type: str) -> BushidoSchedule | None:
        """Return the first schedule matching a job type (useful for presets)."""
        result = await self.session.execute(
            select(BushidoSchedule).where(
                BushidoSchedule.job_type == job_type,
                BushidoSchedule.is_preset == True,
            )
        )
        return result.scalars().first()

    async def upsert_preset_enabled(self, job_type: str, enabled: bool) -> BushidoSchedule | None:
        """Toggle a preset schedule on/off. Creates it if somehow missing."""
        schedule = await self.get_by_job_type(job_type)
        if schedule is None:
            return None
        schedule.is_enabled = enabled
        await self.session.flush()
        await self.session.refresh(schedule)
        return schedule
