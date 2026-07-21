"""Pydantic schemas for Agent Flow — request/response models."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from shogun.schemas.common import ShogunBase


class MemoryInfusionDeduplication(BaseModel):
    mode: str = "exact"
    semantic_threshold: float = Field(default=0.92, ge=0.5, le=1.0)

    @model_validator(mode="after")
    def validate_mode(self):
        if self.mode not in {"none", "exact", "semantic"}:
            raise ValueError("deduplication.mode must be none, exact, or semantic")
        return self


class MemoryInfusionConfig(BaseModel):
    enabled: bool = False
    memory_type: str = "episodic"
    importance: float = Field(default=0.8, ge=0.0, le=1.0)
    decay_type: str = "sticky"
    tags: list[str] = Field(default_factory=lambda: ["auto-stored", "flow-output"], max_length=30)
    title_template: str = Field(default="{flow_name} - {timestamp}", min_length=1, max_length=500)
    content_fields: list[str] = Field(default_factory=lambda: ["result", "summary"], min_length=1, max_length=20)
    redact_sensitive: bool = True
    on_missing_field: str = "store_available"
    max_content_length: int = Field(default=12000, ge=256, le=100000)
    store_on: str = "success"
    deduplication: MemoryInfusionDeduplication = Field(default_factory=MemoryInfusionDeduplication)

    @model_validator(mode="after")
    def validate_choices(self):
        if self.memory_type not in {"episodic", "semantic", "procedural", "persona"}:
            raise ValueError("memory_type must be episodic, semantic, procedural, or persona")
        if self.decay_type not in {"fast", "medium", "slow", "sticky", "pinned"}:
            raise ValueError("decay_type must be fast, medium, slow, sticky, or pinned")
        if self.on_missing_field not in {"skip", "store_available", "fail"}:
            raise ValueError("on_missing_field must be skip, store_available, or fail")
        if self.store_on not in {"success", "partial", "always"}:
            raise ValueError("store_on must be success, partial, or always")
        if any(not field.strip() for field in self.content_fields):
            raise ValueError("content_fields cannot contain empty field names")
        placeholders = set(re.findall(r"{([^{}]+)}", self.title_template))
        unsupported = placeholders - {"flow_name", "node_label", "timestamp", "run_id"}
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise ValueError(f"Unsupported title_template placeholders: {names}")
        return self


# ── Node Schemas ─────────────────────────────────────────────


class AgentFlowNodeCreate(BaseModel):
    """Payload for creating a single node."""

    id: str | None = None  # Optional client-generated ID for React Flow
    node_type: str
    label: str = "Untitled"
    position_x: float = 0.0
    position_y: float = 0.0
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_output_memory_infusion(self):
        if self.node_type == "output" and "memory_infusion" in self.config:
            normalized = MemoryInfusionConfig.model_validate(self.config["memory_infusion"])
            self.config = {**self.config, "memory_infusion": normalized.model_dump()}
        return self


class AgentFlowNodeUpdate(BaseModel):
    """Partial update for a single node."""

    label: str | None = None
    position_x: float | None = None
    position_y: float | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_memory_infusion(self):
        if self.config and "memory_infusion" in self.config:
            normalized = MemoryInfusionConfig.model_validate(self.config["memory_infusion"])
            self.config = {**self.config, "memory_infusion": normalized.model_dump()}
        return self


class AgentFlowNodeResponse(ShogunBase):
    """Response model for a node."""

    id: uuid.UUID
    flow_id: uuid.UUID
    node_type: str
    label: str
    position_x: float
    position_y: float
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ── Edge Schemas ─────────────────────────────────────────────


class AgentFlowEdgeCreate(BaseModel):
    """Payload for creating a single edge."""

    id: str | None = None  # Optional client-generated ID
    source_node_id: str
    target_node_id: str
    source_handle: str | None = None
    target_handle: str | None = None
    label: str | None = None
    edge_type: str = "default"
    config: dict[str, Any] = Field(default_factory=dict)


class AgentFlowEdgeResponse(ShogunBase):
    """Response model for an edge."""

    id: uuid.UUID
    flow_id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    source_handle: str | None
    target_handle: str | None
    label: str | None
    edge_type: str
    config: dict[str, Any]
    created_at: datetime
    updated_at: datetime


# ── Flow Schemas ─────────────────────────────────────────────


class AgentFlowCreate(BaseModel):
    """Payload for creating a new Agent Flow."""

    name: str
    description: str | None = None
    trigger_type: str = "manual"
    schedule_config: dict[str, Any] = Field(default_factory=dict)
    flow_type: str = "standard"
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    risk_tier: str = "low"
    default_timeout_seconds: int = Field(default=600, ge=1, le=86400)
    allow_as_subflow: bool = True
    required_tools: list[str] = Field(default_factory=list)
    is_template: bool = False
    template_category: str | None = None
    template_source: str | None = None
    template_config: dict[str, Any] = Field(default_factory=dict)


class AgentFlowUpdate(BaseModel):
    """Partial update for a flow."""

    name: str | None = None
    description: str | None = None
    trigger_type: str | None = None
    schedule_config: dict[str, Any] | None = None
    status: str | None = None
    viewport: dict[str, Any] | None = None
    flow_type: str | None = None
    input_contract: dict[str, Any] | None = None
    output_contract: dict[str, Any] | None = None
    risk_tier: str | None = None
    default_timeout_seconds: int | None = Field(default=None, ge=1, le=86400)
    allow_as_subflow: bool | None = None
    required_tools: list[str] | None = None
    is_template: bool | None = None
    template_category: str | None = None
    template_source: str | None = None
    template_config: dict[str, Any] | None = None


class AgentFlowResponse(ShogunBase):
    """Response model for a flow (with nested nodes and edges)."""

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    trigger_type: str
    schedule_config: dict[str, Any]
    viewport: dict[str, Any]
    version: int = 1
    flow_type: str = "standard"
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    risk_tier: str = "low"
    default_timeout_seconds: int = 600
    allow_as_subflow: bool = True
    required_tools: list[str] = Field(default_factory=list)
    is_template: bool = False
    template_category: str | None = None
    template_source: str | None = None
    template_config: dict[str, Any] = Field(default_factory=dict)
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    created_by: str | None
    nodes: list[AgentFlowNodeResponse] = []
    edges: list[AgentFlowEdgeResponse] = []


class AgentFlowListItem(ShogunBase):
    """Lightweight response for flow list (without nodes/edges)."""

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    trigger_type: str
    version: int = 1
    flow_type: str = "standard"
    risk_tier: str = "low"
    allow_as_subflow: bool = True
    is_template: bool = False
    template_category: str | None = None
    template_source: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Bulk Graph Save ──────────────────────────────────────────


class AgentFlowGraphSave(BaseModel):
    """Bulk save payload — replaces all nodes and edges for a flow."""

    nodes: list[AgentFlowNodeCreate] = []
    edges: list[AgentFlowEdgeCreate] = []
    viewport: dict[str, Any] = Field(default_factory=lambda: {"x": 0, "y": 0, "zoom": 1})


# ── Execution Run Schemas ────────────────────────────────────


class AgentFlowRunCreate(BaseModel):
    """Trigger a flow execution."""

    trigger_type: str = "manual"
    input_payload: dict[str, Any] = Field(default_factory=dict)
    governance_context: dict[str, Any] = Field(default_factory=dict)


class AgentFlowRunResponse(ShogunBase):
    """Full execution run with per-node states."""

    id: uuid.UUID
    flow_id: uuid.UUID
    status: str
    trigger_type: str
    flow_version: int = 1
    root_run_id: uuid.UUID | None = None
    parent_run_id: uuid.UUID | None = None
    parent_node_id: uuid.UUID | None = None
    run_depth: int = 0
    node_states: dict[str, Any]
    result_summary: dict[str, Any]
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[Any] = Field(default_factory=list)
    governance_context: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class AgentFlowRunListItem(ShogunBase):
    """Lightweight run for list views."""

    id: uuid.UUID
    flow_id: uuid.UUID
    status: str
    trigger_type: str
    flow_version: int = 1
    root_run_id: uuid.UUID | None = None
    parent_run_id: uuid.UUID | None = None
    parent_node_id: uuid.UUID | None = None
    run_depth: int = 0
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime


class FlowStackCreate(BaseModel):
    """Create a normal flow composed of sequential subflow nodes."""

    name: str
    description: str | None = None
    flow_ids: list[uuid.UUID] = Field(min_length=2, max_length=20)
    version_mode: str = "locked"
    timeout_seconds: int = Field(default=600, ge=1, le=86400)


class SubflowValidationRequest(BaseModel):
    child_flow_id: uuid.UUID
    child_flow_version_mode: str = "locked"
    child_flow_version: int | None = None


class SaveFlowTemplateRequest(BaseModel):
    """Save a reusable snapshot of an existing flow or stack."""

    name: str | None = None
    category: str = "My Templates"
    description: str | None = None


class FlowStackComposeNode(BaseModel):
    """A draggable AgentFlow template or saved flow on the stack canvas."""

    id: str
    template_id: str | None = None
    flow_id: uuid.UUID | None = None
    label: str | None = None
    position_x: float = 0.0
    position_y: float = 0.0


class FlowStackComposeEdge(BaseModel):
    id: str | None = None
    source: str
    target: str


class FlowStackComposeRequest(BaseModel):
    name: str
    description: str | None = None
    category: str = "Custom"
    nodes: list[FlowStackComposeNode] = Field(min_length=1, max_length=50)
    edges: list[FlowStackComposeEdge] = Field(default_factory=list)
    orchestrator_config: dict[str, Any] = Field(default_factory=dict)
    save_as_template: bool = False


class FlowStackTemplateInstantiate(BaseModel):
    template_id: str
    name: str | None = None

