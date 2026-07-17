"""Task-aware model registry, routing decisions, and usage telemetry."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class ModelRegistryEntry(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_registry"
    __table_args__ = (
        Index("ix_model_registry_model_provider", "model_id", "provider_id", unique=True),
        Index("ix_model_registry_enabled", "enabled", "cost_tier", "quality_tier"),
    )

    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("model_providers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    connection_type: Mapped[str] = mapped_column(String(30), nullable=False, default="api")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    capabilities: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    quality_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    cost_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    latency_tier: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    context_window: Mapped[int] = mapped_column(Integer, nullable=False, default=8192)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    local: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    role_tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class ModelRoutingDecision(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_routing_decisions"
    __table_args__ = (
        Index("ix_model_routing_decisions_run", "run_id", "created_at"),
        Index("ix_model_routing_decisions_stack", "stack_run_id", "created_at"),
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    step_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_type: Mapped[str] = mapped_column(String(80), nullable=False)
    complexity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    active_profile: Mapped[str] = mapped_column(String(100), nullable=False)
    selected_registry_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    selected_model: Mapped[str] = mapped_column(String(255), nullable=False)
    selected_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    fallback_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_latency_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_vision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_tool_use: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_json_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class ModelUsageEvent(Base, UUIDMixin):
    __tablename__ = "model_usage_events"
    __table_args__ = (
        Index("ix_model_usage_decision", "routing_decision_id", "created_at"),
        Index("ix_model_usage_stack", "stack_run_id", "created_at"),
    )

    routing_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("model_routing_decisions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    stack_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
