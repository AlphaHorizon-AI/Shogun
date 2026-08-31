"""Mission ORM model.

The table predates Supermode and is also used by the lightweight Bushido
mission ledger.  Supermode deliberately extends that durable unit instead of
creating a second, competing mission abstraction.  Existing columns remain
backwards compatible; Supermode rows are identified by ``is_supermode`` and
``mission_type == "supermode"``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class Mission(Base, UUIDMixin, AuditMixin):
    __tablename__ = "missions"
    __table_args__ = (
        Index("ix_missions_supermode_status", "is_supermode", "status"),
        Index("ix_missions_owner_status", "owner_user_id", "status"),
        Index("ix_missions_next_wake_at", "next_wake_at"),
    )

    mission_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False, default="operator")
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    parent_mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("missions.id"), nullable=True)
    root_mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_summary: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Durable Supermode mission record.  Defaults keep legacy rows valid.
    is_supermode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    owner_user_id: Mapped[str] = mapped_column(String(255), nullable=False, default="local_user")
    team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    objective: Mapped[str | None] = mapped_column(Text, nullable=True)
    objective_original: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    constraints: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    assumptions: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    current_plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    posture_at_creation: Mapped[str | None] = mapped_column(String(30), nullable=True)
    governance_snapshot: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    max_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    max_total_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    max_parallel_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    max_task_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    max_plan_revisions: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=150)
    token_budget: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monetary_budget: Mapped[float | None] = mapped_column(Float, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    model_calls_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_wake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    agentflow_candidate: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    agentflow_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
