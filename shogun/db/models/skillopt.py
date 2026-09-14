"""SkillOpt Integration ORM models.

Covers the existing SkillOpt versioning/candidate/eval tables and the new
SkillOpt Lab tables for the Yellow Label local optimization engine (lab runs,
regression suites, model benchmarks, competence profiles, tool schema tracking).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


# ── Existing SkillOpt tables (extended) ──────────────────────


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

    # ── Yellow Label SkillOpt Lab extensions ─────────────────
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    quarantine_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    quarantine_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_policy: Mapped[str] = mapped_column(
        String(50), nullable=False, default="require_local_admin"
    )
    tool_schema_hashes_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )


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

    # ── Yellow Label SkillOpt Lab extensions ─────────────────
    textual_gradient_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tool_schema_hashes_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )


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


# ── SkillOpt Lab tables ──────────────────────────────────────


class SkillOptLabRun(Base, UUIDMixin, AuditMixin):
    """A proactive optimization run in the SkillOpt Lab."""

    __tablename__ = "skillopt_lab_runs"
    __table_args__ = (Index("ix_skillopt_lab_run_skill", "skill_id", "status"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_version_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    optimizer_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(30), nullable=False, default="mock"
    )

    # Budget limits (§40)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    max_llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    max_runtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900)
    max_cost_eur: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)

    # Progress tracking
    current_iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    best_candidate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    best_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    result_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    config_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptRegressionSuite(Base, UUIDMixin, AuditMixin):
    """A regression test suite for a local skill."""

    __tablename__ = "skillopt_regression_suites"
    __table_args__ = (Index("ix_regression_suite_skill", "skill_id"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    minimum_pass_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)


class SkillOptRegressionCase(Base, UUIDMixin, AuditMixin):
    """An individual test case within a regression suite."""

    __tablename__ = "skillopt_regression_cases"
    __table_args__ = (Index("ix_regression_case_suite", "suite_id"),)

    suite_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    expected_output_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    evaluation_criteria_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=1
    )


class SkillOptRegressionRun(Base, UUIDMixin, AuditMixin):
    """Execution record for a regression suite run."""

    __tablename__ = "skillopt_regression_runs"
    __table_args__ = (Index("ix_regression_run_suite", "suite_id"),)

    suite_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    skill_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    results_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)


class SkillOptBenchmarkRun(Base, UUIDMixin, AuditMixin):
    """A model benchmark run comparing multiple models on a regression suite."""

    __tablename__ = "skillopt_benchmark_runs"
    __table_args__ = (Index("ix_benchmark_run_skill", "skill_id"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regression_suite_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"),
        nullable=False
    )
    skill_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="SET NULL"), nullable=True
    )
    model_ids_json: Mapped[list] = mapped_column(
        JSONType(), nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    summary_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptBenchmarkResult(Base, UUIDMixin, AuditMixin):
    """Per-model results within a benchmark run."""

    __tablename__ = "skillopt_benchmark_results"
    __table_args__ = (Index("ix_benchmark_result_run", "benchmark_run_id"),)

    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skillopt_benchmark_runs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_compliance: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_tool_calls: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)


class SkillOptCompetenceProfile(Base, UUIDMixin, AuditMixin):
    """Local model competence profile — stores benchmark results per model per skill."""

    __tablename__ = "skillopt_competence_profiles"
    __table_args__ = (
        Index("ix_competence_profile_model_skill", "model_id", "skill_id"),
    )

    model_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(30), nullable=False, default="local")
    success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_compliance: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_tool_calls: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    profile_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class SkillOptToolSchemaVersion(Base, UUIDMixin, AuditMixin):
    """Tracks tool schema hashes for staleness detection (§20)."""

    __tablename__ = "skillopt_tool_schema_versions"
    __table_args__ = (Index("ix_tool_schema_name", "tool_name"),)

    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    schema_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
