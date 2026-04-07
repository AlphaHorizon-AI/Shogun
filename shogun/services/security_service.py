"""Security service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.security_policy import SecurityPolicy
from shogun.services.base_service import BaseService


class SecurityService(BaseService[SecurityPolicy]):
    def __init__(self, session: AsyncSession):
        super().__init__(SecurityPolicy, session)

    async def get_by_tier(self, tier: str) -> SecurityPolicy | None:
        result = await self.session.execute(
            select(SecurityPolicy).where(SecurityPolicy.tier == tier).limit(1)
        )
        return result.scalars().first()

    async def get_builtin_policies(self) -> list[SecurityPolicy]:
        result = await self.session.execute(
            select(SecurityPolicy).where(SecurityPolicy.is_builtin == True)
        )
        return list(result.scalars().all())
