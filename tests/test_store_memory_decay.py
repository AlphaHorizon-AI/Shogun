from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.config import settings
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.memory_salience import compute_decayed_relevance
from shogun.schemas.memory import MemoryRecordCreate
from shogun.services import memory_service
from shogun.services.event_logger import EventLogger
from shogun.services.memory_governance import ALLOWED_DECAY_TYPES, MemoryDecayError, validate_decay_type
from shogun.services.native_skills import NATIVE_TOOLS, execute_native_tool


class _VectorStore:
    def upsert(self, **_kwargs):
        return None

    def search(self, **_kwargs):
        return []


@pytest.fixture
async def memory_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    monkeypatch.setattr(memory_service, "get_vector_store", lambda: _VectorStore())
    audit = AsyncMock(return_value="evt_test")
    monkeypatch.setattr(EventLogger, "emit", audit)

    async with sessions() as session:
        agent = Agent(
            id=uuid.uuid4(),
            agent_type="shogun",
            name="Max",
            slug="max",
            status="active",
            is_primary=True,
        )
        session.add(agent)
        await session.commit()
        yield session, agent, audit

    await engine.dispose()


def _store_memory_tool() -> dict:
    return next(tool for tool in NATIVE_TOOLS if tool["function"]["name"] == "store_memory")


def test_store_memory_schema_exposes_canonical_optional_decay_type():
    parameters = _store_memory_tool()["function"]["parameters"]

    assert parameters["properties"]["decay_type"]["enum"] == list(ALLOWED_DECAY_TYPES)
    assert "decay_type" not in parameters["required"]
    assert parameters["properties"]["tags"]["type"] == "array"


def test_decay_validation_rejects_invalid_and_accepts_null():
    assert validate_decay_type(None) is None
    assert validate_decay_type("sticky") == "sticky"
    with pytest.raises(MemoryDecayError) as exc_info:
        validate_decay_type("forever")
    assert exc_info.value.allowed_values == ALLOWED_DECAY_TYPES


def test_memory_api_schema_accepts_decay_type_alias():
    body = MemoryRecordCreate.model_validate({
        "agent_id": str(uuid.uuid4()),
        "memory_type": "semantic",
        "title": "API sticky",
        "content": "Stored through the memory API.",
        "importance_score": 0.9,
        "decay_type": "sticky",
    })

    assert body.decay_class.value == "sticky"
    assert body.model_dump()["decay_class"].value == "sticky"


@pytest.mark.asyncio
async def test_explicit_sticky_is_persisted_and_audited(memory_context):
    session, agent, audit = memory_context
    result = json.loads(await execute_native_tool("store_memory", {
        "title": "Communication preference",
        "content": "Use direct and precise feedback.",
        "memory_type": "persona",
        "importance": 0.9,
        "decay_type": "sticky",
        "tags": ["preference", "communication"],
    }, session))

    record = await session.get(MemoryRecord, uuid.UUID(result["memory_id"]))
    assert result["status"] == "success"
    assert result["decay_type"] == "sticky"
    assert record is not None
    assert record.decay_class == "sticky"
    assert record.is_pinned is False
    assert record.tags == ["preference", "communication"]
    stored_event = next(call for call in audit.await_args_list if call.kwargs["event_type"] == "memory.stored")
    assert stored_event.kwargs["detail"]["decay_type"] == "sticky"
    assert stored_event.kwargs["agent_id"] == str(agent.id)


@pytest.mark.asyncio
async def test_omitted_and_null_decay_keep_historical_defaults(memory_context):
    session, _agent, _audit = memory_context
    base = {
        "content": "Durable fact",
        "memory_type": "semantic",
        "importance": 0.9,
    }
    omitted = json.loads(await execute_native_tool(
        "store_memory", {**base, "title": "Omitted decay"}, session
    ))
    explicit_null = json.loads(await execute_native_tool(
        "store_memory", {**base, "title": "Null decay", "decay_type": None}, session
    ))

    assert omitted["decay_type"] == "pinned"
    assert explicit_null["decay_type"] == "pinned"


