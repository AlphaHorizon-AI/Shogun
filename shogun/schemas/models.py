"""Model schemas — providers, model definitions, and routing profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import (
    AuthType,
    CostProfile,
    HealthStatus,
    LatencyProfile,
    ProviderStatus,
    ProviderType,
    ShogunBase,
)


# ── Model Provider ───────────────────────────────────────────


class ModelProviderCreate(ShogunBase):
    """Request body for adding a model provider."""

    provider_type: ProviderType
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    base_url: str | None = None
    auth_type: AuthType = AuthType.API_KEY
    is_local: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class ModelProviderUpdate(ShogunBase):
    """Request body for updating a model provider."""

    name: str | None = None
    base_url: str | None = None
    auth_type: AuthType | None = None
    config: dict[str, Any] | None = None
    status: ProviderStatus | None = None


class ModelProviderResponse(ShogunBase):
    """Response model for a model provider."""

    id: uuid.UUID
    provider_type: ProviderType
    name: str
    slug: str
    base_url: str | None = None
    auth_type: AuthType
    is_local: bool
    status: ProviderStatus
    health_status: HealthStatus
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ── Model Definition ─────────────────────────────────────────


class ModelDefinitionResponse(ShogunBase):
    """Response model for a model definition."""

    id: uuid.UUID
    provider_id: uuid.UUID
    model_key: str
    display_name: str
    family: str | None = None
    modality: str = "text"
    context_window: int | None = None
    supports_tools: bool = False
    supports_json_mode: bool = False
    supports_vision: bool = False
    cost_profile: CostProfile = CostProfile.STANDARD
    latency_profile: LatencyProfile = LatencyProfile.MEDIUM
    status: str = "available"
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ── Model Routing Profile ────────────────────────────────────


class RoutingRule(ShogunBase):
    """A single task-to-model routing rule."""

    task_type: str
    primary_model_id: uuid.UUID
    fallback_model_ids: list[uuid.UUID] = Field(default_factory=list)
    latency_bias: str | None = None
    cost_bias: str | None = None


class ModelRoutingProfileCreate(ShogunBase):
    """Request body for creating a model routing profile."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    rules: list[RoutingRule] = Field(default_factory=list)
    is_default: bool = False


class ModelRoutingProfileUpdate(ShogunBase):
    """Request body for updating a model routing profile."""

    name: str | None = None
    description: str | None = None
    rules: list[RoutingRule] | None = None
    is_default: bool | None = None


class ModelRoutingProfileResponse(ShogunBase):
    """Response model for a model routing profile."""

    id: uuid.UUID
    name: str
    description: str | None = None
    rules: list[RoutingRule]
    is_default: bool
    created_at: datetime
    updated_at: datetime
