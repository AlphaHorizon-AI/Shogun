"""Minimal Agent ORM model stub so legacy flow references resolve cleanly."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class Agent(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(200), default="assistant")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    routing_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="idle")
    config: Mapped[dict[str, Any]] = mapped_column(JSONType(), default=dict)
