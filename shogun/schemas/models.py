"""Model schemas — providers, model definitions, and routing profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_serializer

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
    status: ProviderStatus = ProviderStatus.CONNECTED
    config: dict[str, Any] = Field(default_factory=dict)


class ModelProviderUpdate(ShogunBase):
    """Request body for updating a model provider."""

    name: str | None = None
    base_url: str | None = None
    auth_type: AuthType | None = None
    config: dict[str, Any] | None = None
    status: ProviderStatus | None = None


class ModelDiscoveryRequest(ShogunBase):
    """Discover models exposed by a configured or not-yet-saved provider."""

    provider_type: ProviderType
    base_url: str | None = None
    api_key: str | None = None
    provider_id: uuid.UUID | None = None


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

    @field_serializer("config")
    def serialize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Never return stored provider credentials through the control API."""

        sensitive = {"api_key", "token", "access_token", "refresh_token", "password", "secret"}

        def redact(value: Any) -> Any:
            if isinstance(value, dict):
                return {
                    key: "********" if key.casefold() in sensitive else redact(item)
                    for key, item in value.items()
                }
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value

        return redact(config)


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
    primary_model_id: uuid.UUID | str
    fallback_model_ids: list[uuid.UUID | str] = Field(default_factory=list)
    latency_bias: str | None = None
    cost_bias: str | None = None


class RoutingModelSettings(ShogunBase):
    """Generation controls scoped to one physical model in one profile."""

    temperature: float = Field(0.3, ge=0.0, le=2.0)


class ModelRoutingProfileCreate(ShogunBase):
    """Request body for creating a model routing profile."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    rules: list[RoutingRule] = Field(default_factory=list)
    model_settings: dict[str, RoutingModelSettings] = Field(default_factory=dict)
    is_default: bool = False


class ModelRoutingProfileUpdate(ShogunBase):
    """Request body for updating a model routing profile."""

    name: str | None = None
    description: str | None = None
    rules: list[RoutingRule] | None = None
    model_settings: dict[str, RoutingModelSettings] | None = None
    is_default: bool | None = None


class ModelRoutingProfileResponse(ShogunBase):
    """Response model for a model routing profile."""

    id: uuid.UUID
    name: str
    description: str | None = None
    rules: list[RoutingRule]
    model_settings: dict[str, RoutingModelSettings] = Field(default_factory=dict)
    is_default: bool
    created_at: datetime
    updated_at: datetime
