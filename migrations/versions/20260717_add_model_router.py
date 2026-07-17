"""Add task-aware model registry, decisions, and usage.

Revision ID: 20260717router
Revises: 20260716tpls
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260717router"
down_revision = "20260716tpls"
branch_labels = None
depends_on = None


def _audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "model_registry",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("provider_id", GUID(), sa.ForeignKey("model_providers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("connection_type", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("capabilities", JSONType(), nullable=False),
        sa.Column("quality_tier", sa.Integer(), nullable=False),
        sa.Column("cost_tier", sa.Integer(), nullable=False),
        sa.Column("latency_tier", sa.Integer(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("local", sa.Boolean(), nullable=False),
        sa.Column("role_tags", JSONType(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("config_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_model_registry_provider_id", "model_registry", ["provider_id"])
    op.create_index("ix_model_registry_model_provider", "model_registry", ["model_id", "provider_id"], unique=True)
    op.create_index("ix_model_registry_enabled", "model_registry", ["enabled", "cost_tier", "quality_tier"])
    op.create_table(
        "model_routing_decisions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("run_id", GUID(), nullable=True),
        sa.Column("stack_run_id", GUID(), nullable=True),
        sa.Column("step_id", sa.String(255), nullable=True),
        sa.Column("task_type", sa.String(80), nullable=False),
        sa.Column("complexity_score", sa.Integer(), nullable=False),
        sa.Column("active_profile", sa.String(100), nullable=False),
        sa.Column("selected_registry_id", GUID(), nullable=True),
        sa.Column("selected_model", sa.String(255), nullable=False),
        sa.Column("selected_provider", sa.String(100), nullable=False),
        sa.Column("fallback_model", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("estimated_cost_tier", sa.Integer(), nullable=False),
        sa.Column("estimated_latency_tier", sa.Integer(), nullable=False),
        sa.Column("escalation_level", sa.Integer(), nullable=False),
        sa.Column("requires_vision", sa.Boolean(), nullable=False),
        sa.Column("requires_tool_use", sa.Boolean(), nullable=False),
        sa.Column("requires_json_mode", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        *_audit_columns(),
    )
    op.create_index("ix_model_routing_decisions_run_id", "model_routing_decisions", ["run_id"])
    op.create_index("ix_model_routing_decisions_stack_run_id", "model_routing_decisions", ["stack_run_id"])
    op.create_index("ix_model_routing_decisions_run", "model_routing_decisions", ["run_id", "created_at"])
    op.create_index("ix_model_routing_decisions_stack", "model_routing_decisions", ["stack_run_id", "created_at"])
    op.create_table(
        "model_usage_events",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "routing_decision_id",
            GUID(),
            sa.ForeignKey("model_routing_decisions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("stack_run_id", GUID(), nullable=True),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_json", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_usage_events_routing_decision_id", "model_usage_events", ["routing_decision_id"])
    op.create_index("ix_model_usage_events_stack_run_id", "model_usage_events", ["stack_run_id"])
    op.create_index("ix_model_usage_decision", "model_usage_events", ["routing_decision_id", "created_at"])
    op.create_index("ix_model_usage_stack", "model_usage_events", ["stack_run_id", "created_at"])


def downgrade() -> None:
    op.drop_table("model_usage_events")
    op.drop_table("model_routing_decisions")
    op.drop_table("model_registry")
