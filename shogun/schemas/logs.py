"""Log and audit event schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import Severity, ShogunBase


class ExecutionEventResponse(ShogunBase):
    """Response model for an execution event log entry."""

    id: uuid.UUID
    mission_id: uuid.UUID | None = None
    agent_id: uuid.UUID | None = None
    event_type: str
    severity: Severity
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime


class LogExportRequest(ShogunBase):
    """Request body for exporting a log bundle."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    agent_id: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    severity: Severity | None = None
