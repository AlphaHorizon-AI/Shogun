"""Bushido schemas — reflection, maintenance, and self-improvement."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from shogun.schemas.common import (
    BushidoFrequency,
    BushidoJobStatus,
    BushidoJobType,
    MemoryType,
    RiskLevel,
    ShogunBase,
    TriggerMode,
)

# ── Bushido Job ──────────────────────────────────────────────


class BushidoScope(ShogunBase):
    """Scope for a Bushido run."""

    agent_ids: list[uuid.UUID] = Field(default_factory=list)
    memory_types: list[MemoryType] = Field(default_factory=list)


class BushidoRunRequest(ShogunBase):
    """Request body for triggering a Bushido run."""

    job_type: BushidoJobType
    scope: BushidoScope = Field(default_factory=BushidoScope)
    trigger_mode: TriggerMode = TriggerMode.MANUAL
    priority: int = Field(default=50, ge=0, le=100)


class BushidoJobResponse(ShogunBase):
    """Response model for a Bushido job."""

    id: uuid.UUID
    job_type: BushidoJobType
    status: BushidoJobStatus
    scope: BushidoScope
    trigger_mode: TriggerMode
    started_at: datetime | None = None
    completed_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    output_ref: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


# ── Bushido Recommendation ───────────────────────────────────


class BushidoRecommendationResponse(ShogunBase):
    """Response model for a Bushido recommendation."""

    id: uuid.UUID
    job_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    recommendation_type: str
    title: str
    description: str
    confidence: float
    risk_level: RiskLevel
    approval_required: bool
    status: str
    created_at: datetime
    updated_at: datetime


# ── Bushido Schedule ─────────────────────────────────────────


class BushidoScheduleCreate(ShogunBase):
    """Request body for creating a new Bushido schedule."""

    name: str
    job_type: BushidoJobType
    frequency: BushidoFrequency = BushidoFrequency.NIGHTLY
    schedule_time: str | None = "02:00"            # "HH:MM"
    schedule_days: list[str] | None = None          # ["mon", "wed"]
    schedule_day: int | None = None                 # day of month 1-28
    minute_offset: int = Field(default=0, ge=0, le=55)
    schedule_datetime: str | None = None            # ISO string for one-off
    scope: BushidoScope = Field(default_factory=BushidoScope)
    priority: int = Field(default=50, ge=0, le=100)
    all_agents: bool = True
    dry_run: bool = False
    auto_approve: bool = False
    task_instruction: str | None = None
    is_enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Job name is required")
        return value

    @field_validator("schedule_time")
    @classmethod
    def validate_schedule_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            hour_text, minute_text = value.split(":")
            hour, minute = int(hour_text), int(minute_text)
        except (ValueError, AttributeError):
            raise ValueError("Schedule time must use HH:MM format") from None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Schedule time must be a valid local time")
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def validate_frequency_details(self):
        if self.frequency == BushidoFrequency.WEEKLY and not self.schedule_days:
            raise ValueError("Weekly schedules require at least one active day")
        if self.frequency == BushidoFrequency.ONE_OFF:
            if not self.schedule_datetime:
                raise ValueError("One-off schedules require a future date and time")
            try:
                run_at = datetime.fromisoformat(self.schedule_datetime)
            except ValueError:
                raise ValueError("One-off schedule date is invalid") from None
            now = datetime.now(run_at.tzinfo) if run_at.tzinfo else datetime.now()
            if run_at <= now:
                raise ValueError("One-off schedule date must be in the future")
        if self.job_type == BushidoJobType.CUSTOM_TASK and not (self.task_instruction or "").strip():
            raise ValueError("Custom tasks require a task instruction")
        return self


class BushidoScheduleUpdate(ShogunBase):
    """Partial update for a Bushido schedule."""

    name: str | None = None
    frequency: BushidoFrequency | None = None
    schedule_time: str | None = None
    schedule_days: list[str] | None = None
    schedule_day: int | None = None
    minute_offset: int | None = None
    schedule_datetime: str | None = None
    scope: BushidoScope | None = None
    priority: int | None = None
    all_agents: bool | None = None
    dry_run: bool | None = None
    auto_approve: bool | None = None
    task_instruction: str | None = None
    is_enabled: bool | None = None

    # Legacy compat — keep the old flat-bool form for the PUT /schedule endpoint
    nightly_consolidation: bool | None = None
    weekly_performance_audit: bool | None = None
    skill_health_check: bool | None = None
    persona_drift_check: bool | None = None


class BushidoScheduleResponse(ShogunBase):
    """Response model for a Bushido schedule."""

    id: uuid.UUID
    name: str
    job_type: BushidoJobType
    frequency: BushidoFrequency
    schedule_time: str | None
    schedule_days: list[str] | None
    schedule_day: int | None
    minute_offset: int
    schedule_datetime: str | None
    scope: dict[str, Any]
    priority: int
    all_agents: bool
    dry_run: bool
    auto_approve: bool
    task_instruction: str | None
    is_enabled: bool
    is_preset: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ReminderCreate(ShogunBase):
    """Create a durable L0 reminder."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    origin: str = Field(default="user", pattern="^(user|ai|system)$")
    item_type: str = Field(default="reminder", pattern="^(reminder|obligation|follow_up|check|deferred)$")
    reason: str | None = Field(default=None, max_length=4000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    expires_at: datetime | None = None
    source_message_id: str | None = Field(default=None, max_length=255)
    requires_confirmation: bool = False
    tenant_id: str = Field(default="local", min_length=1, max_length=255)
    user_id: str = Field(default="local_user", min_length=1, max_length=255)
    agent_id: uuid.UUID | None = None
    conversation_provider: str = Field(default="web", pattern="^(web|telegram|teams)$")
    conversation_id: str | None = Field(default=None, max_length=255)
    topic_id: str | None = Field(default=None, max_length=255)
    priority: int = Field(default=50, ge=0, le=100)
    schedule_type: str = Field(default="one_time", pattern="^(one_time|daily|weekdays|weekly|interval)$")
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    schedule_time: str | None = None
    schedule_days: list[int] | None = None
    interval_minutes: int | None = Field(default=None, ge=1, le=525600)
    run_at: datetime | None = None
    end_at: datetime | None = None
    max_occurrences: int | None = Field(default=None, ge=1)
    delivery_channel: str = Field(default="web", pattern="^(web|telegram|teams|both)$")
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Reminder title is required")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Unknown IANA timezone") from None
        return value

    @field_validator("schedule_time")
    @classmethod
    def valid_reminder_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            hour, minute = (int(part) for part in value.split(":"))
        except (ValueError, AttributeError):
            raise ValueError("Schedule time must use HH:MM format") from None
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Schedule time must be valid")
        return f"{hour:02d}:{minute:02d}"

    @model_validator(mode="after")
    def valid_reminder_schedule(self):
        now = datetime.now(self.run_at.tzinfo) if self.run_at and self.run_at.tzinfo else datetime.now()
        if self.schedule_type == "one_time" and (not self.run_at or self.run_at <= now):
            raise ValueError("One-time reminders require a future run_at")
        if self.schedule_type in {"daily", "weekdays", "weekly"} and not self.schedule_time:
            raise ValueError("Recurring calendar reminders require schedule_time")
        if self.schedule_type == "weekly":
            if not self.schedule_days or any(day < 0 or day > 6 for day in self.schedule_days):
                raise ValueError("Weekly reminders require schedule_days using Monday=0 through Sunday=6")
        if self.schedule_type == "interval" and not self.interval_minutes:
            raise ValueError("Interval reminders require interval_minutes")
        return self


