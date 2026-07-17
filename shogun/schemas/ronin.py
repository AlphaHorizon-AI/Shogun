"""Ronin Pydantic schemas — API request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from shogun.schemas.common import ShogunBase


# ── Session schemas ──────────────────────────────────────────────────


class RoninSessionCreate(ShogunBase):
    """Create a new Ronin desktop session."""
    name: str = "Ronin Session"
    agent_id: uuid.UUID | None = None
    posture: str = "observe_only"
    komainu_level: int = 1


class RoninSessionResponse(ShogunBase):
    """Ronin session details for API responses."""
    id: uuid.UUID
    name: str
    agent_id: uuid.UUID | None = None
    posture: str
    status: str
    environment_type: str
    os_type: str
    os_version: str | None = None
    hostname: str | None = None
    machine_id: str | None = None
    is_disposable: bool = False
    last_screenshot_path: str | None = None
    last_action: str | None = None
    last_action_at: datetime | None = None
    current_app: str | None = None
    current_app_trust: str | None = None
    action_count: int = 0
    komainu_level: int = 1
    created_at: datetime
    updated_at: datetime


# ── Action schemas ───────────────────────────────────────────────────


class RoninActionRequest(ShogunBase):
    """Execute a Ronin action."""
    action_type: str  # e.g. "desktop.click", "browser.open"
    target: str | None = None
    value: str | None = None
    reason: str = ""
    session_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoninActionResult(ShogunBase):
    """Result of a Ronin action execution."""
    status: str
    action_type: str
    target: str | None = None
    result_data: dict[str, Any] = Field(default_factory=dict)
    screenshot_before: str | None = None
    screenshot_after: str | None = None
    confidence: float | None = None
    verified: bool = False
    error: str | None = None
    duration_ms: int | None = None
    approval_id: str | None = None


# ── Approval schemas ─────────────────────────────────────────────────


class RoninApprovalRequest(ShogunBase):
    """Respond to a pending approval."""
    decision: str  # "approved" | "denied"
    decided_by: str = "operator"


class RoninApprovalResponse(ShogunBase):
    """Pending approval details."""
    id: str
    agent_id: str | None = None
    session_id: str | None = None
    action_type: str
    target: str | None = None
    reason: str
    risk_level: str
    app_name: str | None = None
    app_trust: str | None = None
    screenshot_path: str | None = None
    created_at: str
    status: str


# ── Status & info schemas ───────────────────────────────────────────


class RoninStatusResponse(ShogunBase):
    """Ronin system status."""
    ronin_enabled: bool = False
    ronin_posture: str = "disabled"
    active_sessions: int = 0
    environment: dict[str, Any] = Field(default_factory=dict)
    komainu: dict[str, Any] = Field(default_factory=dict)
    pending_approvals: int = 0
    capabilities_count: int = 0
    active_tier: str = "tactical"
    desktop_available: bool = False
    desktop_active: bool = False
    visible_indicator: bool = True
    runtime: dict[str, Any] = Field(default_factory=dict)


class EnvironmentInfoResponse(ShogunBase):
    """Detected environment details."""
    environment_type: str
    os_type: str
    os_version: str | None = None
    hostname: str | None = None
    machine_id: str | None = None
    is_disposable: bool = False
    hypervisor: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AppTrustEntryResponse(ShogunBase):
    """App trust registry entry."""
    process: str | None = None
    process_pattern: str | None = None
    name: str
    trust_level: str
    platform: str = "all"


class RoninCapabilityResponse(ShogunBase):
    """Registered capability."""
    name: str
    category: str
    risk_level: str
    requires_approval: bool = False
    description: str = ""
    posture_minimum: str
    app_trust_minimum: str
    enabled: bool = True


class RoninNodeInfo(ShogunBase):
    """Ronin node info for Gensui fleet visibility."""
    node_type: str = "ronin"
    hostname: str | None = None
    machine_id: str | None = None
    os: str | None = None
    os_version: str | None = None
    environment_type: str | None = None
    posture: str | None = None
    active_sessions: int = 0
    current_app: str | None = None
    current_app_trust: str | None = None
    current_action: str | None = None
    komainu_status: str = "inactive"
    approval_queue_size: int = 0
    uptime_seconds: int = 0
