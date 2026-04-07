"""Persona schemas — behavioral profile definitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from shogun.schemas.common import (
    LevelEnum,
    MemoryStyle,
    SecurityBias,
    ShogunBase,
    Tone,
    ToolUsageStyle,
)


class PersonaCreate(ShogunBase):
    """Request body for creating a new persona."""

    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tone: Tone
    risk_tolerance: LevelEnum
    autonomy: LevelEnum
    verbosity: LevelEnum
    planning_depth: LevelEnum
    tool_usage_style: ToolUsageStyle
    security_bias: SecurityBias
    memory_style: MemoryStyle
    default_model_routing_profile_id: uuid.UUID | None = None


class PersonaUpdate(ShogunBase):
    """Request body for updating an existing persona (partial)."""

    name: str | None = None
    description: str | None = None
    tone: Tone | None = None
    risk_tolerance: LevelEnum | None = None
    autonomy: LevelEnum | None = None
    verbosity: LevelEnum | None = None
    planning_depth: LevelEnum | None = None
    tool_usage_style: ToolUsageStyle | None = None
    security_bias: SecurityBias | None = None
    memory_style: MemoryStyle | None = None
    default_model_routing_profile_id: uuid.UUID | None = None
    is_active: bool | None = None


class PersonaResponse(ShogunBase):
    """Response model for a persona."""

    id: uuid.UUID
    slug: str
    name: str
    description: str | None = None
    tone: Tone
    risk_tolerance: LevelEnum
    autonomy: LevelEnum
    verbosity: LevelEnum
    planning_depth: LevelEnum
    tool_usage_style: ToolUsageStyle
    security_bias: SecurityBias
    memory_style: MemoryStyle
    default_model_routing_profile_id: uuid.UUID | None = None
    is_builtin: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
