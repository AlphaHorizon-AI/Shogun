"""Add durable Supermode mission runtime and Mission Control records.

Revision ID: 20260831supermode
Revises: 20260819transprofiles
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260831supermode"
down_revision = "20260819transprofiles"
branch_labels = None
depends_on = None


def _audit_columns():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=True, server_default="system"),
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    now = datetime.now(timezone.utc)

    if "missions" in tables:
        columns = {column["name"] for column in inspector.get_columns("missions")}
        additions = (
            ("is_supermode", sa.Column("is_supermode", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("owner_user_id", sa.Column("owner_user_id", sa.String(255), nullable=False, server_default="local_user")),
            ("team_id", sa.Column("team_id", sa.String(255), nullable=True)),
            ("chat_session_id", sa.Column("chat_session_id", sa.String(255), nullable=True)),
            ("objective", sa.Column("objective", sa.Text(), nullable=True)),
            ("objective_original", sa.Column("objective_original", sa.Text(), nullable=True)),
            ("success_criteria", sa.Column("success_criteria", JSONType(), nullable=False, server_default="[]")),
            ("constraints", sa.Column("constraints", JSONType(), nullable=False, server_default="[]")),
            ("assumptions", sa.Column("assumptions", JSONType(), nullable=False, server_default="[]")),
            (
                "current_plan_version",
                sa.Column("current_plan_version", sa.Integer(), nullable=False, server_default="0"),
            ),
            ("progress_percent", sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0")),
            ("posture_at_creation", sa.Column("posture_at_creation", sa.String(30), nullable=True)),
            ("governance_snapshot", sa.Column("governance_snapshot", JSONType(), nullable=False, server_default="{}")),
            ("max_agents", sa.Column("max_agents", sa.Integer(), nullable=False, server_default="6")),
            ("max_total_agents", sa.Column("max_total_agents", sa.Integer(), nullable=False, server_default="20")),
            ("max_parallel_agents", sa.Column("max_parallel_agents", sa.Integer(), nullable=False, server_default="6")),
            ("max_task_depth", sa.Column("max_task_depth", sa.Integer(), nullable=False, server_default="2")),
            ("max_plan_revisions", sa.Column("max_plan_revisions", sa.Integer(), nullable=False, server_default="10")),
            ("max_model_calls", sa.Column("max_model_calls", sa.Integer(), nullable=False, server_default="150")),
            ("token_budget", sa.Column("token_budget", sa.Integer(), nullable=True)),
            ("monetary_budget", sa.Column("monetary_budget", sa.Float(), nullable=True)),
            ("deadline_at", sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True)),
            ("model_calls_used", sa.Column("model_calls_used", sa.Integer(), nullable=False, server_default="0")),
            ("tokens_used", sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0")),
            ("cost_used", sa.Column("cost_used", sa.Float(), nullable=False, server_default="0")),
            ("last_activity_at", sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True)),
            ("next_wake_at", sa.Column("next_wake_at", sa.DateTime(timezone=True), nullable=True)),
            ("result_summary", sa.Column("result_summary", sa.Text(), nullable=True)),
            ("final_answer", sa.Column("final_answer", sa.Text(), nullable=True)),
            ("error_message", sa.Column("error_message", sa.Text(), nullable=True)),
            ("agentflow_candidate", sa.Column("agentflow_candidate", JSONType(), nullable=False, server_default="{}")),
            ("agentflow_id", sa.Column("agentflow_id", GUID(), nullable=True)),
        )
        with op.batch_alter_table("missions") as batch:
            for name, column in additions:
                if name not in columns:
                    batch.add_column(column)

    if "mission_plans" not in tables:
        op.create_table(
            "mission_plans",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(1000), nullable=False),
            sa.Column("planner_model", sa.String(500), nullable=True),
            sa.Column("plan_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("supersedes_version", sa.Integer(), nullable=True),
            *_audit_columns(),
            sa.UniqueConstraint("mission_id", "version", name="uq_mission_plans_mission_version"),
        )
    if "mission_agents" not in tables:
        op.create_table(
            "mission_agents",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "parent_agent_id",
                GUID(),
                sa.ForeignKey("mission_agents.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("role_name", sa.String(255), nullable=False),
            sa.Column("role_description", sa.String(2000), nullable=False, server_default=""),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("system_instructions", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
            sa.Column("spawn_reason", sa.String(2000), nullable=False),
            sa.Column("spawn_requested_by", sa.String(255), nullable=True),
            sa.Column("spawn_approved_by_commander", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("capability_envelope", JSONType(), nullable=False, server_default="{}"),
            sa.Column("tool_allowlist", JSONType(), nullable=False, server_default="[]"),
            sa.Column("routing_preferences", JSONType(), nullable=False, server_default="{}"),
            sa.Column("current_task_id", GUID(), nullable=True),
            sa.Column("tasks_completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tasks_failed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("model_calls", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_used", sa.Float(), nullable=False, server_default="0"),
            sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
            *_audit_columns(),
        )
    if "mission_tasks" not in tables:
        op.create_table(
            "mission_tasks",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("parent_task_id", GUID(), sa.ForeignKey("mission_tasks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("objective", sa.Text(), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=False, server_default=""),
            sa.Column("task_type", sa.String(80), nullable=False, server_default="mission_research"),
            sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("depth", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "assigned_agent_id",
                GUID(),
                sa.ForeignKey("mission_agents.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("depends_on_task_ids", JSONType(), nullable=False, server_default="[]"),
            sa.Column("blocked_reason", sa.String(2000), nullable=True),
            sa.Column("required_capabilities", JSONType(), nullable=False, server_default="[]"),
            sa.Column("required_tools", JSONType(), nullable=False, server_default="[]"),
            sa.Column("required_memory_scope", JSONType(), nullable=False, server_default="{}"),
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lease_owner", sa.String(255), nullable=True),
            sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("execution_attempt_id", sa.String(64), nullable=True),
            sa.Column("idempotency_key", sa.String(255), nullable=True),
            sa.Column("input_payload", JSONType(), nullable=False, server_default="{}"),
            sa.Column("output_payload", JSONType(), nullable=False, server_default="{}"),
            sa.Column("artifacts", JSONType(), nullable=False, server_default="[]"),
            sa.Column("findings", JSONType(), nullable=False, server_default="[]"),
            sa.Column("task_summary", sa.Text(), nullable=True),
            sa.Column("model_name", sa.String(500), nullable=True),
            sa.Column("model_provider", sa.String(100), nullable=True),
            sa.Column("routing_reason", sa.String(2000), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_wake_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_code", sa.String(100), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            *_audit_columns(),
        )
    if "mission_events" not in tables:
        op.create_table(
            "mission_events",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", GUID(), nullable=True),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
            sa.Column("summary", sa.String(2000), nullable=False),
            sa.Column("event_data", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, default=now),
        )
    if "mission_approvals" not in tables:
        op.create_table(
            "mission_approvals",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", GUID(), nullable=True),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("action_type", sa.String(100), nullable=False),
            sa.Column("tool_name", sa.String(255), nullable=True),
            sa.Column("arguments_redacted", JSONType(), nullable=False, server_default="{}"),
            sa.Column("reason", sa.String(2000), nullable=False),
            sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolved_by", sa.String(255), nullable=True),
            sa.Column("resolution", sa.String(1000), nullable=True),
            *_audit_columns(),
        )
    if "mission_learning" not in tables:
        op.create_table(
            "mission_learning",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", GUID(), nullable=True),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("learning_type", sa.String(40), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("generalized_content", sa.Text(), nullable=True),
            sa.Column("evidence", JSONType(), nullable=False, server_default="{}"),
            sa.Column("source_refs", JSONType(), nullable=False, server_default="[]"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("novelty", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("reusability", sa.Float(), nullable=False, server_default="0.5"),
            sa.Column("memory_scope", sa.String(40), nullable=False, server_default="personal"),
            sa.Column("status", sa.String(30), nullable=False, server_default="candidate"),
            sa.Column("consolidated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("memory_id", GUID(), nullable=True),
            *_audit_columns(),
        )
    if "mission_artifacts" not in tables:
        op.create_table(
            "mission_artifacts",
            sa.Column("id", GUID(), primary_key=True),
            sa.Column("mission_id", GUID(), sa.ForeignKey("missions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", GUID(), nullable=True),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("artifact_type", sa.String(80), nullable=False),
            sa.Column("filename", sa.String(500), nullable=False),
            sa.Column("workspace_path", sa.String(2000), nullable=False),
            sa.Column("mime_type", sa.String(255), nullable=True),
            sa.Column("size", sa.Integer(), nullable=True),
            sa.Column("hash", sa.String(128), nullable=True),
            sa.Column("description", sa.String(2000), nullable=True),
            *_audit_columns(),
        )

    # Explicit, portable indexes used by the supervisor and Mission Control.
    indexes = {
        "ix_missions_supermode_status": ("missions", ["is_supermode", "status"]),
        "ix_missions_owner_status": ("missions", ["owner_user_id", "status"]),
        "ix_missions_next_wake_at": ("missions", ["next_wake_at"]),
        "ix_mission_tasks_mission_status": ("mission_tasks", ["mission_id", "status"]),
        "ix_mission_tasks_status_wake": ("mission_tasks", ["status", "next_wake_at"]),
        "ix_mission_tasks_lease": ("mission_tasks", ["lease_expires_at"]),
        "ix_mission_agents_mission_status": ("mission_agents", ["mission_id", "status"]),
        "ix_mission_events_mission_created": ("mission_events", ["mission_id", "created_at"]),
        "ix_mission_approvals_mission_status": ("mission_approvals", ["mission_id", "status"]),
        "ix_mission_learning_mission_status": ("mission_learning", ["mission_id", "status"]),
    }
    for name, (table, columns) in indexes.items():
        if table in set(sa.inspect(bind).get_table_names()):
            existing = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    for table in (
        "mission_artifacts",
        "mission_learning",
        "mission_approvals",
        "mission_events",
        "mission_tasks",
        "mission_agents",
        "mission_plans",
    ):
        op.drop_table(table)
    # Supermode mission columns are intentionally retained on downgrade to
    # preserve durable mission provenance and avoid destructive data loss.
