"""API dependencies — shared dependency injection for all routes."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.engine import get_async_session
from shogun.services.persona_service import PersonaService
from shogun.services.kaizen_service import KaizenService
from shogun.services.agent_service import AgentService
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService
from shogun.services.tool_service import ToolService
from shogun.services.security_service import SecurityService
from shogun.services.skill_service import SkillService, SkillSourceService
from shogun.services.memory_service import MemoryService
from shogun.services.bushido_service import BushidoJobService, BushidoRecommendationService
from shogun.services.mission_service import MissionService
from shogun.services.audit_service import AuditService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


def get_persona_service(db: AsyncSession = Depends(get_db)) -> PersonaService:
    return PersonaService(db)


def get_kaizen_service(db: AsyncSession = Depends(get_db)) -> KaizenService:
    return KaizenService(db)


def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)


def get_model_provider_service(db: AsyncSession = Depends(get_db)) -> ModelProviderService:
    return ModelProviderService(db)


def get_model_routing_service(db: AsyncSession = Depends(get_db)) -> ModelRoutingProfileService:
    return ModelRoutingProfileService(db)


def get_tool_service(db: AsyncSession = Depends(get_db)) -> ToolService:
    return ToolService(db)


def get_security_service(db: AsyncSession = Depends(get_db)) -> SecurityService:
    return SecurityService(db)


def get_skill_service(db: AsyncSession = Depends(get_db)) -> SkillService:
    return SkillService(db)


def get_skill_source_service(db: AsyncSession = Depends(get_db)) -> SkillSourceService:
    return SkillSourceService(db)


def get_memory_service(db: AsyncSession = Depends(get_db)) -> MemoryService:
    return MemoryService(db)


def get_bushido_job_service(db: AsyncSession = Depends(get_db)) -> BushidoJobService:
    return BushidoJobService(db)


def get_bushido_recommendation_service(db: AsyncSession = Depends(get_db)) -> BushidoRecommendationService:
    return BushidoRecommendationService(db)


def get_mission_service(db: AsyncSession = Depends(get_db)) -> MissionService:
    return MissionService(db)


def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(db)
