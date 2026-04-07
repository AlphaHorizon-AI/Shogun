"""Model definition ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class ModelDefinition(Base, UUIDMixin, AuditMixin):
    __tablename__ = "models"

    provider_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("model_providers.id"), nullable=False)
    model_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)
    modality: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cost_profile: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    latency_profile: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="available")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONType(), nullable=False, default=dict)

    provider = relationship("ModelProvider", lazy="joined")
