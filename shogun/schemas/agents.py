"""Agent schemas — Shogun and Samurai agent definitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from shogun.schemas.common import AgentStatus, AgentType, ShogunBase, SpawnPolicy


class MemoryScope(ShogunBase):
    """Defines which memory types an agent has access to."""

    episodic: bool = True
    semantic: bool = True
    procedural: bool = True
    persona: bool = True
    skills: bool = True


class AgentCreate(ShogunBase):
    """Request body for creating a new agent (Shogun or Samurai)."""

    agent_type: AgentType
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    persona_id: uuid.UUID | None = None
    kaizen_profile_id: uuid.UUID | None = None
    security_policy_id: uuid.UUID | None = None
    model_routing_profile_id: uuid.UUID | None = None
    memory_scope: MemoryScope = Field(default_factory=MemoryScope)
    spawn_policy: SpawnPolicy = SpawnPolicy.MANUAL
    parent_agent_id: uuid.UUID | None = None
    role_id: uuid.UUID | None = None
    avatar_url: str | None = "/shogun-avatar.png"
    bushido_settings: dict = Field(default_factory=lambda: {"nightly_consolidation": True, "weekly_performance_audit": True, "skill_health_check": True, "persona_drift_check": False})
    tags: list[str] = Field(default_factory=list)


class AgentUpdate(ShogunBase):
    """Request body for updating an agent (partial)."""

    name: str | None = None
    description: str | None = None
    persona_id: uuid.UUID | None = None
    kaizen_profile_id: uuid.UUID | None = None
    security_policy_id: uuid.UUID | None = None
    model_routing_profile_id: uuid.UUID | None = None
    memory_scope: MemoryScope | None = None
    spawn_policy: SpawnPolicy | None = None
    avatar_url: str | None = None
    bushido_settings: dict | None = None
    tags: list[str] | None = None


class AgentResponse(ShogunBase):
    """Response model for an agent."""

    id: uuid.UUID
    agent_type: AgentType
    name: str
    slug: str
    description: str | None = None
    status: AgentStatus
    persona_id: uuid.UUID | None = None
    kaizen_profile_id: uuid.UUID | None = None
    security_policy_id: uuid.UUID | None = None
    model_routing_profile_id: uuid.UUID | None = None
    memory_scope: MemoryScope
    spawn_policy: SpawnPolicy
    is_primary: bool = False
    parent_agent_id: uuid.UUID | None = None
    avatar_url: str | None = None
    bushido_settings: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    last_heartbeat_at: datetime | None = None
    samurai_profile: SamuraiProfileResponse | None = None
    created_at: datetime
    updated_at: datetime


class SamuraiRoleInline(ShogunBase):
    """Lightweight inline model for nested samurai role serialization."""

    id: uuid.UUID
    slug: str
    name: str
    purpose: str
    description: str | None = None


class SamuraiProfileCreate(ShogunBase):
    """Request body for creating/updating a Samurai capability profile."""

    role: str | None = None
    role_id: uuid.UUID | None = None
    specializations: list[str] = Field(default_factory=list)
    allowed_task_types: list[str] = Field(default_factory=list)
    blocked_task_types: list[str] = Field(default_factory=list)
    max_parallel_jobs: int = Field(default=2, ge=1, le=20)
    auto_spawnable: bool = False


class SamuraiProfileResponse(ShogunBase):
    """Response model for a Samurai capability profile."""

    id: uuid.UUID
    agent_id: uuid.UUID
    role: str
    role_id: uuid.UUID | None = None
    samurai_role: SamuraiRoleInline | None = None
    specializations: list[str]
    allowed_task_types: list[str]
    blocked_task_types: list[str]
    max_parallel_jobs: int
    auto_spawnable: bool
    created_at: datetime
    updated_at: datetime
