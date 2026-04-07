"""Kaizen service."""

from __future__ import annotations

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.kaizen import KaizenProfile
from shogun.services.base_service import BaseService

import uuid


class KaizenService(BaseService[KaizenProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(KaizenProfile, session)

    async def get_active_for_target(self, target_type: str, target_id: uuid.UUID) -> KaizenProfile | None:
        result = await self.session.execute(
            select(KaizenProfile)
            .where(
                KaizenProfile.target_type == target_type,
                KaizenProfile.target_id == target_id,
                KaizenProfile.status == "active",
            )
            .order_by(desc(KaizenProfile.version))
            .limit(1)
        )
        return result.scalars().first()

    async def get_versions(self, target_type: str, target_id: uuid.UUID) -> list[KaizenProfile]:
        result = await self.session.execute(
            select(KaizenProfile)
            .where(
                KaizenProfile.target_type == target_type,
                KaizenProfile.target_id == target_id,
            )
            .order_by(desc(KaizenProfile.version))
        )
        return list(result.scalars().all())

    async def create_version(self, **kwargs) -> KaizenProfile:
        # Get current max version
        target_type = kwargs.get("target_type")
        target_id = kwargs.get("target_id")
        versions = await self.get_versions(target_type, target_id)
        next_version = (versions[0].version + 1) if versions else 1

        # Deactivate old versions
        for v in versions:
            if v.status == "active":
                v.status = "superseded"

        kwargs["version"] = next_version
        kwargs["status"] = "active"
        return await self.create(**kwargs)
