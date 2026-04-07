"""Bushido schemas — reflection, maintenance, and self-improvement."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import (
    BushidoJobStatus,
    BushidoJobType,
    MemoryType,
    RiskLevel,
    ShogunBase,
    TriggerMode,
)


# ── Bushido Job ──────────────────────────────────────────────


class BushidoScope(ShogunBase):
    """Scope for a Bushido run."""

    agent_ids: list[uuid.UUID] = Field(default_factory=list)
    memory_types: list[MemoryType] = Field(default_factory=list)


class BushidoRunRequest(ShogunBase):
    """Request body for triggering a Bushido run."""

    job_type: BushidoJobType
    scope: BushidoScope = Field(default_factory=BushidoScope)


class BushidoJobResponse(ShogunBase):
    """Response model for a Bushido job."""

    id: uuid.UUID
    job_type: BushidoJobType
    status: BushidoJobStatus
    scope: BushidoScope
    trigger_mode: TriggerMode
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    output_ref: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


# ── Bushido Recommendation ───────────────────────────────────


class BushidoRecommendationResponse(ShogunBase):
    """Response model for a Bushido recommendation."""

    id: uuid.UUID
    job_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    recommendation_type: str
    title: str
    description: str
    confidence: float
    risk_level: RiskLevel
    approval_required: bool
    status: str
    created_at: datetime
    updated_at: datetime


# ── Bushido Schedule ─────────────────────────────────────────


class BushidoScheduleUpdate(ShogunBase):
    """Request body for updating the Bushido schedule."""

    nightly_consolidation: bool = True
    weekly_performance_audit: bool = True
    skill_health_check: bool = True
    persona_drift_check: bool = False
