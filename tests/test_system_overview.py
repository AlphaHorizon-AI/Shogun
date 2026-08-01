from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api import security as security_api
from shogun.api import system as system_api
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.programming_memory import ProgrammingMemory
from shogun.services.memory_service import MemoryService


@pytest_asyncio.fixture
async def overview_memory_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)
        await connection.run_sync(ProgrammingMemory.__table__.create)
    async with sessions() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_active_record_count_is_zero_for_an_empty_installation(overview_memory_session):
    assert await MemoryService(overview_memory_session).count_active_records() == 0


@pytest.mark.asyncio
async def test_active_record_count_uses_installation_database(overview_memory_session):
    agent_id = uuid.uuid4()
    overview_memory_session.add_all([
        MemoryRecord(
            memory_type="semantic",
            agent_id=agent_id,
            title="Active memory",
            content="Count this record",
            is_archived=False,
        ),
        MemoryRecord(
            memory_type="semantic",
            agent_id=agent_id,
            title="Archived memory",
            content="Do not count this record",
            is_archived=True,
        ),
        ProgrammingMemory(
            agent_id=agent_id,
            workspace_key="workspace-key",
            workspace_name="workspace",
            title="Programming memory",
            problem="A problem",
            solution="A solution",
            content_hash="content-hash",
        ),
    ])
    await overview_memory_session.commit()

    assert await MemoryService(overview_memory_session).count_active_records() == 2


@pytest.mark.asyncio
async def test_overview_exposes_live_knowledge_volume(monkeypatch):
    class EmptyAgentService:
        async def get_all(self, **_kwargs):
            return [], 0

    class InstallationMemoryService:
        async def count_active_records(self):
            return 37

    async def healthy_qdrant():
        return "healthy"

    async def tactical_posture():
        return {"active_tier": "tactical"}

    monkeypatch.setattr(system_api, "_check_qdrant", healthy_qdrant)
    monkeypatch.setattr(security_api, "_get_agent_posture", tactical_posture)

    response = await system_api.get_overview(
        agent_svc=EmptyAgentService(),
        mission_svc=None,
        memory_svc=InstallationMemoryService(),
        security_svc=None,
    )

    assert response.data["knowledge_volume"] == 37
