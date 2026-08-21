"""Ronin Policy Schema — Pydantic models for posture, environment, trust, and capabilities.

These models define the type-safe structures used throughout Ronin for
security posture evaluation, environment detection, and action classification.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Enums ────────────────────────────────────────────────────────────


class RoninPostureLevel(str, Enum):
    """Ronin security posture levels — maps to Shogun security tiers."""

    DISABLED = "disabled"
    OBSERVE_ONLY = "observe_only"
    BROWSER_ONLY = "browser_only"
    DESKTOP_LIMITED = "desktop_limited"
    DESKTOP_FULL = "desktop_full"
    ADMIN_APPROVAL_REQUIRED = "admin_approval_required"


class EnvironmentType(str, Enum):
    """Execution environment type — detected at runtime."""

    PHYSICAL = "physical"
    VM = "vm"
    SANDBOX = "sandbox"
    REMOTE_DESKTOP = "remote_desktop"
    CITRIX = "citrix"
    CLOUD_WORKSPACE = "cloud_workspace"


class AppTrustLevel(str, Enum):
    """Application trust level — controls interaction permissions."""

    TRUSTED = "trusted"
    RESTRICTED = "restricted"
    SENSITIVE = "sensitive"
    FORBIDDEN = "forbidden"


class RiskLevel(str, Enum):
    """Risk classification for Ronin actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RoninPermissionGate(str, Enum):
    """Action semantics governed by Ronin's non-generic permission controls."""

    CREDENTIAL_ENTRY = "credential_entry"
    FILE_DELETION = "file_deletion"
    EXTERNAL_UPLOADS = "external_uploads"
    INSTALL_SOFTWARE = "install_software"
    ADMIN_ESCALATION = "admin_escalation"


class RoninGateDecision(str, Enum):
    """Tri-state decision for a semantic Ronin permission gate."""

    ALLOWED = "allowed"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"


class KomainuLevel(int, Enum):
    """Komainu (guardian) response level on human input detection."""

    PAUSE = 1
    TERMINATE = 2
    HARAKIRI = 3


class RoninSessionStatus(str, Enum):
    """Ronin desktop session lifecycle status."""

    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    CLOSED = "closed"


class RoninActionStatus(str, Enum):
    """Result status of a Ronin action execution."""

    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"
    APPROVAL_REQUIRED = "approval_required"
    TIMEOUT = "timeout"
    LOW_CONFIDENCE = "low_confidence"
    TARGET_NOT_FOUND = "target_not_found"
    POSTURE_DENIED = "posture_denied"
    APP_FORBIDDEN = "app_forbidden"
    ENVIRONMENT_DENIED = "environment_denied"
    KOMAINU_PAUSED = "komainu_paused"


# ── Models ───────────────────────────────────────────────────────────


class EnvironmentInfo(BaseModel):
    """Detected execution environment details."""

    environment_type: EnvironmentType = EnvironmentType.PHYSICAL
    os_type: str = "unknown"  # windows | macos | linux
    os_version: str | None = None
    hostname: str | None = None
    machine_id: str | None = None
    is_disposable: bool = False
    hypervisor: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class AppTrustEntry(BaseModel):
    """A single application in the trust registry."""

    process: str | None = None  # Exact process name (e.g. "code.exe")
    process_pattern: str | None = None  # Glob pattern (e.g. "*wallet*")
    name: str  # Human-readable name
    trust_level: AppTrustLevel = AppTrustLevel.RESTRICTED
    platform: str = "all"  # "all" | "windows" | "macos" | "linux"
    notes: str | None = None


class RoninCapability(BaseModel):
    """A registered Ronin action capability with risk metadata."""

    name: str  # e.g. "desktop.click"
    category: str  # "desktop" | "browser" | "os" | "app" | "ronin"
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    description: str = ""
    handler: str = ""  # Dotted path to handler function
    app_trust_minimum: AppTrustLevel = AppTrustLevel.TRUSTED
    posture_minimum: RoninPostureLevel = RoninPostureLevel.DESKTOP_LIMITED
    permission_gates: list[RoninPermissionGate] = Field(default_factory=list)
    enabled: bool = True


class PostureDecision(BaseModel):
    """Result of a posture guard evaluation."""

    allowed: bool
    reason: str
    approval_required: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    app_trust: AppTrustLevel | None = None
    environment: EnvironmentType | None = None


class RoninPermissions(BaseModel):
    """Ronin permission set — what the current posture allows."""

    ronin_enabled: bool = False
    ronin_posture: RoninPostureLevel = RoninPostureLevel.DISABLED
    ronin_max_sessions: int = 0
    ronin_screenshots_enabled: bool = False
    ronin_mouse_enabled: bool = False
    ronin_keyboard_enabled: bool = False
    ronin_native_apps_enabled: bool = False
    ronin_window_management_enabled: bool = False
    ronin_require_verification: bool = True
    ronin_require_high_risk_approval: bool = True
    ronin_block_critical_actions: bool = True
    ronin_protected_applications: list[str] = Field(default_factory=list)
    ronin_visible_indicator: bool = True
    ronin_shell_commands: bool = False
    ronin_admin_escalation: bool = False
    ronin_credential_entry: RoninGateDecision = RoninGateDecision.BLOCKED
    ronin_file_deletion: RoninGateDecision = RoninGateDecision.BLOCKED
    ronin_external_uploads: RoninGateDecision = RoninGateDecision.BLOCKED
    ronin_install_software: RoninGateDecision = RoninGateDecision.BLOCKED
    ronin_komainu_level: KomainuLevel = KomainuLevel.PAUSE
    ronin_environment_policy: str = "any"  # any | vm_only | sandbox_only


class RoninPolicy(BaseModel):
    """Complete Ronin policy definition for a posture level."""

    posture: RoninPostureLevel
    description: str = ""
    permissions: RoninPermissions = Field(default_factory=RoninPermissions)
    allowed_environments: list[EnvironmentType] = Field(
        default_factory=lambda: list(EnvironmentType)
    )
    blocked_app_categories: list[AppTrustLevel] = Field(
        default_factory=lambda: [AppTrustLevel.FORBIDDEN]
    )


class RoninAction(BaseModel):
    """An action request from a Shogun agent to Ronin."""

    agent_id: str
    session_id: str | None = None
    action_type: str  # e.g. "desktop.click", "browser.open"
    target: str | None = None  # e.g. "button:Install", CSS selector, image path
    value: str | None = None  # e.g. text to type, URL to open
    reason: str = ""
    risk_level: RiskLevel | None = None  # Override; auto-classified if None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RoninResult(BaseModel):
    """Result of executing a Ronin action."""

    status: RoninActionStatus
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
