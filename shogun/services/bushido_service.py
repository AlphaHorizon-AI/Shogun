"""Bushido service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.bushido import BushidoJob, BushidoRecommendation
from shogun.services.base_service import BaseService

import uuid


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
