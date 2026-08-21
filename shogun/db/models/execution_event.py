"""Execution-event ORM model for governance and investigation records.

Every event captures WHO did WHAT, WHEN, WHY, WITH WHAT PERMISSIONS,
USING WHICH MODEL, ON WHICH DATA, WITH WHICH RESULT.

Optional governance fields capture decision provenance, confidence tracking,
use-case context, governance flags, and human-oversight records. Their presence
does not establish regulatory conformity or record completeness.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, GUID, JSONType, UUIDMixin


class ExecutionEvent(Base, UUIDMixin):
    """Operational event record that can support governance assessments.

    Two-layer design:
      Layer 1 (this table): Operational logs — fast and searchable
      Layer 2 (immutable_audit.db): HMAC-chained and append-only through the
      application service; retention is managed by the deploying organisation
    """

    __tablename__ = "execution_events"

    # ── Identity & Correlation ────────────────────────────────
    event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: f"evt_{uuid.uuid4().hex[:16]}"
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    # ── Event Classification ──────────────────────────────────
    event_category: Mapped[str] = mapped_column(
        String(50), nullable=False, default="system", index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="info", index=True
    )

    # ── Action & Result ───────────────────────────────────────
    action: Mapped[str] = mapped_column(String(2000), nullable=False)
    summary: Mapped[str] = mapped_column(
        String(2000), nullable=False, default=""
    )
    result: Mapped[str] = mapped_column(
        String(50), nullable=False, default="success"
    )

    # ── Model & Provider ──────────────────────────────────────
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Tool / Skill ──────────────────────────────────────────
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Data Classification ───────────────────────────────────
    data_classification: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default="internal"
    )

    # ── Policy / Authorization ────────────────────────────────
    policy_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    policy_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    policy_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # ── Risk ──────────────────────────────────────────────────
    risk_score: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default="low"
    )

    # ── Structured Detail ─────────────────────────────────────
    detail: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    payload: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    memory_ids: Mapped[list] = mapped_column(
        JSONType(), nullable=False, default=list
    )

    # ── Access Context ────────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # ── EU AI Act — Decision Provenance ───────────────────────
    confidence_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    governance_flags: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
    use_case_context: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )

    # ── Timestamps ────────────────────────────────────────────
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
