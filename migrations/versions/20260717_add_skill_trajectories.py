"""Add Order 10 skill trajectory evidence tables.

Revision ID: 20260717trajectory
Revises: 20260717skills
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260717trajectory"
down_revision = "20260717skills"
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
        "skill_candidate_retrievals",
        sa.Column("id", GUID(), primary_key=True), sa.Column("run_id", sa.String(255)),
        sa.Column("stack_run_id", GUID()), sa.Column("step_run_id", GUID()),
        sa.Column("flow_id", sa.String(255)), sa.Column("node_id", sa.String(255)),
        sa.Column("agent_id", sa.String(255)), sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("task_summary", sa.Text(), nullable=False),
        sa.Column("candidate_skill_ids", JSONType(), nullable=False),
        sa.Column("retrieval_scores", JSONType(), nullable=False),
        sa.Column("selected_skill_ids", JSONType(), nullable=False),
        sa.Column("rejected_skill_ids", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_candidate_retrieval_run", "skill_candidate_retrievals", ["run_id", "created_at"])

    op.create_table(
        "skill_episodes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("active_skill_run_id", GUID(), sa.ForeignKey("active_skill_runs.id", ondelete="SET NULL")),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_version", sa.String(80), nullable=False), sa.Column("run_id", sa.String(255)),
        sa.Column("stack_run_id", GUID()), sa.Column("step_run_id", GUID()),
        sa.Column("flow_id", sa.String(255)), sa.Column("node_id", sa.String(255)),
        sa.Column("agent_id", sa.String(255)), sa.Column("model_id", sa.String(255)),
        sa.Column("model_profile", sa.String(100)), sa.Column("posture", sa.String(30), nullable=False),
        sa.Column("task_summary", sa.Text(), nullable=False), sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column("injection_mode", sa.String(50), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_episode_run", "skill_episodes", ["run_id", "created_at"])
    op.create_index("ix_skill_episode_skill", "skill_episodes", ["skill_id", "created_at"])
    op.create_index("ix_skill_episode_active_run", "skill_episodes", ["active_skill_run_id"])

    op.create_table(
        "skill_trajectories",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_episode_id", GUID(), sa.ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_version", sa.String(80), nullable=False), sa.Column("run_id", sa.String(255)),
        sa.Column("stack_run_id", GUID()), sa.Column("step_run_id", GUID()),
        sa.Column("trajectory_json", JSONType(), nullable=False),
        sa.Column("final_outcome", sa.String(30), nullable=False),
        sa.Column("contribution", sa.String(30), nullable=False), sa.Column("score", sa.Float(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_trajectory_run", "skill_trajectories", ["run_id", "created_at"])
    op.create_index("ix_skill_trajectory_skill", "skill_trajectories", ["skill_id", "created_at"])
    op.create_index("ix_skill_trajectory_outcome", "skill_trajectories", ["final_outcome", "score"])

    op.create_table(
        "skill_tool_links", sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_episode_id", GUID(), sa.ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_call_id", sa.String(255)), sa.Column("tool_name", sa.String(255), nullable=False),
        sa.Column("tool_input_summary", sa.Text(), nullable=False), sa.Column("tool_output_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_tool_link_episode", "skill_tool_links", ["skill_episode_id", "created_at"])

    op.create_table(
        "skill_verification_links", sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_episode_id", GUID(), sa.ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("verification_id", sa.String(255)), sa.Column("verification_type", sa.String(100), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=False), sa.Column("observed_result", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("score", sa.Float(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_verification_episode", "skill_verification_links", ["skill_episode_id", "created_at"])

    op.create_table(
        "skill_outcome_scores", sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_episode_id", GUID(), sa.ForeignKey("skill_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_version", sa.String(80), nullable=False), sa.Column("run_id", sa.String(255)),
        sa.Column("stack_run_id", GUID()), sa.Column("score", sa.Float(), nullable=False),
        sa.Column("score_type", sa.String(50), nullable=False), sa.Column("scoring_method", sa.String(80), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False), sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_outcome_score_skill", "skill_outcome_scores", ["skill_id", "created_at"])

    op.create_table(
        "skill_improvement_candidates", sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_version", sa.String(80), nullable=False),
        sa.Column("based_on_trajectory_id", GUID(), sa.ForeignKey("skill_trajectories.id", ondelete="SET NULL")),
        sa.Column("issue_type", sa.String(100), nullable=False), sa.Column("observed_problem", sa.Text(), nullable=False),
        sa.Column("suggested_improvement", sa.Text(), nullable=False), sa.Column("validation_idea", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False), *_audit_columns(),
    )
    op.create_index("ix_skill_improvement_skill", "skill_improvement_candidates", ["skill_id", "status", "created_at"])


def downgrade() -> None:
    for table in [
        "skill_improvement_candidates", "skill_outcome_scores", "skill_verification_links",
        "skill_tool_links", "skill_trajectories", "skill_episodes", "skill_candidate_retrievals",
    ]:
        op.drop_table(table)
