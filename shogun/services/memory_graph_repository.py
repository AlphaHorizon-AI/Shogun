"""SQLAlchemy repository boundary for the portable MemoryGraph backend."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_graph import MemoryGraphConflict, MemoryGraphEdge, MemoryGraphNode


class MemoryGraphRepository:
    """Relational graph repository; replaceable by a dedicated backend later."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def node(self, node_id: uuid.UUID) -> MemoryGraphNode | None:
        return await self.session.get(MemoryGraphNode, node_id)

    async def node_by_key(self, canonical_key: str) -> MemoryGraphNode | None:
        result = await self.session.execute(
            select(MemoryGraphNode).where(MemoryGraphNode.canonical_key == canonical_key)
        )
        return result.scalars().first()

    async def nodes(
        self,
        *,
        node_type: str | None = None,
        status: str | None = "active",
        tenant_id: str = "local",
        workspace_id: str | None = None,
        project_id: str | None = None,
        agent_id: uuid.UUID | None = None,
        query: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[MemoryGraphNode], int]:
        predicates: list[Any] = [MemoryGraphNode.tenant_id == tenant_id]
        if node_type:
            predicates.append(MemoryGraphNode.node_type == node_type)
        if status:
            predicates.append(MemoryGraphNode.status == status)
        if workspace_id:
            predicates.append(MemoryGraphNode.workspace_id == workspace_id)
        if project_id:
            predicates.append(MemoryGraphNode.project_id == project_id)
        if agent_id:
            predicates.append(MemoryGraphNode.agent_id == agent_id)
        if query:
            pattern = f"%{query.strip()}%"
            predicates.append(
                or_(MemoryGraphNode.name.ilike(pattern), MemoryGraphNode.display_name.ilike(pattern))
            )
        count = await self.session.scalar(select(func.count()).select_from(MemoryGraphNode).where(*predicates))
        result = await self.session.execute(
            select(MemoryGraphNode)
            .where(*predicates)
            .order_by(MemoryGraphNode.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all(), int(count or 0)

    async def edges(
        self,
        *,
        node_id: uuid.UUID | None = None,
        relationship_type: str | None = None,
        status: str = "active",
        limit: int = 500,
    ) -> Sequence[MemoryGraphEdge]:
        predicates: list[Any] = [MemoryGraphEdge.status == status]
        if node_id:
            predicates.append(
                or_(MemoryGraphEdge.from_node_id == node_id, MemoryGraphEdge.to_node_id == node_id)
            )
        if relationship_type:
            predicates.append(MemoryGraphEdge.relationship_type == relationship_type)
        result = await self.session.execute(
            select(MemoryGraphEdge)
            .where(*predicates)
            .order_by(MemoryGraphEdge.updated_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def edge_by_relation(
        self, from_node_id: uuid.UUID, to_node_id: uuid.UUID, relationship_type: str
    ) -> MemoryGraphEdge | None:
        result = await self.session.execute(
            select(MemoryGraphEdge).where(
                MemoryGraphEdge.from_node_id == from_node_id,
                MemoryGraphEdge.to_node_id == to_node_id,
                MemoryGraphEdge.relationship_type == relationship_type,
            )
        )
        return result.scalars().first()

    async def conflict(self, conflict_id: uuid.UUID) -> MemoryGraphConflict | None:
        return await self.session.get(MemoryGraphConflict, conflict_id)

    async def conflicts(
        self, *, resolution_status: str | None = "needs_review", limit: int = 100
    ) -> Sequence[MemoryGraphConflict]:
        query = select(MemoryGraphConflict)
        if resolution_status:
            query = query.where(MemoryGraphConflict.resolution_status == resolution_status)
        result = await self.session.execute(
            query.order_by(MemoryGraphConflict.created_at.desc()).limit(limit)
        )
        return result.scalars().all()
