"""SkillOpt Integration ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class SkillVersion(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_versions"
    __table_args__ = (Index("ix_skill_version_skill", "skill_id", "version_number"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate")
    content_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillUsageEvent(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_usage_events"
    __table_args__ = (
        Index("ix_skill_usage_event_skill", "skill_id", "skill_version_id"),
        Index("ix_skill_usage_event_run", "run_id"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    task_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptTrainingRun(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skillopt_training_runs"
    __table_args__ = (Index("ix_skillopt_training_run_skill", "skill_id", "status"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    optimizer_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_model_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    training_set_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    validation_set_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    result_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptCandidate(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skillopt_candidates"
    __table_args__ = (Index("ix_skillopt_candidate_run", "training_run_id"),)

    training_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skillopt_training_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=False
    )
    candidate_content_path: Mapped[str] = mapped_column(String(500), nullable=False)
    candidate_diff_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_validation")
    static_validation_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptEvalResult(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skillopt_eval_results"
    __table_args__ = (Index("ix_skillopt_eval_result_candidate", "candidate_id"),)

    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skillopt_candidates.id", ondelete="CASCADE"), nullable=True, index=True
    )
    skill_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=True
    )
    eval_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posture: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    baseline_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    safety_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    runtime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
