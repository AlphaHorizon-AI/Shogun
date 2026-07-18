from __future__ import annotations

import uuid
from importlib import import_module

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.agents import _classify_chat_mode
from shogun.api.memory import (
    _programming_archive_record,
    delete_programming_memory,
    list_programming_memories,
)
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.programming_memory import ProgrammingMemory
from shogun.services.memory_service import MemoryService
from shogun.services.native_skills import NATIVE_TOOLS
from shogun.services.programming_memory import ProgrammingMemoryService
from shogun.services.self_learning import (
    capture_operator_correction,
    capture_researched_solution,
    is_explicit_operator_correction,
)


@pytest_asyncio.fixture
async def memory_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(ProgrammingMemory.__table__.create)
    async with sessions() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def self_learning_sessions(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)

    engine_module = import_module("shogun.db.engine")
    memory_service_module = import_module("shogun.services.memory_service")

    class _VectorStore:
        def upsert(self, **_kwargs):
            return None

    monkeypatch.setattr(engine_module, "async_session_factory", sessions)
    monkeypatch.setattr(memory_service_module, "get_vector_store", lambda: _VectorStore())
    yield sessions
    await engine.dispose()


@pytest.mark.asyncio
async def test_programming_memory_is_project_scoped_deduplicated_and_reinforced(memory_session, tmp_path):
    service = ProgrammingMemoryService(memory_session)
    workspace_a = service.workspace_key(tmp_path / "project-a")
    workspace_b = service.workspace_key(tmp_path / "project-b")
    agent_id = uuid.uuid4()

    record, created = await service.remember(
        agent_id=agent_id,
        workspace_key=workspace_a,
        workspace_name="project-a",
        title="Fix async database lock",
        problem="SQLite migration fails with a duplicate column during startup",
        solution="Establish the verified legacy baseline before upgrading to head",
        validation_status="tests_passed",
        evidence="pytest: 9 passed",
        languages=["Python"],
        files=["shogun/app.py"],
    )
    duplicate, duplicate_created = await service.remember(
        agent_id=agent_id,
        workspace_key=workspace_a,
        workspace_name="project-a",
        title="Same fix",
        problem="SQLite migration fails with a duplicate column during startup",
        solution="Establish the verified legacy baseline before upgrading to head",
        validation_status="unverified",
        tags=["migration"],
    )
    await memory_session.commit()

    assert created is True and duplicate_created is False
    assert duplicate.id == record.id
    assert duplicate.validation_status == "tests_passed"
    assert "migration" in duplicate.tags
    assert await service.search(workspace_key=workspace_b, query="duplicate column") == []

    results = await service.search(workspace_key=workspace_a, query="sqlite duplicate column migration")
    assert results[0]["id"] == str(record.id)
    assert results[0]["validation_status"] == "tests_passed"

    prior_confidence = record.confidence_score
    reinforced = await service.reinforce(record.id, workspace_key=workspace_a, successful=True)
    assert reinforced.successful_use_count == 1
    assert reinforced.confidence_score > prior_confidence
    assert await service.reinforce(record.id, workspace_key=workspace_b, successful=True) is None

    archive_record = _programming_archive_record(record)
    assert archive_record["memory_type"] == "programming"
    assert archive_record["workspace_name"] == "project-a"
    assert archive_record["validation_status"] == "tests_passed"
    assert archive_record["content"] == record.solution


@pytest.mark.asyncio
async def test_programming_archive_api_lists_searches_and_deletes(memory_session, tmp_path):
    service = ProgrammingMemoryService(memory_session)
    record, _ = await service.remember(
        agent_id=uuid.uuid4(),
        workspace_key=service.workspace_key(tmp_path / "archive-project"),
        workspace_name="archive-project",
        title="Repair migration startup",
        problem="Startup cannot find the schema baseline",
        solution="Stamp the verified baseline before upgrading",
        validation_status="tests_passed",
        evidence="22 tests passed",
        files=["shogun/app.py"],
        languages=["Python"],
    )
    await memory_session.commit()

    response = await list_programming_memories(
        query="schema baseline",
        workspace_key=None,
        agent_id=None,
        kind=None,
        validation_status=None,
        sort_by="created_at",
        limit=200,
        svc=MemoryService(memory_session),
    )
    assert len(response.data) == 1
    assert response.data[0]["id"] == str(record.id)
    assert response.data[0]["files"] == ["shogun/app.py"]

    deleted = await delete_programming_memory(record.id, svc=MemoryService(memory_session))
    assert deleted.data == {"deleted": True, "id": str(record.id)}
    assert await memory_session.get(ProgrammingMemory, record.id) is None


def test_explicit_corrections_route_to_memory_aware_chat():
    assert is_explicit_operator_correction("No, that is not the correct API endpoint.")
    assert is_explicit_operator_correction("Actually: use port 8000.")
    assert not is_explicit_operator_correction("Is this answer incorrect?")
    assert _classify_chat_mode("That's wrong; the topic identifier is 22.", [])["mode"] == "governed"


def test_programming_memory_tools_are_exposed():
    by_name = {tool["function"]["name"]: tool["function"] for tool in NATIVE_TOOLS}
    names = set(by_name)
    assert {"ide_memory_search", "ide_memory_store", "ide_memory_reinforce"} <= names
    assert by_name["ide_memory_store"]["parameters"]["required"] == [
        "workspace_id",
        "title",
        "problem",
        "solution",
        "validation_status",
    ]


@pytest.mark.asyncio
async def test_operator_correction_is_persisted_and_deduplicated(self_learning_sessions):
    agent_id = uuid.uuid4()
    first = await capture_operator_correction(
        agent_id=agent_id,
        user_message="Actually: the service listens on port 8000.",
        history=[{"role": "assistant", "content": "It listens on port 9000."}],
        source_type="governed_chat",
    )
    duplicate = await capture_operator_correction(
        agent_id=agent_id,
        user_message="Actually: the service listens on port 8000.",
        history=[{"role": "assistant", "content": "It listens on port 9000."}],
        source_type="governed_chat",
    )

    async with self_learning_sessions() as session:
        records = list((await session.scalars(select(MemoryRecord))).all())
    assert first is not None and duplicate is not None
    assert first.id == duplicate.id
    assert len(records) == 1
    assert records[0].source_system == "operator"
    assert records[0].successful_use_count == 1
    assert "operator-correction" in records[0].tags


@pytest.mark.asyncio
async def test_researched_solution_is_saved_with_source_provenance(self_learning_sessions):
    record = await capture_researched_solution(
        agent_id=uuid.uuid4(),
        question="How should this API be configured?",
        solution="Set the verified configuration value to 22.",
        tool_messages=[
            {
                "role": "tool",
                "content": "Official documentation: https://example.com/reference/topic",
            }
        ],
    )

    assert record is not None
    assert record.memory_type == "procedural"
    assert record.source_type == "web_research"
    assert record.source_system == "mado"
    assert "https://example.com/reference/topic" in record.content
