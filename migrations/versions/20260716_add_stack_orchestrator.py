"""Add persistent Stack Orchestrator runtime state.

Revision ID: 20260716orch
Revises: 20260716stack
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260716orch"
down_revision = "20260716stack"
branch_labels = None
depends_on = None


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "stack_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("stack_id", GUID(), sa.ForeignKey("agent_flows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("root_run_id", GUID(), nullable=True),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("posture", sa.String(30), nullable=False),
        sa.Column("model_profile", sa.String(100), nullable=False),
        sa.Column("current_step_id", sa.String(255), nullable=True),
        sa.Column("max_runtime_minutes", sa.Integer(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("max_retry_attempts_per_step", sa.Integer(), nullable=False),
        sa.Column("checkpoint_frequency", sa.String(30), nullable=False),
        sa.Column("context_compaction", sa.Boolean(), nullable=False),
        sa.Column("verification_required", sa.Boolean(), nullable=False),
        sa.Column("approval_policy", sa.String(50), nullable=False),
        sa.Column("artifact_policy", sa.String(30), nullable=False),
        sa.Column("failure_policy", sa.String(30), nullable=False),
        sa.Column("success_criteria", JSONType(), nullable=False),
        sa.Column("allowed_tools", JSONType(), nullable=False),
        sa.Column("completed_steps", JSONType(), nullable=False),
        sa.Column("pending_steps", JSONType(), nullable=False),
        sa.Column("failed_steps", JSONType(), nullable=False),
        sa.Column("approval_events", JSONType(), nullable=False),
        sa.Column("model_usage", JSONType(), nullable=False),
        sa.Column("final_summary", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
    )
    op.create_index("ix_stack_runs_stack_id", "stack_runs", ["stack_id"])
    op.create_index("ix_stack_runs_root_run_id", "stack_runs", ["root_run_id"])
    op.create_index("ix_stack_runs_status_updated", "stack_runs", ["status", "updated_at"])

    op.create_table(
        "stack_step_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("stack_run_id", GUID(), sa.ForeignKey("stack_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(255), nullable=False),
        sa.Column("parent_step_id", sa.String(255), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("step_type", sa.String(50), nullable=False),
        sa.Column("flow_id", GUID(), sa.ForeignKey("agent_flows.id", ondelete="SET NULL"), nullable=True),
        sa.Column("flow_run_id", GUID(), nullable=True),
        sa.Column("model_used", sa.String(255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("input_json", JSONType(), nullable=False),
        sa.Column("output_json", JSONType(), nullable=False),
        sa.Column("error_json", JSONType(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(30), nullable=False),
        sa.Column("requires_verification", sa.Boolean(), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("required_tools", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stack_step_runs_stack_run_id", "stack_step_runs", ["stack_run_id"])
    op.create_index("ix_stack_step_runs_flow_run_id", "stack_step_runs", ["flow_run_id"])
    op.create_index("ix_stack_step_runs_stack_order", "stack_step_runs", ["stack_run_id", "sequence"])
    op.create_index("ix_stack_step_runs_stack_status", "stack_step_runs", ["stack_run_id", "status"])

    op.create_table(
        "stack_checkpoints",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("stack_run_id", GUID(), sa.ForeignKey("stack_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_run_id", GUID(), sa.ForeignKey("stack_step_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=False),
        sa.Column("resume_instruction", sa.Text(), nullable=False),
        sa.Column("artifacts_json", JSONType(), nullable=False),
        sa.Column("state_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stack_checkpoints_stack_run_id", "stack_checkpoints", ["stack_run_id"])
    op.create_index("ix_stack_checkpoints_stack_created", "stack_checkpoints", ["stack_run_id", "created_at"])

    op.create_table(
        "stack_artifacts",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("stack_run_id", GUID(), sa.ForeignKey("stack_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_run_id", GUID(), sa.ForeignKey("stack_step_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("artifact_type", sa.String(50), nullable=False),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stack_artifacts_stack_run_id", "stack_artifacts", ["stack_run_id"])
    op.create_index("ix_stack_artifacts_stack_step", "stack_artifacts", ["stack_run_id", "step_run_id"])

    op.create_table(
        "stack_verifications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("stack_run_id", GUID(), sa.ForeignKey("stack_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_run_id", GUID(), sa.ForeignKey("stack_step_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("verification_type", sa.String(50), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False),
        sa.Column("observed_result", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_stack_verifications_stack_run_id", "stack_verifications", ["stack_run_id"])
    op.create_index("ix_stack_verifications_stack_step", "stack_verifications", ["stack_run_id", "step_run_id"])


def downgrade() -> None:
    op.drop_table("stack_verifications")
    op.drop_table("stack_artifacts")
    op.drop_table("stack_checkpoints")
    op.drop_table("stack_step_runs")
    op.drop_table("stack_runs")
