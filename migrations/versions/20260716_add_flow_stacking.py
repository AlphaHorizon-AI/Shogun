"""Add Flow Stacking hierarchy and flow composition metadata.

Revision ID: 20260716stack
Revises: 20260706chat
"""

from alembic import op
import sqlalchemy as sa


revision = "20260716stack"
down_revision = "20260706chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_flows", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("agent_flows", sa.Column("flow_type", sa.String(50), nullable=False, server_default="standard"))
    op.add_column("agent_flows", sa.Column("input_contract", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("agent_flows", sa.Column("output_contract", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("agent_flows", sa.Column("risk_tier", sa.String(20), nullable=False, server_default="low"))
    op.add_column("agent_flows", sa.Column("default_timeout_seconds", sa.Integer(), nullable=False, server_default="600"))
    op.add_column("agent_flows", sa.Column("allow_as_subflow", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("agent_flows", sa.Column("required_tools", sa.Text(), nullable=False, server_default="[]"))

    op.add_column("agent_flow_runs", sa.Column("flow_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("agent_flow_runs", sa.Column("root_run_id", sa.String(36), nullable=True))
    op.add_column("agent_flow_runs", sa.Column("parent_run_id", sa.String(36), nullable=True))
    op.add_column("agent_flow_runs", sa.Column("parent_node_id", sa.String(36), nullable=True))
    op.add_column("agent_flow_runs", sa.Column("run_depth", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("agent_flow_runs", sa.Column("input_payload", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("agent_flow_runs", sa.Column("output_payload", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("agent_flow_runs", sa.Column("artifacts", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("agent_flow_runs", sa.Column("governance_context", sa.Text(), nullable=False, server_default="{}"))
    op.execute("UPDATE agent_flow_runs SET root_run_id = id WHERE root_run_id IS NULL")
    with op.batch_alter_table("agent_flow_runs") as batch_op:
        batch_op.alter_column("root_run_id", existing_type=sa.String(36), nullable=False)
    op.create_index("ix_agent_flow_runs_root_run_id", "agent_flow_runs", ["root_run_id"])
    op.create_index("ix_agent_flow_runs_parent_run_id", "agent_flow_runs", ["parent_run_id"])

    op.create_table(
        "agent_flow_run_edges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("root_run_id", sa.String(36), nullable=False),
        sa.Column("parent_run_id", sa.String(36), nullable=False),
        sa.Column("child_run_id", sa.String(36), sa.ForeignKey("agent_flow_runs.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("parent_node_id", sa.String(36), nullable=False),
        sa.Column("child_flow_id", sa.String(36), nullable=False),
        sa.Column("execution_mode", sa.String(20), nullable=False, server_default="sequential"),
        sa.Column("status", sa.String(50), nullable=False, server_default="created"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_agent_flow_run_edges_root_run_id", "agent_flow_run_edges", ["root_run_id"])
    op.create_index("ix_agent_flow_run_edges_parent_run_id", "agent_flow_run_edges", ["parent_run_id"])
    op.create_index("ix_agent_flow_run_edges_root_parent", "agent_flow_run_edges", ["root_run_id", "parent_run_id"])


def downgrade() -> None:
    op.drop_table("agent_flow_run_edges")
    op.drop_index("ix_agent_flow_runs_parent_run_id", table_name="agent_flow_runs")
    op.drop_index("ix_agent_flow_runs_root_run_id", table_name="agent_flow_runs")
    for name in ("governance_context", "artifacts", "output_payload", "input_payload", "run_depth", "parent_node_id", "parent_run_id", "root_run_id", "flow_version"):
        op.drop_column("agent_flow_runs", name)
    for name in ("required_tools", "allow_as_subflow", "default_timeout_seconds", "risk_tier", "output_contract", "input_contract", "flow_type", "version"):
        op.drop_column("agent_flows", name)
