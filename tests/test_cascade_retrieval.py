from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from qdrant_client.http.models import FieldCondition, Filter, HasIdCondition
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.config import settings
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.memory_retrieval import MemoryRetrievalRun
from shogun.engine.vector_store import VectorStore
from shogun.schemas.memory import MemoryScopeEnvelope
from shogun.services import memory_service
from shogun.services.cascade_retrieval import CascadeRetrievalService
from shogun.services.memory_routing_context import memory_routing_scope
from shogun.services.memory_scope import resolve_active_memory_scope
from shogun.services.memory_service import MemoryService
from shogun.services.telegram_routing_context import telegram_routing_scope


class _ScopedVectorStore:
    def __init__(self, records: list[MemoryRecord]):
        self.records = records
        self.calls: list[dict] = []

    def upsert(self, **_kwargs):
        return None

    def search(self, **kwargs):
        self.calls.append(kwargs)
        allowed = kwargs.get("allowed_memory_ids")
        allowed_set = set(allowed) if allowed is not None else None
        memory_types = set(kwargs.get("memory_types") or [])
        agent_id = kwargs.get("agent_id")
        hits = []
        for index, record in enumerate(self.records):
            if allowed_set is not None and str(record.id) not in allowed_set:
                continue
            if agent_id and str(record.agent_id) != agent_id:
                continue
            if memory_types and record.memory_type not in memory_types:
                continue
            hits.append({"memory_id": str(record.id), "score": 0.95 - index * 0.01, "payload": {}})
        return hits[: kwargs.get("limit", 20)]


@pytest.fixture
async def cascade_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)
        await connection.run_sync(MemoryRetrievalRun.__table__.create)

    agent_id = uuid.uuid4()
    other_agent_id = uuid.uuid4()
    records = [
        MemoryRecord(
            agent_id=agent_id,
            memory_type="semantic",
            title="Project Alpha decision",
            content="Alpha uses the governed cascade.",
            project_id="alpha",
            scope_status="classified",
        ),
        MemoryRecord(
            agent_id=agent_id,
            memory_type="semantic",
            title="Project Beta decision",
            content="Beta must never leak into Alpha.",
            project_id="beta",
            scope_status="classified",
        ),
        MemoryRecord(
            agent_id=agent_id,
            memory_type="semantic",
            title="Legacy agent preference",
            content="Use concise answers.",
        ),
        MemoryRecord(
            agent_id=agent_id,
            memory_type="semantic",
            title="Restricted Alpha secret",
            content="Restricted content.",
            project_id="alpha",
            sensitivity="restricted",
            scope_status="classified",
        ),
        MemoryRecord(
            agent_id=other_agent_id,
            memory_type="semantic",
            title="Other agent Alpha memory",
            content="Another agent's private memory.",
            project_id="alpha",
            scope_status="classified",
        ),
    ]
    vector = _ScopedVectorStore(records)
    monkeypatch.setattr(memory_service, "get_vector_store", lambda: vector)
    monkeypatch.setattr(settings, "memory_cascade_min_results", 5)
    monkeypatch.setattr(settings, "memory_cascade_diagnostics_enabled", True)

    async with sessions() as session:
        session.add_all(records)
        await session.commit()
        yield session, agent_id, records, vector
    await engine.dispose()


