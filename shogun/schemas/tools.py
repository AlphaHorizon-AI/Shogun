"""Tool connector schemas — API/tool integration definitions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import (
    AuthType,
    ConnectorSource,
    ConnectorType,
    HealthStatus,
    ProviderStatus,
    RiskLevel,
    ShogunBase,
)


class ToolConnectorCreate(ShogunBase):
    """Request body for creating a tool connector."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    connector_type: ConnectorType
    source: ConnectorSource = ConnectorSource.MANUAL
    base_url: str | None = None
    auth_type: AuthType = AuthType.NONE
    scope: str | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    config: dict[str, Any] = Field(default_factory=dict)


class ToolConnectorUpdate(ShogunBase):
    """Request body for updating a tool connector."""

    name: str | None = None
    base_url: str | None = None
    auth_type: AuthType | None = None
    scope: str | None = None
    risk_level: RiskLevel | None = None
    config: dict[str, Any] | None = None
    status: ProviderStatus | None = None


class ToolConnectorResponse(ShogunBase):
    """Response model for a tool connector."""

    id: uuid.UUID
    name: str
    slug: str
    connector_type: ConnectorType
    source: ConnectorSource
    base_url: str | None = None
    status: ProviderStatus
    auth_type: AuthType
    scope: str | None = None
    risk_level: RiskLevel
    config: dict[str, Any]
    health_status: HealthStatus
    created_at: datetime
    updated_at: datetime
