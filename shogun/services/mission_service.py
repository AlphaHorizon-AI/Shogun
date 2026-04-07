"""Mission service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.mission import Mission
from shogun.services.base_service import BaseService

import uuid


class MissionService(BaseService[Mission]):
    def __init__(self, session: AsyncSession):
        super().__init__(Mission, session)

    async def cancel(self, mission_id: uuid.UUID) -> Mission | None:
        return await self.update(mission_id, status="cancelled")
