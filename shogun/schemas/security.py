"""Security schemas — policies, permissions, and simulation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import SecurityTier, ShogunBase


class FilesystemPermissions(ShogunBase):
    mode: str = "scoped"
    allowed_paths: list[str] = Field(default_factory=list)
    allow_home_access: bool = False
    allow_arbitrary_paths: bool = False


class NetworkPermissions(ShogunBase):
    mode: str = "allowlist"
    allowed_domains: list[str] = Field(default_factory=list)
    allow_arbitrary_requests: bool = False


class ShellPermissions(ShogunBase):
    enabled: bool = False
    allowed_binaries: list[str] = Field(default_factory=list)


class SkillPermissions(ShogunBase):
    allow_auto_install: bool = False
    require_approval: bool = True
    allow_untrusted: bool = False


class SubagentPermissions(ShogunBase):
    allow_spawn: bool = True
    max_active: int = 5
    allow_auto_spawn: bool = False


class MemoryPermissions(ShogunBase):
    allow_write: bool = True
    allow_bulk_delete: bool = False


class CommsPermissions(ShogunBase):
    allow_read_email: bool = True
    allow_send_email: bool = True
    allow_read_calendar: bool = True
    allow_create_events: bool = True
    allow_list_cron: bool = True
    allow_manage_cron: bool = False


class PolicyPermissions(ShogunBase):
    """Full permissions block for a security policy."""

    filesystem: FilesystemPermissions = Field(default_factory=FilesystemPermissions)
    network: NetworkPermissions = Field(default_factory=NetworkPermissions)
    shell: ShellPermissions = Field(default_factory=ShellPermissions)
    skills: SkillPermissions = Field(default_factory=SkillPermissions)
    subagents: SubagentPermissions = Field(default_factory=SubagentPermissions)
    memory: MemoryPermissions = Field(default_factory=MemoryPermissions)
    comms: CommsPermissions = Field(default_factory=CommsPermissions)
    agentflow: dict[str, Any] = Field(default_factory=dict)
    flow_stack: dict[str, Any] = Field(default_factory=dict)
    visual_intake: dict[str, Any] = Field(default_factory=dict)
    ide_mode: dict[str, Any] = Field(default_factory=dict)


class SecurityPolicyCreate(ShogunBase):
    """Request body for creating a security policy."""

    name: str = Field(..., min_length=1, max_length=255)
    tier: SecurityTier
    description: str | None = None
    permissions: PolicyPermissions = Field(default_factory=PolicyPermissions)
    kill_switch_enabled: bool = True
    dry_run_supported: bool = True


class SecurityPolicyUpdate(ShogunBase):
    """Request body for updating a security policy."""

    name: str | None = None
    tier: SecurityTier | None = None
    description: str | None = None
    permissions: PolicyPermissions | None = None
    kill_switch_enabled: bool | None = None
    dry_run_supported: bool | None = None


class SecurityPolicyResponse(ShogunBase):
    """Response model for a security policy."""

    id: uuid.UUID
    name: str
    tier: SecurityTier
    description: str | None = None
    permissions: PolicyPermissions
    kill_switch_enabled: bool
    dry_run_supported: bool
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class PermissionSimulateRequest(ShogunBase):
    """Request body for simulating permissions for a proposed action."""

    agent_id: uuid.UUID
    action: dict[str, Any]


class PermissionSimulateResponse(ShogunBase):
    """Response model for a permission simulation."""

    allowed: bool
    warnings: list[str] = Field(default_factory=list)
    denials: list[str] = Field(default_factory=list)


class SecurityAssignRequest(ShogunBase):
    """Request body for assigning a security policy to an agent."""

    agent_id: uuid.UUID
    security_policy_id: uuid.UUID


class SecurityPostureResponse(ShogunBase):
    """Response model for the current security posture summary."""

    active_tier: SecurityTier
    filesystem_mode: str
    network_mode: str
    shell_enabled: bool
    skill_auto_install: bool
    max_active_subagents: int
    kill_switch_enabled: bool
    kill_switch_active: bool = False
    ide_enabled: bool = False
    comms_read_email: bool = True
    comms_send_email: bool = True
    comms_read_calendar: bool = True
    comms_create_events: bool = True
    comms_list_cron: bool = True
    comms_manage_cron: bool = False
    # Mado browser automation
    mado_enabled: bool = True
    mado_headless_only: bool = True
    mado_max_sessions: int = 3
    mado_autonomous_browsing: bool = False
    mado_downloads_enabled: bool = True
    mado_uploads_enabled: bool = True
    # Ronin desktop automation
    ronin_enabled: bool = False
    ronin_posture: str = "disabled"
    ronin_max_sessions: int = 0
    ronin_screenshots_enabled: bool = False
    ronin_mouse_enabled: bool = False
    ronin_keyboard_enabled: bool = False
    ronin_native_apps_enabled: bool = False
    ronin_shell_commands: bool = False
    ronin_admin_escalation: bool = False
    ronin_credential_entry: str = "blocked"
    ronin_file_deletion: str = "blocked"
    ronin_external_uploads: str = "blocked"
    ronin_install_software: str = "blocked"
    ronin_komainu_level: int = 1
    ronin_environment_policy: str = "any"

