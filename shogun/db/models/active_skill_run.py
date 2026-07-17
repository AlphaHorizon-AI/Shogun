"""Minimal active-skill usage records (Order 9 bridge to trajectories)."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class ActiveSkillRun(Base, UUIDMixin, AuditMixin):
    __tablename__ = "active_skill_runs"
    __table_args__ = (
        Index("ix_active_skill_runs_run", "run_id", "created_at"),
        Index("ix_active_skill_runs_stack_step", "stack_run_id", "step_run_id"),
        Index("ix_active_skill_runs_skill", "skill_id", "created_at"),
    )

    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    step_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False)
    activation_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="advisory")
    usage_location: Mapped[str] = mapped_column(String(50), nullable=False, default="chat")
    injected_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posture: Mapped[str] = mapped_column(String(30), nullable=False, default="guarded")
    conflict_notes: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    outcome_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
