"""Portable relational foundation for the Kiroku MemoryGraph."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class MemoryGraphNode(Base, UUIDMixin, AuditMixin):
    __tablename__ = "memory_graph_nodes"
    __table_args__ = (
        UniqueConstraint("canonical_key", name="uq_memory_graph_nodes_canonical_key"),
        Index("ix_memory_graph_nodes_scope", "tenant_id", "workspace_id", "project_id"),
        Index("ix_memory_graph_nodes_type_status", "node_type", "status"),
    )

    canonical_key: Mapped[str] = mapped_column(String(700), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    scope_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, default="local")
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sensitivity: Mapped[str] = mapped_column(String(30), nullable=False, default="internal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    source_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("memory_records.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MemoryGraphEdge(Base, UUIDMixin, AuditMixin):
    __tablename__ = "memory_graph_edges"
    __table_args__ = (
        UniqueConstraint(
            "from_node_id", "to_node_id", "relationship_type", name="uq_memory_graph_edges_relation"
        ),
        Index("ix_memory_graph_edges_from_type", "from_node_id", "relationship_type"),
        Index("ix_memory_graph_edges_to_type", "to_node_id", "relationship_type"),
    )

    from_node_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("memory_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    to_node_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("memory_graph_nodes.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(60), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("memory_records.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")


class MemoryGraphConflict(Base, UUIDMixin, AuditMixin):
    __tablename__ = "memory_graph_conflicts"
    __table_args__ = (
        Index("ix_memory_graph_conflicts_status", "resolution_status", "created_at"),
        Index("ix_memory_graph_conflicts_memories", "memory_id_a", "memory_id_b"),
    )

    memory_id_a: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False
    )
    memory_id_b: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("memory_records.id", ondelete="CASCADE"), nullable=False
    )
    conflict_type: Mapped[str] = mapped_column(String(50), nullable=False, default="contradiction")
    resolution_status: Mapped[str] = mapped_column(String(30), nullable=False, default="needs_review")
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