@pytest.mark.asyncio
async def test_explicit_decay_overrides_auto_pin_and_invalid_value_is_rejected(memory_context):
    session, _agent, audit = memory_context
    explicit = json.loads(await execute_native_tool("store_memory", {
        "title": "Explicit slow",
        "content": "Important but intentionally decaying.",
        "memory_type": "semantic",
        "importance": 0.95,
        "decay_type": "slow",
    }, session))
    invalid = json.loads(await execute_native_tool("store_memory", {
        "title": "Invalid",
        "content": "Unsupported decay.",
        "memory_type": "semantic",
        "importance": 0.9,
        "decay_type": "forever",
    }, session))

    explicit_record = await session.get(MemoryRecord, uuid.UUID(explicit["memory_id"]))
    assert explicit_record.decay_class == "slow"
    assert explicit_record.is_pinned is False
    assert invalid["error"] == "invalid_decay_type"
    assert invalid["allowed_values"] == list(ALLOWED_DECAY_TYPES)
    assert any(call.kwargs["event_type"] == "memory.decay_type.invalid" for call in audit.await_args_list)


@pytest.mark.asyncio
async def test_sticky_policy_rejects_low_importance(memory_context, monkeypatch):
    session, _agent, audit = memory_context
    monkeypatch.setattr(settings, "memory_sticky_requires_min_importance", 0.7)

    result = json.loads(await execute_native_tool("store_memory", {
        "title": "Temporary note",
        "content": "This should not become sticky.",
        "memory_type": "episodic",
        "importance": 0.4,
        "decay_type": "sticky",
    }, session))

    records = list((await session.execute(select(MemoryRecord))).scalars())
    assert result["error"] == "sticky_memory_importance_too_low"
    assert records == []
    assert any(call.kwargs["event_type"] == "memory.sticky.rejected" for call in audit.await_args_list)


def test_sticky_memory_does_not_decay():
    now = datetime.now(timezone.utc)
    assert compute_decayed_relevance(
        current_relevance=0.9,
        decay_class="sticky",
        last_confirmed_at=now - timedelta(days=365),
        is_pinned=False,
        now=now,
    ) == 0.9


@pytest.mark.asyncio
async def test_sticky_retrieval_respects_agent_scope_cap_and_emits_debug_event(
    memory_context, monkeypatch
):
    session, agent, audit = memory_context
    monkeypatch.setattr(settings, "memory_max_sticky_memories_in_context", 1)
    other_agent_id = uuid.uuid4()
    session.add_all([
        MemoryRecord(
            agent_id=agent.id,
            memory_type="semantic",
            title="Highest scoped sticky",
            content="Persistent scoped fact",
            importance_score=0.95,
            relevance_score=0.8,
            confidence_score=0.9,
            decay_class="sticky",
        ),
        MemoryRecord(
            agent_id=agent.id,
            memory_type="semantic",
            title="Lower scoped sticky",
            content="Second persistent scoped fact",
            importance_score=0.8,
            relevance_score=0.8,
            confidence_score=0.9,
            decay_class="sticky",
        ),
        MemoryRecord(
            agent_id=other_agent_id,
            memory_type="semantic",
            title="Other agent sticky",
            content="Must not cross agent scope",
            importance_score=1.0,
            relevance_score=1.0,
            confidence_score=1.0,
            decay_class="sticky",
        ),
    ])
    await session.commit()

    results = await memory_service.MemoryService(session).search(
        "unrelated semantic query",
        agent_id=agent.id,
        limit=10,
    )

    assert [item["title"] for item in results] == ["Highest scoped sticky"]
    event = next(
        call for call in audit.await_args_list
        if call.kwargs["event_type"] == "memory.retrieval.sticky_injected"
    )
    assert event.kwargs["detail"]["sticky_considered"] == 1
    assert event.kwargs["detail"]["sticky_injected"] == 1


@pytest.mark.asyncio
async def test_sticky_retrieval_respects_token_budget(memory_context, monkeypatch):
    session, agent, audit = memory_context
    monkeypatch.setattr(settings, "memory_max_sticky_context_tokens", 10)
    session.add(MemoryRecord(
        agent_id=agent.id,
        memory_type="semantic",
        title="Oversized sticky memory",
        content="x" * 200,
        importance_score=1.0,
        relevance_score=1.0,
        confidence_score=1.0,
        decay_class="sticky",
    ))
    await session.commit()

    results = await memory_service.MemoryService(session).search(
        "anything",
        agent_id=agent.id,
        limit=10,
    )

    assert results == []
    event = next(
        call for call in audit.await_args_list
        if call.kwargs["event_type"] == "memory.retrieval.sticky_injected"
    )
    assert event.kwargs["detail"]["sticky_injected"] == 0
    assert event.kwargs["detail"]["sticky_skipped_token_budget"] == 1
