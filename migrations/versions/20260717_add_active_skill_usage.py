"""Add normalized active skill usage metadata and run records.

Revision ID: 20260717skills
Revises: 20260717router
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260717skills"
down_revision = "20260717router"
branch_labels = None
depends_on = None


def upgrade() -> None:
    additions = [
        sa.Column("exam_status", sa.String(30), nullable=False, server_default="untested"),
        sa.Column("tags", JSONType(), nullable=False, server_default="[]"),
        sa.Column("triggers", JSONType(), nullable=False, server_default="[]"),
        sa.Column("use_when", JSONType(), nullable=False, server_default="[]"),
        sa.Column("avoid_when", JSONType(), nullable=False, server_default="[]"),
        sa.Column("requires_tools", JSONType(), nullable=False, server_default="[]"),
        sa.Column("minimum_posture", sa.String(30), nullable=False, server_default="guarded"),
        sa.Column("risk_tier", sa.String(20), nullable=False, server_default="low"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("conflict_group", sa.String(100), nullable=True),
        sa.Column("model_hint", sa.String(100), nullable=True),
        sa.Column("max_context_tokens", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("activation_mode", sa.String(30), nullable=False, server_default="advisory"),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("brief_text", sa.Text(), nullable=True),
        sa.Column("verification_checklist", JSONType(), nullable=False, server_default="[]"),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    ]
    for column in additions:
        op.add_column("skills", column)
    op.create_table(
        "active_skill_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("stack_run_id", GUID(), nullable=True),
        sa.Column("step_run_id", GUID(), nullable=True),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activation_reason", sa.Text(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("activation_mode", sa.String(30), nullable=False),
        sa.Column("usage_location", sa.String(50), nullable=False),
        sa.Column("injected_tokens", sa.Integer(), nullable=False),
        sa.Column("posture", sa.String(30), nullable=False),
        sa.Column("conflict_notes", JSONType(), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("outcome_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_active_skill_runs_run", "active_skill_runs", ["run_id", "created_at"])
    op.create_index("ix_active_skill_runs_stack_step", "active_skill_runs", ["stack_run_id", "step_run_id"])
    op.create_index("ix_active_skill_runs_skill", "active_skill_runs", ["skill_id", "created_at"])


def downgrade() -> None:
    op.drop_table("active_skill_runs")
    for name in [
        "failure_count", "success_count", "usage_count", "last_used_at", "embedding_id",
        "verification_checklist", "brief_text", "body_text", "activation_mode", "max_context_tokens",
        "model_hint", "conflict_group", "priority", "risk_tier", "minimum_posture", "requires_tools",
        "avoid_when", "use_when", "triggers", "tags", "exam_status",
    ]:
        op.drop_column("skills", name)
