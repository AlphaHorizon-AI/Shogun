from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.config import settings
from shogun.db.models.memory_context_pack import MemoryContextPack
from shogun.db.models.memory_graph import MemoryGraphConflict, MemoryGraphEdge, MemoryGraphNode
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.memory_retrieval import MemoryRetrievalRun
from shogun.schemas.memory import MemoryScopeEnvelope
from shogun.schemas.memory_graph import MemoryGraphEdgeCreate
from shogun.services import memory_service, retrieval_verifier
from shogun.services.cascade_retrieval import CascadeRetrievalService
from shogun.services.memory_context_pack_service import MemoryContextPackService
from shogun.services.memory_graph_service import MemoryGraphService


class _SeedOnlyVectorStore:
    def __init__(self, seed_id: uuid.UUID):
        self.seed_id = str(seed_id)

    def search(self, **kwargs):
        allowed = set(kwargs.get("allowed_memory_ids") or [])
        if self.seed_id not in allowed:
            return []
        return [{"memory_id": self.seed_id, "score": 0.92, "payload": {}}]


def _memory(agent_id: uuid.UUID, title: str, project_id: str, *, content: str | None = None):
    return MemoryRecord(
        agent_id=agent_id,
        memory_type="semantic",
        title=title,
        content=content or f"Context for {title}",
        project_id=project_id,
        workspace_id="shogun",
        scope_status="classified",
        relevance_score=0.8,
        importance_score=0.8,
        confidence_score=0.9,
    )


@pytest.fixture
async def phase3_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)
        await connection.run_sync(MemoryRetrievalRun.__table__.create)
        await connection.run_sync(MemoryGraphNode.__table__.create)
        await connection.run_sync(MemoryGraphEdge.__table__.create)
        await connection.run_sync(MemoryGraphConflict.__table__.create)
        await connection.run_sync(MemoryContextPack.__table__.create)

    agent_id = uuid.uuid4()
    other_agent_id = uuid.uuid4()
    seed = _memory(agent_id, "Vector seed", "alpha")
    related = _memory(agent_id, "Graph-related decision", "alpha")
    cross_scope = _memory(agent_id, "Beta secret", "beta")
    shared = _memory(other_agent_id, "Shared agent finding", "alpha")

    monkeypatch.setattr(settings, "memory_retrieval_mode", "cascade")
    monkeypatch.setattr(settings, "memory_graph_retrieval_mode", "active")
    monkeypatch.setattr(settings, "memory_graph_max_depth", 2)
    monkeypatch.setattr(settings, "memory_graph_shared_agent_reads_enabled", False)
    monkeypatch.setattr(settings, "memory_cascade_min_results", 5)
    monkeypatch.setattr(settings, "memory_context_pack_max_tokens", 2000)

    async with sessions() as session:
        session.add_all([seed, related, cross_scope, shared])
        await session.flush()
        graph = MemoryGraphService(session)
        for record in (seed, related, cross_scope, shared):
            await graph.ensure_memory_node(record, update_vector=False)
        await session.flush()
        monkeypatch.setattr(memory_service, "get_vector_store", lambda: _SeedOnlyVectorStore(seed.id))
        yield session, agent_id, seed, related, cross_scope, shared
    await engine.dispose()


