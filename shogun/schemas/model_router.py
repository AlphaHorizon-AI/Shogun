"""Schemas for task-aware model routing."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from shogun.schemas.common import ShogunBase

TASK_TYPES = (
    "simple_chat",
    "summarization",
    "classification",
    "extraction",
    "memory_write",
    "memory_retrieval",
    "planning",
    "complex_reasoning",
    "coding_plan",
    "coding_edit",
    "test_failure_analysis",
    "visual_understanding",
    "screenshot_analysis",
    "ui_mockup_analysis",
    "photo_understanding",
    "visual_self_verification",
    "browser_task",
    "desktop_task",
    "productivity_task",
    "self_verification",
    "final_review",
    "skill_selection",
    "skill_execution",
    "stack_planning",
    "stack_step_execution",
    "context_compaction",
)


class ModelCapabilities(ShogunBase):
    chat: bool = True
    reasoning: bool = False
    coding: bool = False
    vision: bool = False
    tool_use: bool = False
    long_context: bool = False
    json_mode: bool = False


class ModelRegistryCreate(ShogunBase):
    model_id: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    provider_id: uuid.UUID | None = None
    provider: str = Field(..., min_length=1, max_length=100)
    connection_type: Literal["api", "local"] = "api"
    enabled: bool = True
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)
    quality_tier: int = Field(3, ge=1, le=5)
    cost_tier: int = Field(3, ge=1, le=5)
    latency_tier: int = Field(3, ge=1, le=5)
    context_window: int = Field(8192, ge=1024)
    max_output_tokens: int = Field(4096, ge=128)
    local: bool = False
    role_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class ModelRegistryUpdate(ShogunBase):
    display_name: str | None = None
    provider_id: uuid.UUID | None = None
    provider: str | None = None
    connection_type: Literal["api", "local"] | None = None
    enabled: bool | None = None
    capabilities: ModelCapabilities | None = None
    quality_tier: int | None = Field(None, ge=1, le=5)
    cost_tier: int | None = Field(None, ge=1, le=5)
    latency_tier: int | None = Field(None, ge=1, le=5)
    context_window: int | None = Field(None, ge=1024)
    max_output_tokens: int | None = Field(None, ge=128)
    local: bool | None = None
    role_tags: list[str] | None = None
    notes: str | None = None
    config_json: dict[str, Any] | None = None


class ModelRegistryResponse(ModelRegistryCreate):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ModelRouteRequest(ShogunBase):
    prompt: str = ""
    task_type: str | None = None
    complexity_override: int | None = Field(None, ge=1, le=5)
    required_capabilities: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"
    retry_count: int = Field(0, ge=0)
    verification_status: str | None = None
    context_size_estimate: int = Field(0, ge=0)
    file_count: int = Field(0, ge=0)
    tool_count: int = Field(0, ge=0)
    stack_depth: int = Field(0, ge=0)
    posture: str | None = None
    profile_override: str | None = None
    local_only: bool = False
    run_id: uuid.UUID | None = None
    stack_run_id: uuid.UUID | None = None
    step_id: str | None = None
    escalation_level: int = Field(0, ge=0)
    exclude_model_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_task(self):
        if self.task_type and self.task_type not in TASK_TYPES and self.task_type != "*":
            raise ValueError(f"Unknown task_type: {self.task_type}")
        return self


class ModelRouteDecisionResponse(ShogunBase):
    id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    stack_run_id: uuid.UUID | None = None
    step_id: str | None = None
    task_type: str
    complexity_score: int
    active_profile: str
    selected_registry_id: uuid.UUID | None = None
    selected_model: str
    selected_provider: str
    fallback_model: str | None = None
    fallback_provider: str | None = None
    reason: str
    estimated_cost_tier: int
    estimated_latency_tier: int
    escalation_level: int
    requires_vision: bool
    requires_tool_use: bool
    requires_json_mode: bool
    candidate_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ModelUsageCreate(ShogunBase):
    routing_decision_id: uuid.UUID | None = None
    stack_run_id: uuid.UUID | None = None
    model_id: str
    provider: str
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    estimated_cost: float = Field(0.0, ge=0)
    latency_ms: int = Field(0, ge=0)
    success: bool = True
    error_json: dict[str, Any] = Field(default_factory=dict)


class ActiveProfileRequest(ShogunBase):
    profile_id: uuid.UUID | None = None
    profile: str | None = None
