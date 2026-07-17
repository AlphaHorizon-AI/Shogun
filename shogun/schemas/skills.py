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
    description: str = ""
    source: str = "local"
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    requires_tools: list[str] = Field(default_factory=list)
    minimum_posture: str = "guarded"
    risk_tier: str = "low"
    priority: int = 50
    conflict_group: str | None = None
    model_hint: str | None = None


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
    exam_status: str = "untested"
    tags: list[str] = Field(default_factory=list)
    triggers: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    requires_tools: list[str] = Field(default_factory=list)
    minimum_posture: str = "guarded"
    risk_tier: str = "low"
    priority: int = 50
    conflict_group: str | None = None
    model_hint: str | None = None
    max_context_tokens: int = 600
    activation_mode: str = "advisory"
    body_text: str | None = None
    brief_text: str | None = None
    verification_checklist: list[str] = Field(default_factory=list)
    embedding_id: str | None = None
    last_used_at: datetime | None = None
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
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


class SkillActivationRequest(ShogunBase):
    run_id: str | None = None
    stack_run_id: uuid.UUID | None = None
    step_run_id: uuid.UUID | None = None
    objective: str = Field(..., min_length=1)
    context: str = ""
    posture: str = "guarded"
    available_tools: list[str] = Field(default_factory=list)
    max_skills: int | None = Field(default=None, ge=1, le=20)
    usage_location: str = "chat"
    explicit_skill_ids: list[uuid.UUID] = Field(default_factory=list)
    ide_enabled: bool = False
    activation_phase: str = "execution"


class SkillOutcomeRequest(ShogunBase):
    active_skill_run_id: uuid.UUID
    outcome: str
    outcome_summary: str | None = None


class ActiveSkillRunResponse(ShogunBase):
    id: uuid.UUID
    run_id: str | None = None
    stack_run_id: uuid.UUID | None = None
    step_run_id: uuid.UUID | None = None
    skill_id: uuid.UUID
    skill_name: str | None = None
    activation_reason: str
    relevance_score: float
    activation_mode: str
    usage_location: str
    injected_tokens: int
    posture: str
    conflict_notes: list[str] = Field(default_factory=list)
    outcome: str
    outcome_summary: str | None = None
    created_at: datetime


class SkillActivationItem(ShogunBase):
    active_skill_run_id: uuid.UUID | None = None
    skill_id: uuid.UUID
    name: str
    skill_type: str
    relevance_score: float
    activation_reason: str
    activation_mode: str
    brief: str
    injected_tokens: int
    verification_checklist: list[str] = Field(default_factory=list)
    model_hint: str | None = None


class SkillCandidateItem(ShogunBase):
    skill_id: uuid.UUID
    name: str
    relevance_score: float
    reason: str
    blocked_reason: str | None = None


class SkillActivationResponse(ShogunBase):
    run_id: str
    context_block: str
    total_injected_tokens: int
    active_skills: list[SkillActivationItem] = Field(default_factory=list)
    considered_skills: list[SkillCandidateItem] = Field(default_factory=list)
    blocked_skills: list[SkillCandidateItem] = Field(default_factory=list)
    conflict_notes: list[str] = Field(default_factory=list)
