from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.config import settings
from shogun.db.models.memory_graph import MemoryGraphConflict, MemoryGraphEdge, MemoryGraphNode
from shogun.db.models.memory_record import MemoryRecord
from shogun.schemas.memory_graph import MemoryGraphEdgeCreate, MemoryGraphNodeCreate
from shogun.services import memory_graph_service, memory_service
from shogun.services.memory_graph_service import MemoryGraphService
from shogun.services.memory_service import MemoryService


class _GraphVectorStore:
    def __init__(self):
        self.upserts: list[dict] = []
        self.payload_updates: list[dict] = []

    def upsert(self, **kwargs):
        self.upserts.append(kwargs)

    def set_payload(self, **kwargs):
        self.payload_updates.append(kwargs)


@pytest.fixture
async def graph_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(MemoryRecord.__table__.create)
        await connection.run_sync(MemoryGraphNode.__table__.create)
        await connection.run_sync(MemoryGraphEdge.__table__.create)
        await connection.run_sync(MemoryGraphConflict.__table__.create)

    vector = _GraphVectorStore()
    monkeypatch.setattr(memory_graph_service, "get_vector_store", lambda: vector)
    monkeypatch.setattr(memory_service, "get_vector_store", lambda: vector)

    async with sessions() as session:
        yield session, vector
    await engine.dispose()


def _memory(agent_id: uuid.UUID, title: str, project_id: str) -> MemoryRecord:
    return MemoryRecord(
        agent_id=agent_id,
        memory_type="semantic",
        title=title,
        content=f"Content for {title}",
        project_id=project_id,
        workspace_id="shogun",
        qdrant_point_id=str(uuid.uuid4()),
        scope_status="classified",
    )


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_preserves_memory_ids(graph_context):
    session, vector = graph_context
    agent_id = uuid.uuid4()
    first = _memory(agent_id, "Alpha decision", "alpha")
    second = _memory(agent_id, "Beta decision", "beta")
    session.add_all([first, second])
    await session.flush()

    service = MemoryGraphService(session)
    result = await service.backfill(limit=100)

    assert result.scanned == 2
    assert result.memory_nodes_created == 2
    assert result.scope_nodes_created == 4  # one agent, one workspace, two projects
    assert result.edges_created == 6
    assert result.complete is True
    assert await session.get(MemoryRecord, first.id) is first

    first_node = await service.repository.node(first.id)
    assert first_node is not None
    assert first_node.source_memory_id == first.id
    assert first_node.project_id == "alpha"
    assert first_node.payload_json["memory_type"] == "semantic"
    linked_ids = {item["payload"]["graph_node_id"] for item in vector.payload_updates}
    assert linked_ids == {str(first.id), str(second.id)}

    repeated = await service.backfill(limit=100)
    assert repeated.memory_nodes_created == 0
    assert repeated.scope_nodes_created == 0
    assert repeated.edges_created == 0


@pytest.mark.asyncio
async def test_conflict_resolution_supersedes_without_deleting_history(graph_context):
    session, _vector = graph_context
    agent_id = uuid.uuid4()
    old = _memory(agent_id, "Old Teams fact", "shogun")
    new = _memory(agent_id, "New Teams fact", "shogun")
    session.add_all([old, new])
    await session.flush()

    service = MemoryGraphService(session)
    conflict = await service.create_conflict(old.id, new.id)
    assert conflict.resolution_status == "needs_review"
    assert (await service.repository.node(old.id)).status == "conflicting"
    assert (await service.repository.node(new.id)).status == "conflicting"

    resolved = await service.resolve_conflict(
        conflict.id,
        resolution_status="resolved",
        resolved_by="operator",
        resolution_note="The newer Teams support statement is authoritative.",
        superseding_memory_id=new.id,
    )
    assert resolved is not None
    assert resolved.resolved_at is not None
    assert (await service.repository.node(old.id)).status == "superseded"
    assert (await service.repository.node(new.id)).status == "active"
    assert await session.get(MemoryRecord, old.id) is old
    supersedes = await service.repository.edge_by_relation(new.id, old.id, "supersedes")
    assert supersedes is not None


@pytest.mark.asyncio
async def test_graph_rejects_cross_tenant_edges(graph_context):
    session, _vector = graph_context
    service = MemoryGraphService(session)
    local = await service.create_node(
        MemoryGraphNodeCreate(node_type="project", name="Local project")
    )
    external = await service.create_node(
        MemoryGraphNodeCreate(
            node_type="project",
            name="External project",
            scope={"tenant_id": "external"},
        )
    )

    with pytest.raises(ValueError, match="Cross-tenant"):
        await service.create_edge(
            MemoryGraphEdgeCreate(
                from_node_id=local.id,
                to_node_id=external.id,
                relationship_type="related_to",
            )
        )


@pytest.mark.asyncio
async def test_dual_write_links_new_memory_when_enabled(graph_context, monkeypatch):
    session, vector = graph_context
    monkeypatch.setattr(settings, "memory_graph_write_mode", "dual")

    memory = await MemoryService(session).create_memory(
        memory_type="semantic",
        agent_id=uuid.uuid4(),
        title="Graph-linked decision",
        content="New memories can enter both stores during controlled rollout.",
        scope={"workspace_id": "shogun", "project_id": "phase-two"},
    )

    node = await session.scalar(
        select(MemoryGraphNode).where(MemoryGraphNode.source_memory_id == memory.id)
    )
    assert node is not None
    assert node.id == memory.id
    assert vector.upserts[0]["payload"]["graph_node_id"] == str(memory.id)
    assert vector.upserts[0]["payload"]["graph_status"] == "active"
    assert vector.payload_updates[-1]["payload"]["graph_status"] == "active"


def test_memory_graph_routes_are_registered():
    from shogun.app import create_app

    paths = {route.path for route in create_app().routes}
    assert "/api/v1/memory-graph/nodes" in paths
    assert "/api/v1/memory-graph/edges" in paths
    assert "/api/v1/memory-graph/backfill" in paths
    assert "/api/v1/memory-graph/conflicts/{conflict_id}/resolve" in paths
