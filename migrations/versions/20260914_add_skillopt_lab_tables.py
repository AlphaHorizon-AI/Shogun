"""Add SkillOpt Lab tables and versioning extensions.

Revision ID: 20260914skilloptlab
Revises: 20260831fleetskills
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260914skilloptlab"
down_revision = "20260831fleetskills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ── 1. Extend existing skill_versions table ───────────────────────
    if "skill_versions" in tables:
        columns = {column["name"] for column in inspector.get_columns("skill_versions")}
        version_additions = [
            ("scope", sa.Column("scope", sa.String(30), nullable=False, server_default="local")),
            ("quarantine_status", sa.Column("quarantine_status", sa.String(30), nullable=True)),
            ("quarantine_reason", sa.Column("quarantine_reason", sa.Text(), nullable=True)),
            ("activated_at", sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True)),
            ("superseded_at", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True)),
            (
                "approval_policy",
                sa.Column("approval_policy", sa.String(50), nullable=False, server_default="require_local_admin"),
            ),
            (
                "tool_schema_hashes_json",
                sa.Column("tool_schema_hashes_json", JSONType(), nullable=False, server_default="{}"),
            ),
        ]
        with op.batch_alter_table("skill_versions") as batch:
            for name, column in version_additions:
                if name not in columns:
                    batch.add_column(column)

        # Backfill defaults for any preexisting rows with NULLs
        op.execute("UPDATE skill_versions SET scope = 'local' WHERE scope IS NULL")
        op.execute("UPDATE skill_versions SET approval_policy = 'require_local_admin' WHERE approval_policy IS NULL")
        op.execute("UPDATE skill_versions SET tool_schema_hashes_json = '{}' WHERE tool_schema_hashes_json IS NULL")

    # ── 2. Extend existing skillopt_candidates table ──────────────────
    if "skillopt_candidates" in tables:
        columns = {column["name"] for column in inspector.get_columns("skillopt_candidates")}
        candidate_additions = [
            (
                "textual_gradient_json",
                sa.Column("textual_gradient_json", JSONType(), nullable=False, server_default="{}"),
            ),
            ("iteration_number", sa.Column("iteration_number", sa.Integer(), nullable=False, server_default="1")),
            (
                "tool_schema_hashes_json",
                sa.Column("tool_schema_hashes_json", JSONType(), nullable=False, server_default="{}"),
            ),
        ]
        with op.batch_alter_table("skillopt_candidates") as batch:
            for name, column in candidate_additions:
                if name not in columns:
                    batch.add_column(column)

        # Backfill defaults
        op.execute("UPDATE skillopt_candidates SET textual_gradient_json = '{}' WHERE textual_gradient_json IS NULL")
        op.execute("UPDATE skillopt_candidates SET iteration_number = 1 WHERE iteration_number IS NULL")
        op.execute(
            "UPDATE skillopt_candidates SET tool_schema_hashes_json = '{}' WHERE tool_schema_hashes_json IS NULL"
        )

    # Re-inspect tables for new table creations
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ── 3. Create 8 new SkillOpt Lab tables ────────────────────────────

    # 3.1 skillopt_lab_runs
    if "skillopt_lab_runs" not in tables:
        op.create_table(
            "skillopt_lab_runs",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "base_version_id", GUID(), sa.ForeignKey("skill_versions.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("optimizer_model", sa.String(255), nullable=True),
            sa.Column("execution_mode", sa.String(30), nullable=False, server_default="mock"),
            sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="10"),
            sa.Column("max_llm_calls", sa.Integer(), nullable=False, server_default="40"),
            sa.Column("max_tool_calls", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("max_runtime_seconds", sa.Integer(), nullable=False, server_default="900"),
            sa.Column("max_cost_eur", sa.Float(), nullable=False, server_default="5.0"),
            sa.Column("current_iteration", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_llm_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tool_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_cost_eur", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("best_candidate_id", GUID(), nullable=True),
            sa.Column("best_score", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("result_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("config_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_skillopt_lab_run_skill",
            "skillopt_lab_runs",
            ["skill_id", "status"],
        )

    # 3.2 skillopt_regression_suites
    if "skillopt_regression_suites" not in tables:
        op.create_table(
            "skillopt_regression_suites",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("minimum_pass_rate", sa.Float(), nullable=False, server_default="0.95"),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_pass_rate", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_regression_suite_skill",
            "skillopt_regression_suites",
            ["skill_id"],
        )

    # 3.3 skillopt_regression_cases
    if "skillopt_regression_cases" not in tables:
        op.create_table(
            "skillopt_regression_cases",
            sa.Column("id", GUID(), nullable=False),
            sa.Column(
                "suite_id", GUID(), sa.ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("case_id", sa.String(100), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("input_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("expected_output_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("evaluation_criteria_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("tags", JSONType(), nullable=False, server_default="[]"),
            sa.Column("is_enabled", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_regression_case_suite",
            "skillopt_regression_cases",
            ["suite_id"],
        )

    # 3.4 skillopt_regression_runs
    if "skillopt_regression_runs" not in tables:
        op.create_table(
            "skillopt_regression_runs",
            sa.Column("id", GUID(), nullable=False),
            sa.Column(
                "suite_id", GUID(), sa.ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column(
                "skill_version_id", GUID(), sa.ForeignKey("skill_versions.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("model_used", sa.String(255), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="running"),
            sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_cases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("pass_rate", sa.Float(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("results_json", JSONType(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_regression_run_suite",
            "skillopt_regression_runs",
            ["suite_id"],
        )

    # 3.5 skillopt_benchmark_runs
    if "skillopt_benchmark_runs" not in tables:
        op.create_table(
            "skillopt_benchmark_runs",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "regression_suite_id",
                GUID(),
                sa.ForeignKey("skillopt_regression_suites.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "skill_version_id", GUID(), sa.ForeignKey("skill_versions.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("model_ids_json", JSONType(), nullable=False, server_default="[]"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("summary_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_benchmark_run_skill",
            "skillopt_benchmark_runs",
            ["skill_id"],
        )

    # 3.6 skillopt_benchmark_results
    if "skillopt_benchmark_results" not in tables:
        op.create_table(
            "skillopt_benchmark_results",
            sa.Column("id", GUID(), nullable=False),
            sa.Column(
                "benchmark_run_id",
                GUID(),
                sa.ForeignKey("skillopt_benchmark_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("model_id", sa.String(255), nullable=False),
            sa.Column("success_rate", sa.Float(), nullable=True),
            sa.Column("policy_compliance", sa.Float(), nullable=True),
            sa.Column("avg_tool_calls", sa.Float(), nullable=True),
            sa.Column("avg_latency_seconds", sa.Float(), nullable=True),
            sa.Column("avg_cost_eur", sa.Float(), nullable=True),
            sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("passed_cases", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("results_json", JSONType(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_benchmark_result_run",
            "skillopt_benchmark_results",
            ["benchmark_run_id"],
        )

    # 3.7 skillopt_competence_profiles
    if "skillopt_competence_profiles" not in tables:
        op.create_table(
            "skillopt_competence_profiles",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("model_id", sa.String(255), nullable=False),
            sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scope", sa.String(30), nullable=False, server_default="local"),
            sa.Column("success_rate", sa.Float(), nullable=True),
            sa.Column("policy_compliance", sa.Float(), nullable=True),
            sa.Column("avg_tool_calls", sa.Float(), nullable=True),
            sa.Column("avg_latency_seconds", sa.Float(), nullable=True),
            sa.Column("avg_cost_eur", sa.Float(), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("profile_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_competence_profile_model_skill",
            "skillopt_competence_profiles",
            ["model_id", "skill_id"],
        )

    # 3.8 skillopt_tool_schema_versions
    if "skillopt_tool_schema_versions" not in tables:
        op.create_table(
            "skillopt_tool_schema_versions",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("tool_name", sa.String(255), nullable=False),
            sa.Column("schema_hash", sa.String(255), nullable=False),
            sa.Column("schema_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
            sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_tool_schema_name",
            "skillopt_tool_schema_versions",
            ["tool_name"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # Drop tables in reverse dependency order
    for table_name in (
        "skillopt_tool_schema_versions",
        "skillopt_competence_profiles",
        "skillopt_benchmark_results",
        "skillopt_benchmark_runs",
        "skillopt_regression_runs",
        "skillopt_regression_cases",
        "skillopt_regression_suites",
        "skillopt_lab_runs",
    ):
        if table_name in tables:
            op.drop_table(table_name)

    # Drop columns from skillopt_candidates
    if "skillopt_candidates" in tables:
        columns = {column["name"] for column in inspector.get_columns("skillopt_candidates")}
        with op.batch_alter_table("skillopt_candidates") as batch:
            for name in ("tool_schema_hashes_json", "iteration_number", "textual_gradient_json"):
                if name in columns:
                    batch.drop_column(name)

    # Drop columns from skill_versions
    if "skill_versions" in tables:
        columns = {column["name"] for column in inspector.get_columns("skill_versions")}
        with op.batch_alter_table("skill_versions") as batch:
            for name in (
                "tool_schema_hashes_json",
                "approval_policy",
                "superseded_at",
                "activated_at",
                "quarantine_reason",
                "quarantine_status",
                "scope",
            ):
                if name in columns:
                    batch.drop_column(name)
