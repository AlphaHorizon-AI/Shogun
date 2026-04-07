"""Model service — providers, definitions, and routing profiles."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_definition import ModelDefinition
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.services.base_service import BaseService

import uuid


class ModelProviderService(BaseService[ModelProvider]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelProvider, session)

    async def get_by_slug(self, slug: str) -> ModelProvider | None:
        result = await self.session.execute(
            select(ModelProvider).where(ModelProvider.slug == slug)
        )
        return result.scalars().first()


class ModelDefinitionService(BaseService[ModelDefinition]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelDefinition, session)

    async def get_by_provider(self, provider_id: uuid.UUID) -> list[ModelDefinition]:
        result = await self.session.execute(
            select(ModelDefinition).where(ModelDefinition.provider_id == provider_id)
        )
        return list(result.scalars().all())


class ModelRoutingProfileService(BaseService[ModelRoutingProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelRoutingProfile, session)

    async def get_default(self) -> ModelRoutingProfile | None:
        result = await self.session.execute(
            select(ModelRoutingProfile).where(ModelRoutingProfile.is_default == True)
        )
        return result.scalars().first()