class ReminderUpdate(ShogunBase):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    item_type: str | None = Field(default=None, pattern="^(reminder|obligation|follow_up|check|deferred)$")
    reason: str | None = Field(default=None, max_length=4000)
    expires_at: datetime | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    delivery_channel: str | None = Field(default=None, pattern="^(web|telegram|teams|both)$")
    metadata_json: dict[str, Any] | None = None


class ReminderResponse(ShogunBase):
    id: uuid.UUID
    tenant_id: str
    user_id: str
    agent_id: uuid.UUID | None
    conversation_provider: str
    conversation_id: str | None
    topic_id: str | None
    title: str
    description: str | None
    origin: str
    item_type: str
    reason: str | None
    confidence: float | None
    expires_at: datetime | None
    source_message_id: str | None
    requires_confirmation: bool
    priority: int
    schedule_type: str
    timezone: str
    schedule_time: str | None
    schedule_days: list[int] | None
    interval_minutes: int | None
    run_at: datetime | None
    end_at: datetime | None
    max_occurrences: int | None
    status: str
    delivery_channel: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    snoozed_until: datetime | None
    occurrence_count: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ReminderRunResponse(ShogunBase):
    id: uuid.UUID
    task_id: uuid.UUID
    scheduled_for: datetime
    started_at: datetime
    completed_at: datetime | None
    status: str
    occurrence_number: int
    delivery_result: dict[str, Any]
    error: str | None
    correlation_id: str
    created_at: datetime


class ReminderSnoozeRequest(ShogunBase):
    minutes: int = Field(ge=1, le=10080)


class ReminderParseRequest(ShogunBase):
    text: str = Field(min_length=1, max_length=1000)
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
