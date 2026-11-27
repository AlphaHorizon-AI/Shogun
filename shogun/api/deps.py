"""API dependencies — shared dependency injection for core AgentFlow routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.engine import get_async_session
from shogun.services.agent_flow_service import AgentFlowService
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


def get_model_provider_service(db: AsyncSession = Depends(get_db)) -> ModelProviderService:
    return ModelProviderService(db)


def get_model_routing_service(db: AsyncSession = Depends(get_db)) -> ModelRoutingProfileService:
    return ModelRoutingProfileService(db)


def get_agent_flow_service(db: AsyncSession = Depends(get_db)) -> AgentFlowService:
    return AgentFlowService(db)
