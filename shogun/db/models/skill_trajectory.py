"""Order 10 structured evidence for active skill usage."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class SkillCandidateRetrieval(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_candidate_retrievals"
    __table_args__ = (Index("ix_skill_candidate_retrieval_run", "run_id", "created_at"),)

    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    flow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    task_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    candidate_skill_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    retrieval_scores: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    selected_skill_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    rejected_skill_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillEpisode(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_episodes"
    __table_args__ = (
        Index("ix_skill_episode_run", "run_id", "created_at"),
        Index("ix_skill_episode_skill", "skill_id", "created_at"),
        Index("ix_skill_episode_active_run", "active_skill_run_id"),
    )

    active_skill_run_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("active_skill_runs.id", ondelete="SET NULL"), nullable=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version: Mapped[str] = mapped_column(String(80), nullable=False, default="1.0.0")
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    flow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    node_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_profile: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posture: Mapped[str] = mapped_column(String(30), nullable=False, default="guarded")
    task_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selection_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    injection_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="context_block")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="selected", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillTrajectory(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_trajectories"
    __table_args__ = (
        Index("ix_skill_trajectory_run", "run_id", "created_at"),
        Index("ix_skill_trajectory_skill", "skill_id", "created_at"),
        Index("ix_skill_trajectory_outcome", "final_outcome", "score"),
    )

    skill_episode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version: Mapped[str] = mapped_column(String(80), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    trajectory_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    final_outcome: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    contribution: Mapped[str] = mapped_column(String(30), nullable=False, default="unclear")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillToolLink(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_tool_links"
    __table_args__ = (Index("ix_skill_tool_link_episode", "skill_episode_id", "created_at"),)

    skill_episode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_input_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tool_output_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="completed")
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillVerificationLink(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_verification_links"
    __table_args__ = (Index("ix_skill_verification_episode", "skill_episode_id", "created_at"),)

    skill_episode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    verification_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    observed_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOutcomeScore(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_outcome_scores"
    __table_args__ = (Index("ix_skill_outcome_score_skill", "skill_id", "created_at"),)

    skill_episode_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version: Mapped[str] = mapped_column(String(80), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    score_type: Mapped[str] = mapped_column(String(50), nullable=False, default="contribution")
    scoring_method: Mapped[str] = mapped_column(String(80), nullable=False, default="deterministic_v1")
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillImprovementCandidate(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_improvement_candidates"
    __table_args__ = (Index("ix_skill_improvement_skill", "skill_id", "status", "created_at"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_version: Mapped[str] = mapped_column(String(80), nullable=False)
    based_on_trajectory_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_trajectories.id", ondelete="SET NULL"), nullable=True
    )
    issue_type: Mapped[str] = mapped_column(String(100), nullable=False)
    observed_problem: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_improvement: Mapped[str] = mapped_column(Text, nullable=False)
    validation_idea: Mapped[str] = mapped_column(Text, nullable=False, default="Replay on a held-out task.")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="candidate", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
