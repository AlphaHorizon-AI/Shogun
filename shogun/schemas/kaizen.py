"""Kaizen schemas — constitutional layer profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import ShogunBase


class BehaviorRule(ShogunBase):
    """A single behavioral rule within a Kaizen profile."""

    rule: str
    severity: str = "medium"


class DelegationRule(ShogunBase):
    """A delegation routing rule within a Kaizen profile."""

    task_type: str
    preferred_samurai_role: str


class KaizenContent(ShogunBase):
    """Structured content of a Kaizen constitutional profile."""

    priorities: list[str] = Field(default_factory=list)
    behavior_rules: list[BehaviorRule] = Field(default_factory=list)
    delegation_rules: list[DelegationRule] = Field(default_factory=list)


class KaizenProfileCreate(ShogunBase):
    """Request body for creating a new Kaizen profile version."""

    target_type: str = Field(..., pattern="^(shogun|samurai)$")
    target_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    content: KaizenContent
    change_summary: str | None = None


class KaizenProfileResponse(ShogunBase):
    """Response model for a Kaizen profile."""

    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    name: str
    version: int
    status: str
    content: KaizenContent
    change_summary: str | None = None
    approved_by: str | None = None
    created_at: datetime
    updated_at: datetime


class KaizenRollbackRequest(ShogunBase):
    """Request body for rolling back a Kaizen profile to a prior version."""

    reason: str | None = None
