"""Public request contracts for Supermode and Mission Control."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from shogun.schemas.common import ShogunBase


class MissionBudgetSettings(ShogunBase):
    max_model_calls: int | None = Field(None, ge=1, le=10_000)
    max_tokens: int | None = Field(None, ge=1_000)
    max_cost: float | None = Field(None, ge=0.0)


class SupermodeSettings(ShogunBase):
    max_active_agents: int | None = Field(None, ge=1, le=50)
    max_total_agents: int | None = Field(None, ge=1, le=200)
    max_parallel_tasks: int | None = Field(None, ge=1, le=50)
    max_task_depth: int | None = Field(None, ge=0, le=10)
    max_plan_revisions: int | None = Field(None, ge=1, le=100)
    budget: MissionBudgetSettings = Field(default_factory=MissionBudgetSettings)
    deadline_at: datetime | None = None

    @model_validator(mode="after")
    def validate_agent_limits(self):
        if (
            self.max_active_agents is not None
            and self.max_total_agents is not None
            and self.max_active_agents > self.max_total_agents
        ):
            raise ValueError("max_active_agents cannot exceed max_total_agents")
        return self


class SupermodeMissionCreate(ShogunBase):
    objective: str = Field(..., min_length=3, max_length=50_000)
    title: str | None = Field(None, min_length=1, max_length=500)
    attachments: list[dict[str, Any] | str] = Field(default_factory=list, max_length=50)
    chat_session_id: str | None = Field(None, max_length=255)
    team_id: str | None = Field(None, max_length=255)
    success_criteria: list[str] = Field(default_factory=list, max_length=50)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    settings: SupermodeSettings = Field(default_factory=SupermodeSettings)


class MissionPatchRequest(ShogunBase):
    title: str | None = Field(None, min_length=1, max_length=500)
    priority: Literal["low", "medium", "high", "critical"] | None = None
    max_model_calls: int | None = Field(None, ge=1, le=10_000)
    token_budget: int | None = Field(None, ge=1_000)
    monetary_budget: float | None = Field(None, ge=0.0)
    deadline_at: datetime | None = None


class MissionSteerRequest(ShogunBase):
    instruction: str = Field(..., min_length=2, max_length=20_000)
    add_constraints: list[str] = Field(default_factory=list, max_length=50)
    remove_constraints: list[str] = Field(default_factory=list, max_length=50)


class MissionAgentCreateRequest(ShogunBase):
    role_name: str = Field(..., min_length=2, max_length=255)
    role_description: str = Field("", max_length=2000)
    objective: str = Field(..., min_length=2, max_length=20_000)
    spawn_reason: str = Field(..., min_length=2, max_length=2000)
    required_capabilities: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)


class ApprovalResolveRequest(ShogunBase):
    resolution: Literal["approved", "denied"]
    note: str | None = Field(None, max_length=1000)


class ReplanRequest(ShogunBase):
    reason: str = Field("Operator requested a new plan", min_length=2, max_length=2000)


class AgentFlowCandidateRequest(ShogunBase):
    name: str | None = Field(None, min_length=1, max_length=255)
