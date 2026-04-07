"""Skill schemas — skill definitions, installation, and import."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import RiskLevel, ShogunBase, SkillStatus, SkillType


# ── Skill Source ─────────────────────────────────────────────


class SkillSourceCreate(ShogunBase):
    """Request body for adding a skill source repository."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    source_type: str = "remote_repo"
    base_url: str | None = None
    default_enabled: bool = True
    trust_level: str = "trusted"
    sync_policy: str = "manual_refresh"


class SkillSourceResponse(ShogunBase):
    """Response model for a skill source."""

    id: uuid.UUID
    name: str
    slug: str
    source_type: str
    base_url: str | None = None
    default_enabled: bool
    trust_level: str
    sync_policy: str
    status: str
    created_at: datetime
    updated_at: datetime


# ── Skill Definition ─────────────────────────────────────────


class SkillManifest(ShogunBase):
    """Parsed manifest for a skill."""

    entrypoint: str = "SKILL.md"
    permissions_requested: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    compatibility: dict[str, bool] = Field(default_factory=dict)


class SkillResponse(ShogunBase):
    """Response model for a skill definition."""

    id: uuid.UUID
    source_id: uuid.UUID | None = None
    name: str
    slug: str
    version: str
    skill_type: SkillType
    manifest: SkillManifest
    risk_score: float = 0.0
    trust_score: int = 0
    status: SkillStatus
    hash: str | None = None
    local_path: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Skill Import ─────────────────────────────────────────────


class SkillImportRequest(ShogunBase):
    """Request body for importing a skill."""

    source_type: str = "remote_repo"
    source_url: str
    install_after_import: bool = False


# ── Skill Install ────────────────────────────────────────────


class SkillInstallRequest(ShogunBase):
    """Request body for installing a skill."""

    target_type: str = "global"
    target_id: uuid.UUID | None = None
    auto_update: bool = False
    quarantine_first: bool = True


class SkillInstallationResponse(ShogunBase):
    """Response model for a skill installation record."""

    id: uuid.UUID
    skill_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID | None = None
    status: str
    installed_version: str
    auto_update: bool
    quarantine_status: str
    last_health_check_at: datetime | None = None
    installed_at: datetime
    installed_by: str
