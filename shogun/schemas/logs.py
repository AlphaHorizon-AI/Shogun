"""Log and audit-event schemas for governance evidence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from shogun.schemas.common import ShogunBase


class ExecutionEventResponse(ShogunBase):
    """Full event response for the governance-evidence dashboard."""

    id: uuid.UUID
    event_id: str
    session_id: uuid.UUID | None = None
    trace_id: str | None = None
    agent_id: uuid.UUID | None = None
    user_id: str | None = None
    mission_id: uuid.UUID | None = None

    event_category: str
    event_type: str
    severity: str

    action: str
    summary: str = ""
    result: str = "success"

    model_used: str | None = None
    provider_used: str | None = None
    tool_name: str | None = None

    data_classification: str | None = "internal"

    policy_ref: str | None = None
    policy_decision: str | None = None
    policy_reason: str | None = None

    risk_score: str | None = "low"

    detail: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    memory_ids: list[str] = Field(default_factory=list)

    ip_address: str | None = None
    occurred_at: datetime
    duration_ms: int | None = None

    # EU AI Act governance
    confidence_score: float | None = None
    governance_flags: dict[str, Any] = Field(default_factory=dict)
    use_case_context: dict[str, Any] = Field(default_factory=dict)


class LogExportRequest(ShogunBase):
    """Request body for exporting a log bundle."""

    date_from: datetime | None = None
    date_to: datetime | None = None
    agent_id: uuid.UUID | None = None
    mission_id: uuid.UUID | None = None
    event_category: str | None = None
    severity: str | None = None
    trace_id: str | None = None


class AuditVerificationResponse(ShogunBase):
    """Result of an HMAC audit-chain consistency check."""

    total_records: int = 0
    verified_records: int = 0
    broken_at: int | None = None
    chain_intact: bool = True
    last_verified_at: datetime | None = None
    message: str = ""
