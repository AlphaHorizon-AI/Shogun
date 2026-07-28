"""API contracts for Stack Orchestrator runtime control."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from shogun.schemas.common import ShogunBase

StackMode = Literal["template", "goal_driven", "selected_stack"]
StackOutputPublication = Literal["summary_and_final", "summary_only", "final_only", "all_steps"]


class StackOrchestratorCreate(BaseModel):
    mode: StackMode
    stack_template_id: str | None = None
    selected_stack_id: uuid.UUID | None = None
    objective: str = Field(min_length=1, max_length=10000)
    success_criteria: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    model_routing_profile: str = "balanced"
    max_runtime_minutes: int = Field(default=60, ge=1, le=1440)
    max_iterations: int = Field(default=50, ge=1, le=500)
    max_retry_attempts_per_step: int = Field(default=2, ge=0, le=10)
    checkpoint_frequency: Literal["after_each_step", "after_each_subflow", "timed"] = "after_each_step"
    context_compaction: Literal["enabled", "disabled"] = "enabled"
    verification_required: bool = True
    approval_policy: Literal["inherited", "step_based", "always_required_for_high_risk"] = "inherited"
    artifact_policy: Literal["retain_all", "retain_final_only", "retain_selected"] = "retain_all"
    output_publication: StackOutputPublication | None = None
    failure_policy: Literal["pause", "retry", "continue_with_error", "fail_stack"] = "pause"
    input_payload: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_mode_reference(self):
        if self.mode == "selected_stack" and not self.selected_stack_id:
            raise ValueError("selected_stack_id is required for selected_stack mode")
        if self.mode == "template" and not self.stack_template_id:
            raise ValueError("stack_template_id is required for template mode")
        return self


class StackPlanDecision(BaseModel):
    approved: bool
    selected_stack_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


class StackStepDecision(BaseModel):
    step_id: str
    approved: bool
    reason: str | None = Field(default=None, max_length=2000)


class StackStepResponse(ShogunBase):
    id: uuid.UUID
    stack_run_id: uuid.UUID
    step_id: str
    parent_step_id: str | None
    sequence: int
    name: str
    status: str
    step_type: str
    flow_id: uuid.UUID | None
    flow_run_id: uuid.UUID | None
    model_used: str | None
    retry_count: int
    max_retries: int
    started_at: datetime | None
    completed_at: datetime | None
    input_json: dict
    output_json: dict
    error_json: dict
    expected_output: str | None
    verification_status: str
    requires_verification: bool
    requires_approval: bool
    risk_level: str
    required_tools: list
    metadata_json: dict


class StackRunResponse(ShogunBase):
    id: uuid.UUID
    stack_id: uuid.UUID | None
    root_run_id: uuid.UUID | None
    mode: str
    status: str
    objective: str
    posture: str
    model_profile: str
    current_step_id: str | None
    max_runtime_minutes: int
    max_iterations: int
    max_retry_attempts_per_step: int
    checkpoint_frequency: str
    context_compaction: bool
    verification_required: bool
    approval_policy: str
    artifact_policy: str
    output_publication: str
    failure_policy: str
    success_criteria: list
    allowed_tools: list
    completed_steps: list
    pending_steps: list
    failed_steps: list
    approval_events: list
    model_usage: list
    final_summary: dict
    published_output: dict
    metadata_json: dict
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    steps: list[StackStepResponse] = Field(default_factory=list)


class StackCheckpointResponse(ShogunBase):
    id: uuid.UUID
    stack_run_id: uuid.UUID
    step_run_id: uuid.UUID | None
    summary: str
    context_summary: str
    resume_instruction: str
    artifacts_json: list
    state_json: dict
    created_at: datetime


class StackArtifactResponse(ShogunBase):
    id: uuid.UUID
    stack_run_id: uuid.UUID
    step_run_id: uuid.UUID | None
    artifact_type: str
    path: str | None
    summary: str
    metadata_json: dict
    created_at: datetime


class StackVerificationResponse(ShogunBase):
    id: uuid.UUID
    stack_run_id: uuid.UUID
    step_run_id: uuid.UUID | None
    verification_type: str
    expected_result: str
    observed_result: str
    status: str
    metadata_json: dict
    created_at: datetime