@pytest.mark.asyncio
async def test_cascade_pre_authorizes_ids_and_blocks_cross_scope_memory(cascade_context):
    session, agent_id, records, vector = cascade_context
    results, diagnostic = await CascadeRetrievalService(session).run(
        query="What did we decide?",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    titles = {item["title"] for item in results}
    assert "Project Alpha decision" in titles
    assert "Legacy agent preference" in titles
    assert "Project Beta decision" not in titles
    assert "Restricted Alpha secret" not in titles
    assert "Other agent Alpha memory" not in titles
    assert diagnostic is not None
    assert diagnostic.status == "completed"
    assert all(call["allowed_memory_ids"] is not None for call in vector.calls)
    assert str(records[1].id) not in {memory_id for call in vector.calls for memory_id in call["allowed_memory_ids"]}


@pytest.mark.asyncio
async def test_shadow_mode_keeps_legacy_results_and_records_cascade_difference(cascade_context):
    session, agent_id, records, _vector = cascade_context
    results, diagnostic = await CascadeRetrievalService(session).run(
        query="decision",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(project_id="alpha"),
        mode="shadow",
        limit=10,
    )

    assert "Project Beta decision" in {item["title"] for item in results}
    assert diagnostic is not None
    excluded_ids = {item["memory_id"] for item in diagnostic.excluded_json}
    assert str(records[1].id) in excluded_ids
    assert diagnostic.query_hash
    assert "decision" not in diagnostic.query_hash


@pytest.mark.asyncio
async def test_new_memory_inherits_active_connector_scope(cascade_context):
    session, agent_id, _records, _vector = cascade_context
    with telegram_routing_scope(
        {"chat_id": "-100555", "chat_type": "private", "message_thread_id": 73, "sender_id": "22"}
    ):
        record = await MemoryService(session).create_memory(
            agent_id=agent_id,
            memory_type="semantic",
            title="Scoped topic decision",
            content="This belongs only to the active topic.",
        )

    assert record.tenant_id == "local"
    assert record.user_id == "telegram:22"
    assert record.conversation_provider == "telegram"
    assert record.conversation_id == "-100555"
    assert record.topic_id == "73"
    assert record.scope_status == "classified"


def test_vector_filter_keeps_type_or_nested_inside_mandatory_conditions():
    captured = {}
    store = VectorStore()
    store.embed = lambda _text: [0.0] * 384
    store._client = SimpleNamespace(
        query_points=lambda **kwargs: captured.update(kwargs) or SimpleNamespace(points=[])
    )

    store.search(
        "query",
        memory_types=["semantic", "procedural"],
        agent_id=str(uuid.uuid4()),
        allowed_memory_ids=[str(uuid.uuid4())],
    )

    query_filter = captured["query_filter"]
    assert query_filter.should is None
    assert any(isinstance(condition, Filter) and condition.should for condition in query_filter.must)
    assert any(isinstance(condition, FieldCondition) and condition.key == "agent_id" for condition in query_filter.must)
    assert any(isinstance(condition, HasIdCondition) for condition in query_filter.must)


def test_scope_envelope_requires_complete_conversation_identity():
    with pytest.raises(ValueError):
        MemoryScopeEnvelope(topic_id="42")
    with pytest.raises(ValueError):
        MemoryScopeEnvelope(conversation_id="chat-1")

    scope = MemoryScopeEnvelope(
        conversation_provider="telegram",
        conversation_id="-100123",
        topic_id="42",
    )
    assert scope.topic_id == "42"


def test_connector_context_resolves_without_cross_request_state():
    assert resolve_active_memory_scope().conversation_provider is None
    with telegram_routing_scope(
        {"chat_id": "-100123", "chat_type": "private", "message_thread_id": 42, "sender_id": "99"}
    ):
        scope = resolve_active_memory_scope()
        assert scope.conversation_provider == "telegram"
        assert scope.conversation_id == "-100123"
        assert scope.topic_id == "42"
        assert scope.user_id == "telegram:99"
    assert resolve_active_memory_scope().conversation_provider is None

    with telegram_routing_scope(
        {"chat_id": "-100999", "chat_type": "supergroup", "message_thread_id": 7, "sender_id": "44"}
    ):
        shared_scope = resolve_active_memory_scope()
        assert shared_scope.user_id is None
        assert shared_scope.conversation_id == "-100999"
        assert shared_scope.topic_id == "7"

    with memory_routing_scope(
        {
            "tenant_id": "tenant-a",
            "user_id": "microsoft_teams:user-a",
            "team_id": "team-a",
            "conversation_provider": "microsoft_teams",
            "conversation_id": "channel-a",
        }
    ):
        scope = resolve_active_memory_scope()
        assert scope.tenant_id == "tenant-a"
        assert scope.team_id == "team-a"
        assert scope.conversation_id == "channel-a"
    assert resolve_active_memory_scope().tenant_id == "local"
