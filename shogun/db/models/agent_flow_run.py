"""AgentFlowRun ORM model — tracks a single execution of an Agent Flow."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class AgentFlowRun(Base, UUIDMixin, AuditMixin):
    """A single execution run of an Agent Flow."""

    __tablename__ = "agent_flow_runs"

    flow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_flows.id", ondelete="CASCADE"), nullable=False,
    )
    flow_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    root_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    parent_node_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    run_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")

    # Per-node execution state: { node_id: { status, output, error, started_at, completed_at } }
    node_states: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    # Final aggregated results
    result_summary: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    input_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    artifacts: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    governance_context: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Error info
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)


class AgentFlowRunEdge(Base, UUIDMixin, AuditMixin):
    """Materialized parent-child link used to query a Flow Stacking tree."""

    __tablename__ = "agent_flow_run_edges"
    __table_args__ = (
        Index("ix_agent_flow_run_edges_root_parent", "root_run_id", "parent_run_id"),
    )

    root_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    parent_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    child_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent_flow_runs.id", ondelete="CASCADE"), nullable=False, unique=True,
    )
    parent_node_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    child_flow_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="sequential")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
