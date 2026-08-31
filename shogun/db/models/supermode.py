"""Normalized durable records used by the Supermode mission runtime."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class MissionPlan(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_plans"
    __table_args__ = (
        Index("ix_mission_plans_mission_version", "mission_id", "version", unique=True),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    planner_model: Mapped[str | None] = mapped_column(String(500), nullable=True)
    plan_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    supersedes_version: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MissionAgent(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_agents"
    __table_args__ = (
        Index("ix_mission_agents_mission_status", "mission_id", "status"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("mission_agents.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="spawned")
    fleet_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_description: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", index=True)
    spawn_reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    spawn_requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    spawn_approved_by_commander: Mapped[bool] = mapped_column(nullable=False, default=True)
    capability_envelope: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    tool_allowlist: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    inherited_skill_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    inherited_skill_names: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    agent_routing_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    routing_preferences: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    current_task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    tasks_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tasks_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_used: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MissionTask(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_tasks"
    __table_args__ = (
        Index("ix_mission_tasks_mission_status", "mission_id", "status"),
        Index("ix_mission_tasks_status_wake", "status", "next_wake_at"),
        Index("ix_mission_tasks_lease", "lease_expires_at"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("mission_tasks.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    task_type: Mapped[str] = mapped_column(String(80), nullable=False, default="mission_research")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("mission_agents.id", ondelete="SET NULL"), nullable=True
    )
    depends_on_task_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    blocked_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    required_capabilities: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    required_tools: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    required_memory_scope: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_attempt_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    artifacts: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    findings: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    task_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    routing_reason: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_wake_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MissionEvent(Base, UUIDMixin):
    __tablename__ = "mission_events"
    __table_args__ = (
        Index("ix_mission_events_mission_created", "mission_id", "created_at"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="info")
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    event_data: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class MissionApproval(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_approvals"
    __table_args__ = (
        Index("ix_mission_approvals_mission_status", "mission_id", "status"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    arguments_redacted: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class MissionLearning(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_learning"
    __table_args__ = (
        Index("ix_mission_learning_mission_status", "mission_id", "status"),
    )

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    learning_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generalized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    source_refs: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    novelty: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    reusability: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    memory_scope: Mapped[str] = mapped_column(String(40), nullable=False, default="personal")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate", index=True)
    consolidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class MissionArtifact(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mission_artifacts"

    mission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    workspace_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
