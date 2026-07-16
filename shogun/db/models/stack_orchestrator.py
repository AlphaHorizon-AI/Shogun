"""Persistent runtime state for the Stack Orchestrator control layer."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class StackRun(Base, UUIDMixin, AuditMixin):
    """One governed, resumable execution supervised by Stack Orchestrator."""

    __tablename__ = "stack_runs"
    __table_args__ = (Index("ix_stack_runs_status_updated", "status", "updated_at"),)

    stack_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("agent_flows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    root_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    posture: Mapped[str] = mapped_column(String(30), nullable=False)
    model_profile: Mapped[str] = mapped_column(String(100), nullable=False, default="balanced")
    current_step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_runtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    max_retry_attempts_per_step: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    checkpoint_frequency: Mapped[str] = mapped_column(String(30), nullable=False, default="after_each_step")
    context_compaction: Mapped[bool] = mapped_column(nullable=False, default=True)
    verification_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    approval_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="inherited")
    artifact_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="retain_all")
    failure_policy: Mapped[str] = mapped_column(String(30), nullable=False, default="pause")
    success_criteria: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    allowed_tools: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    completed_steps: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    pending_steps: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    failed_steps: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    approval_events: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    model_usage: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    final_summary: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column("metadata_json", JSONType(), nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StackStepRun(Base, UUIDMixin, AuditMixin):
    """Persistent state for one orchestrated stack step."""

    __tablename__ = "stack_step_runs"
    __table_args__ = (
        Index("ix_stack_step_runs_stack_order", "stack_run_id", "sequence"),
        Index("ix_stack_step_runs_stack_status", "stack_run_id", "status"),
    )

    stack_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("stack_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    step_type: Mapped[str] = mapped_column(String(50), nullable=False, default="flow")
    flow_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("agent_flows.id", ondelete="SET NULL"),
        nullable=True,
    )
    flow_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    error_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    requires_verification: Mapped[bool] = mapped_column(nullable=False, default=True)
    requires_approval: Mapped[bool] = mapped_column(nullable=False, default=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    required_tools: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata_json", JSONType(), nullable=False, default=dict)


class StackCheckpoint(Base, UUIDMixin, AuditMixin):
    __tablename__ = "stack_checkpoints"
    __table_args__ = (Index("ix_stack_checkpoints_stack_created", "stack_run_id", "created_at"),)

    stack_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("stack_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("stack_step_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    resume_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    artifacts_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    state_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class StackArtifact(Base, UUIDMixin, AuditMixin):
    __tablename__ = "stack_artifacts"
    __table_args__ = (Index("ix_stack_artifacts_stack_step", "stack_run_id", "step_run_id"),)

    stack_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("stack_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("stack_step_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata_json", JSONType(), nullable=False, default=dict)


class StackVerification(Base, UUIDMixin, AuditMixin):
    __tablename__ = "stack_verifications"
    __table_args__ = (Index("ix_stack_verifications_stack_step", "stack_run_id", "step_run_id"),)

    stack_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("stack_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("stack_step_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    verification_type: Mapped[str] = mapped_column(String(50), nullable=False, default="flow_result")
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)
    observed_result: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata_json", JSONType(), nullable=False, default=dict)
