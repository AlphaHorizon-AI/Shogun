"""Mission schemas — tasks and execution units."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import MissionPriority, MissionStatus, MissionType, ShogunBase


class MissionCreate(ShogunBase):
    """Request body for creating a mission."""

    mission_type: MissionType
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    priority: MissionPriority = MissionPriority.MEDIUM
    assigned_agent_id: uuid.UUID | None = None
    parent_mission_id: uuid.UUID | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)


class MissionResponse(ShogunBase):
    """Response model for a mission."""

    id: uuid.UUID
    mission_type: MissionType
    title: str
    description: str | None = None
    status: MissionStatus
    priority: MissionPriority
    requested_by: str
    assigned_agent_id: uuid.UUID | None = None
    parent_mission_id: uuid.UUID | None = None
    root_mission_id: uuid.UUID | None = None
    input_payload: dict[str, Any]
    output_summary: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
