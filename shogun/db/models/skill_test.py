"""Skill validation test ORM model — Order 15."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class SkillTest(Base, UUIDMixin, AuditMixin):
    """A stored validation test definition + last result for a skill version."""

    __tablename__ = "skill_tests"
    __table_args__ = (Index("ix_skill_test_skill", "skill_id", "version"),)

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    test_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="output_quality"
    )
    test_definition_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    last_result_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