@pytest.mark.asyncio
async def test_active_graph_retrieval_expands_verifies_and_builds_context_pack(phase3_context):
    session, agent_id, seed, related, cross_scope, _shared = phase3_context
    results, diagnostic = await CascadeRetrievalService(session).run(
        query="What is connected to this decision?",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    ids = {str(item["memory_id"]) for item in results}
    assert str(seed.id) in ids
    assert str(related.id) in ids
    assert str(cross_scope.id) not in ids
    assert diagnostic is not None
    pack_id = uuid.UUID(diagnostic.plan_json["context_pack_id"])
    pack = await session.get(MemoryContextPack, pack_id)
    assert pack is not None
    assert str(related.id) in pack.graph_expanded_memory_ids
    assert pack.token_estimate <= settings.memory_context_pack_max_tokens
    assert "Graph-related decision" in MemoryContextPackService.render_prompt_block(pack)
    assert any(stage["name"] == "verification_and_policy" for stage in diagnostic.stages_json)


@pytest.mark.asyncio
async def test_graph_shadow_previews_without_changing_vector_results(phase3_context, monkeypatch):
    session, agent_id, seed, related, _cross_scope, _shared = phase3_context
    monkeypatch.setattr(settings, "memory_graph_retrieval_mode", "shadow")

    results, diagnostic = await CascadeRetrievalService(session).run(
        query="decision",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    assert {str(item["memory_id"]) for item in results} == {str(seed.id)}
    assert diagnostic is not None
    assert str(related.id) in diagnostic.plan_json["graph_shadow_result_memory_ids"]


@pytest.mark.asyncio
async def test_conflicting_graph_memory_is_withheld(phase3_context):
    session, agent_id, _seed, related, _cross_scope, _shared = phase3_context
    related_node = await session.get(MemoryGraphNode, related.id)
    related_node.status = "conflicting"
    await session.flush()

    results, diagnostic = await CascadeRetrievalService(session).run(
        query="decision",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    assert str(related.id) not in {str(item["memory_id"]) for item in results}
    assert diagnostic is not None
    assert any(
        item.get("memory_id") == str(related.id) and item["reason"] == "graph_status_conflicting"
        for item in diagnostic.excluded_json
    )


@pytest.mark.asyncio
async def test_graph_edge_cannot_bypass_project_authorization(phase3_context):
    session, agent_id, seed, _related, cross_scope, _shared = phase3_context
    await MemoryGraphService(session).create_edge(
        MemoryGraphEdgeCreate(
            from_node_id=seed.id,
            to_node_id=cross_scope.id,
            relationship_type="related_to",
        )
    )

    results, diagnostic = await CascadeRetrievalService(session).run(
        query="secret",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    assert str(cross_scope.id) not in {str(item["memory_id"]) for item in results}
    assert diagnostic is not None
    assert any(
        item.get("memory_id") == str(cross_scope.id)
        and item["reason"] == "scope_or_sensitivity_not_authorized"
        for item in diagnostic.excluded_json
    )


@pytest.mark.asyncio
async def test_cross_agent_graph_memory_requires_explicit_shared_read_flag(phase3_context, monkeypatch):
    session, agent_id, _seed, _related, _cross_scope, shared = phase3_context
    scope = MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha")

    private_results, _ = await CascadeRetrievalService(session).run(
        query="finding", agent_id=agent_id, scope=scope, mode="cascade", limit=10
    )
    assert str(shared.id) not in {str(item["memory_id"]) for item in private_results}

    monkeypatch.setattr(settings, "memory_graph_shared_agent_reads_enabled", True)
    shared_results, _ = await CascadeRetrievalService(session).run(
        query="finding", agent_id=agent_id, scope=scope, mode="cascade", limit=10
    )
    assert str(shared.id) in {str(item["memory_id"]) for item in shared_results}


@pytest.mark.asyncio
async def test_toolgate_content_policy_can_veto_graph_injection(phase3_context, monkeypatch):
    session, agent_id, _seed, related, _cross_scope, _shared = phase3_context

    def policy(_tool_name, args, _local_scope="global"):
        if "Graph-related" in args["title"]:
            return SimpleNamespace(value="block"), "Blocked by test policy", ["policy:test"]
        return None, None, []

    monkeypatch.setattr(retrieval_verifier, "evaluate_advanced_controls", policy)
    results, diagnostic = await CascadeRetrievalService(session).run(
        query="decision",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    assert str(related.id) not in {str(item["memory_id"]) for item in results}
    assert diagnostic is not None
    assert any(item.get("reason") == "gensui_policy_block" for item in diagnostic.excluded_json)


@pytest.mark.asyncio
async def test_gensui_memory_read_denial_is_fail_closed(phase3_context, monkeypatch):
    session, agent_id, _seed, _related, _cross_scope, _shared = phase3_context

    async def blocked(_action, _context):
        raise HTTPException(status_code=403, detail="Memory reads blocked by posture")

    monkeypatch.setattr("shogun.services.gensui_policy_guard.check_gensui_policy", blocked)
    results, diagnostic = await CascadeRetrievalService(session).run(
        query="decision",
        agent_id=agent_id,
        scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
        mode="cascade",
        limit=10,
    )

    assert results == []
    assert diagnostic is not None
    assert any(item.get("reason") == "gensui_memory_read_blocked" for item in diagnostic.excluded_json)


@pytest.mark.asyncio
async def test_missing_graph_tables_fall_back_to_scoped_vector_results(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)
        await connection.run_sync(MemoryRetrievalRun.__table__.create)
    seed = _memory(uuid.uuid4(), "Safe fallback seed", "alpha")
    monkeypatch.setattr(settings, "memory_graph_retrieval_mode", "active")
    monkeypatch.setattr(settings, "memory_cascade_min_results", 1)
    monkeypatch.setattr(memory_service, "get_vector_store", lambda: _SeedOnlyVectorStore(seed.id))
    async with sessions() as session:
        session.add(seed)
        await session.flush()
        results, diagnostic = await CascadeRetrievalService(session).run(
            query="fallback",
            agent_id=seed.agent_id,
            scope=MemoryScopeEnvelope(workspace_id="shogun", project_id="alpha"),
            mode="cascade",
            limit=5,
        )
        assert {str(item["memory_id"]) for item in results} == {str(seed.id)}
        assert diagnostic is not None
        assert diagnostic.plan_json["graph_fallback"] == "scoped_vector_results"
    await engine.dispose()


def test_phase3_context_pack_routes_are_registered():
    from shogun.app import create_app

    paths = {route.path for route in create_app().routes}
    assert "/api/v1/memory/context-packs/{pack_id}" in paths
    assert "/api/v1/memory/context-packs/by-correlation/{correlation_id}" in paths
