"""Samurai Role schemas — functional template definitions."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from shogun.schemas.common import ShogunBase


class SamuraiRoleCreate(ShogunBase):
    """Request body for creating a new Samurai Role."""

    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    purpose: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class SamuraiRoleUpdate(ShogunBase):
    """Request body for updating an existing Samurai Role (partial)."""

    name: str | None = None
    purpose: str | None = None
    description: str | None = None
    is_active: bool | None = None


class SamuraiRoleResponse(ShogunBase):
    """Response model for a Samurai Role."""

    id: uuid.UUID
    slug: str
    name: str
    purpose: str
    description: str | None = None
    is_builtin: bool = True
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
