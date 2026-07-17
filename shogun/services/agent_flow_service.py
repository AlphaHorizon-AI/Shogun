"""Agent Flow service — CRUD + bulk graph save for workflows."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.services.base_service import BaseService

log = logging.getLogger(__name__)


class AgentFlowService(BaseService[AgentFlow]):
    """Service for Agent Flow CRUD and graph operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(AgentFlow, session)

    # ── List flows (lightweight, no nodes/edges) ─────────────

    async def list_flows(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
        include_templates: bool = False,
    ) -> tuple[Sequence[AgentFlow], int]:
        """List flows with optional status/search filter, excluding soft-deleted."""
        from sqlalchemy import or_

        filters = [AgentFlow.is_deleted == False]
        if not include_templates:
            filters.append(AgentFlow.is_template == False)
        if status:
            filters.append(AgentFlow.status == status)
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    AgentFlow.name.ilike(pattern),
                    AgentFlow.description.ilike(pattern),
                )
            )
        return await self.get_all(offset=offset, limit=limit, filters=filters)

    async def list_saved_templates(
        self, *, flow_type: str | None = None, limit: int = 500,
    ) -> Sequence[AgentFlow]:
        filters = [AgentFlow.is_deleted == False, AgentFlow.is_template == True]
        if flow_type:
            filters.append(AgentFlow.flow_type == flow_type)
        items, _ = await self.get_all(offset=0, limit=limit, filters=filters)
        return items

    # ── Get full flow with nodes and edges ───────────────────

    async def get_flow_full(self, flow_id: uuid.UUID) -> AgentFlow | None:
        """Load a flow with all nodes and edges eagerly."""
        result = await self.session.execute(
            select(AgentFlow)
            .where(AgentFlow.id == flow_id, AgentFlow.is_deleted == False)
            .options(
                selectinload(AgentFlow.nodes),
                selectinload(AgentFlow.edges),
            )
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    # ── Bulk graph save (atomic replace) ─────────────────────

    async def save_flow_graph(
        self,
        flow_id: uuid.UUID,
        nodes_data: list[dict[str, Any]],
        edges_data: list[dict[str, Any]],
        viewport: dict[str, Any] | None = None,
    ) -> AgentFlow | None:
        """Atomically replace all nodes and edges for a flow.

        This is the main "Save" operation from the canvas frontend.
        It deletes existing nodes/edges and recreates them from the payload.
        """
        flow = await self.get_flow_full(flow_id)
        if flow is None:
            return None

        # Build a mapping from client-side IDs to persisted UUIDs. Existing
        # React Flow UUIDs must remain stable so live run states can map back
        # to the cards currently rendered on the canvas.
        node_id_map: dict[str, uuid.UUID] = {}
        used_node_ids: set[uuid.UUID] = set()

        # Delete existing nodes and edges (cascade handles edges via FK)
        for edge in list(flow.edges):
            await self.session.delete(edge)
        for node in list(flow.nodes):
            await self.session.delete(node)
        await self.session.flush()

        # Create new nodes
        new_nodes: list[AgentFlowNode] = []
        for nd in nodes_data:
            client_id = nd.get("id") or str(uuid.uuid4())
            try:
                new_id = uuid.UUID(str(client_id))
            except (ValueError, TypeError, AttributeError):
                new_id = uuid.uuid4()
            if new_id in used_node_ids:
                new_id = uuid.uuid4()
            used_node_ids.add(new_id)
            node_id_map[client_id] = new_id

            node = AgentFlowNode(
                id=new_id,
                flow_id=flow_id,
                node_type=nd.get("node_type", "samurai"),
                label=nd.get("label", "Untitled"),
                position_x=nd.get("position_x", 0.0),
                position_y=nd.get("position_y", 0.0),
                config=nd.get("config", {}),
            )
            self.session.add(node)
            new_nodes.append(node)

        await self.session.flush()

        # Create new edges (resolve client IDs to actual UUIDs)
        for ed in edges_data:
            source_client_id = ed.get("source_node_id", "")
            target_client_id = ed.get("target_node_id", "")

            source_uuid = node_id_map.get(source_client_id)
            target_uuid = node_id_map.get(target_client_id)

            if source_uuid is None or target_uuid is None:
                log.warning(
                    "Skipping edge with unresolved node IDs: source=%s target=%s",
                    source_client_id, target_client_id,
                )
                continue

            edge_client_id = ed.get("id")
            try:
                edge_id = uuid.UUID(str(edge_client_id))
            except (ValueError, TypeError, AttributeError):
                edge_id = uuid.uuid4()

            edge = AgentFlowEdge(
                id=edge_id,
                flow_id=flow_id,
                source_node_id=source_uuid,
                target_node_id=target_uuid,
                source_handle=ed.get("source_handle"),
                target_handle=ed.get("target_handle"),
                label=ed.get("label"),
                edge_type=ed.get("edge_type", "default"),
                config=ed.get("config", {}),
            )
            self.session.add(edge)

        # Update viewport if provided
        if viewport:
            flow.viewport = viewport
        flow.version = int(flow.version or 1) + 1

        await self.session.flush()

        # Reload the full flow
        return await self.get_flow_full(flow_id)

    # ── Duplicate a flow ─────────────────────────────────────

    async def duplicate_flow(self, flow_id: uuid.UUID) -> AgentFlow | None:
        """Deep-copy a flow including all nodes and edges."""
        source = await self.get_flow_full(flow_id)
        if source is None:
            return None

        # Create new flow
        new_flow = AgentFlow(
            name=f"{source.name} (Copy)",
            description=source.description,
            status="draft",
            trigger_type=source.trigger_type,
            schedule_config=source.schedule_config,
            viewport=source.viewport,
            version=1,
            flow_type=source.flow_type,
            input_contract=source.input_contract,
            output_contract=source.output_contract,
            risk_tier=source.risk_tier,
            default_timeout_seconds=source.default_timeout_seconds,
            allow_as_subflow=source.allow_as_subflow,
            required_tools=source.required_tools,
            is_template=False,
            template_category=None,
            template_source=None,
            template_config={},
        )
        self.session.add(new_flow)
        await self.session.flush()

        # Copy nodes with ID mapping
        node_id_map: dict[uuid.UUID, uuid.UUID] = {}
        for node in source.nodes:
            new_node_id = uuid.uuid4()
            node_id_map[node.id] = new_node_id
            new_node = AgentFlowNode(
                id=new_node_id,
                flow_id=new_flow.id,
                node_type=node.node_type,
                label=node.label,
                position_x=node.position_x,
                position_y=node.position_y,
                config=node.config,
            )
            self.session.add(new_node)

        await self.session.flush()

        # Copy edges
        for edge in source.edges:
            new_source = node_id_map.get(edge.source_node_id)
            new_target = node_id_map.get(edge.target_node_id)
            if new_source and new_target:
                new_edge = AgentFlowEdge(
                    flow_id=new_flow.id,
                    source_node_id=new_source,
                    target_node_id=new_target,
                    source_handle=edge.source_handle,
                    target_handle=edge.target_handle,
                    label=edge.label,
                    edge_type=edge.edge_type,
                    config=edge.config,
                )
                self.session.add(new_edge)

        await self.session.flush()
        return await self.get_flow_full(new_flow.id)

    # ── Status management ────────────────────────────────────

    async def update_status(self, flow_id: uuid.UUID, status: str) -> AgentFlow | None:
        """Update flow status (draft, active, paused, archived)."""
        flow = await self.get_by_id(flow_id)
        if flow is None or flow.is_deleted:
            return None
        flow.status = status
        await self.session.flush()
        await self.session.refresh(flow)
        return flow
