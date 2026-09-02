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
        flow_type: str | None = None,
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
        if flow_type:
            filters.append(AgentFlow.flow_type == flow_type)
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
        """Load an included-edition AgentFlow with all nodes and edges eagerly.

        Flow Stack rows remain stored so moving an installation to White Label
        later does not lose its work, but Yellow Label never exposes them.
        """
        result = await self.session.execute(
            select(AgentFlow)
            .where(
                AgentFlow.id == flow_id,
                AgentFlow.is_deleted == False,
                AgentFlow.flow_type == "standard",
            )
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

        # Sync flow trigger & schedule_config from Input node if present
        input_node_data = next((nd for nd in nodes_data if nd.get("node_type") == "input"), None)
        if input_node_data:
            cfg = dict(input_node_data.get("config") or {})
            input_type = str(cfg.get("input_type") or "manual").lower()
            if input_type == "scheduled":
                flow.trigger_type = "scheduled"
                frequency = cfg.get("schedule_frequency") or cfg.get("frequency") or "nightly"
                sch_cfg = {
                    "frequency": frequency,
                    "schedule_time": cfg.get("schedule_time") or "07:00",
                }
                if frequency == "weekly":
                    sch_cfg["schedule_days"] = cfg.get("schedule_days") or ["mon", "tue", "wed", "thu", "fri"]
                elif frequency == "monthly":
                    sch_cfg["schedule_day"] = int(cfg.get("schedule_day") or 1)
                elif frequency == "hourly":
                    sch_cfg["minute_offset"] = int(cfg.get("minute_offset") or cfg.get("schedule_minute_offset") or 0)
                flow.schedule_config = sch_cfg
                if flow.status == "draft":
                    flow.status = "active"
            elif input_type in {"api", "event", "nexus"}:
                flow.trigger_type = input_type
            else:
                flow.trigger_type = "manual"

        # Update viewport if provided
        if viewport:
            flow.viewport = viewport
        flow.version = int(flow.version or 1) + 1

        await self.session.flush()

        # Reload the full flow
        return await self.get_flow_full(flow_id)

    async def patch_flow_graph(
        self,
        flow_id: uuid.UUID,
        node_operations: list[dict[str, Any]] | None = None,
        edge_operations: list[dict[str, Any]] | None = None,
    ) -> AgentFlow | None:
        """Apply targeted graph mutations while preserving untouched nodes and edges."""
        flow = await self.get_flow_full(flow_id)
        if flow is None:
            return None

        node_operations = node_operations or []
        edge_operations = edge_operations or []
        if not node_operations and not edge_operations:
            raise ValueError("At least one node or edge operation is required.")

        nodes = {str(node.id): node for node in flow.nodes}
        edges = {str(edge.id): edge for edge in flow.edges}

        def operation_id(payload: dict[str, Any], key: str) -> str:
            value = str(payload.get(key) or "").strip()
            if not value:
                raise ValueError(f"{key} is required for this graph operation.")
            return value

        for operation in node_operations:
            action = str(operation.get("op") or "").lower()
            if action == "add":
                raw_id = str(operation.get("node_id") or uuid.uuid4())
                try:
                    node_id = uuid.UUID(raw_id)
                except ValueError as exc:
                    raise ValueError("node_id must be a UUID when provided.") from exc
                if str(node_id) in nodes:
                    raise ValueError(f"Node {node_id} already exists.")
                node_type = str(operation.get("node_type") or "").strip()
                if not node_type:
                    raise ValueError("node_type is required when adding a node.")
                node = AgentFlowNode(
                    id=node_id,
                    flow_id=flow_id,
                    node_type=node_type,
                    label=str(operation.get("label") or "Untitled"),
                    position_x=float(operation.get("position_x", 0.0)),
                    position_y=float(operation.get("position_y", 0.0)),
                    config=dict(operation.get("config") or {}),
                )
                self.session.add(node)
                nodes[str(node_id)] = node
            elif action == "update":
                node_id = operation_id(operation, "node_id")
                node = nodes.get(node_id)
                if node is None:
                    raise ValueError(f"Node {node_id} was not found in this AgentFlow.")
                for key in ("node_type", "label", "position_x", "position_y"):
                    if key in operation:
                        setattr(node, key, operation[key])
                if "config" in operation:
                    node.config = dict(operation["config"] or {})
                if "config_patch" in operation:
                    node.config = {**(node.config or {}), **dict(operation["config_patch"] or {})}
            elif action == "delete":
                node_id = operation_id(operation, "node_id")
                node = nodes.pop(node_id, None)
                if node is None:
                    raise ValueError(f"Node {node_id} was not found in this AgentFlow.")
                for edge_id, edge in list(edges.items()):
                    if str(edge.source_node_id) == node_id or str(edge.target_node_id) == node_id:
                        await self.session.delete(edge)
                        edges.pop(edge_id)
                await self.session.delete(node)
            else:
                raise ValueError("Node operation op must be add, update, or delete.")

        await self.session.flush()

        for operation in edge_operations:
            action = str(operation.get("op") or "").lower()
            if action == "add":
                raw_id = str(operation.get("edge_id") or uuid.uuid4())
                try:
                    edge_id = uuid.UUID(raw_id)
                except ValueError as exc:
                    raise ValueError("edge_id must be a UUID when provided.") from exc
                if str(edge_id) in edges:
                    raise ValueError(f"Edge {edge_id} already exists.")
                source_id = operation_id(operation, "source_node_id")
                target_id = operation_id(operation, "target_node_id")
                if source_id not in nodes or target_id not in nodes:
                    raise ValueError("New edges must reference nodes in this AgentFlow.")
                edge = AgentFlowEdge(
                    id=edge_id,
                    flow_id=flow_id,
                    source_node_id=uuid.UUID(source_id),
                    target_node_id=uuid.UUID(target_id),
                    source_handle=operation.get("source_handle"),
                    target_handle=operation.get("target_handle"),
                    label=operation.get("label"),
                    edge_type=str(operation.get("edge_type") or "default"),
                    config=dict(operation.get("config") or {}),
                )
                self.session.add(edge)
                edges[str(edge_id)] = edge
            elif action == "update":
                edge_id = operation_id(operation, "edge_id")
                edge = edges.get(edge_id)
                if edge is None:
                    raise ValueError(f"Edge {edge_id} was not found in this AgentFlow.")
                source_id = str(operation.get("source_node_id") or edge.source_node_id)
                target_id = str(operation.get("target_node_id") or edge.target_node_id)
                if source_id not in nodes or target_id not in nodes:
                    raise ValueError("Updated edges must reference nodes in this AgentFlow.")
                edge.source_node_id = uuid.UUID(source_id)
                edge.target_node_id = uuid.UUID(target_id)
                for key in ("source_handle", "target_handle", "label", "edge_type"):
                    if key in operation:
                        setattr(edge, key, operation[key])
                if "config" in operation:
                    edge.config = dict(operation["config"] or {})
                if "config_patch" in operation:
                    edge.config = {**(edge.config or {}), **dict(operation["config_patch"] or {})}
            elif action == "delete":
                edge_id = operation_id(operation, "edge_id")
                edge = edges.pop(edge_id, None)
                if edge is None:
                    raise ValueError(f"Edge {edge_id} was not found in this AgentFlow.")
                await self.session.delete(edge)
            else:
                raise ValueError("Edge operation op must be add, update, or delete.")

        # Sync flow trigger & schedule_config from Input node if present
        input_node = next((node for node in nodes.values() if node.node_type == "input"), None)
        if input_node:
            cfg = dict(input_node.config or {})
            input_type = str(cfg.get("input_type") or "manual").lower()
            if input_type == "scheduled":
                flow.trigger_type = "scheduled"
                frequency = cfg.get("schedule_frequency") or cfg.get("frequency") or "nightly"
                sch_cfg = {
                    "frequency": frequency,
                    "schedule_time": cfg.get("schedule_time") or "07:00",
                }
                if frequency == "weekly":
                    sch_cfg["schedule_days"] = cfg.get("schedule_days") or ["mon", "tue", "wed", "thu", "fri"]
                elif frequency == "monthly":
                    sch_cfg["schedule_day"] = int(cfg.get("schedule_day") or 1)
                elif frequency == "hourly":
                    sch_cfg["minute_offset"] = int(cfg.get("minute_offset") or cfg.get("schedule_minute_offset") or 0)
                flow.schedule_config = sch_cfg
                if flow.status == "draft":
                    flow.status = "active"
            elif input_type in {"api", "event", "nexus"}:
                flow.trigger_type = input_type
            else:
                flow.trigger_type = "manual"

        flow.version = int(flow.version or 1) + 1
        await self.session.flush()
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
        if flow is None or flow.is_deleted or flow.flow_type != "standard":
            return None
        flow.status = status
        await self.session.flush()
        await self.session.refresh(flow)
        return flow
