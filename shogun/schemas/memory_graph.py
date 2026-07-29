"""API contracts for the Phase 2 Kiroku MemoryGraph."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from shogun.schemas.common import ShogunBase

GraphSensitivity = Literal["public", "internal", "confidential", "restricted"]
GraphNodeStatus = Literal["active", "superseded", "conflicting", "needs_review", "deprecated", "expired"]
ConflictResolutionStatus = Literal["needs_review", "confirmed", "resolved", "dismissed"]


class GraphScope(ShogunBase):
    tenant_id: str = Field(default="local", min_length=1, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    team_id: str | None = Field(default=None, max_length=255)
    workspace_id: str | None = Field(default=None, max_length=255)
    project_id: str | None = Field(default=None, max_length=255)
    agent_id: uuid.UUID | None = None
    topic_id: str | None = Field(default=None, max_length=255)


class MemoryGraphNodeCreate(ShogunBase):
    node_type: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=500)
    canonical_key: str | None = Field(default=None, max_length=700)
    payload_json: dict = Field(default_factory=dict)
    scope: GraphScope = Field(default_factory=GraphScope)
    sensitivity: GraphSensitivity = "internal"
    source_memory_id: uuid.UUID | None = None
    qdrant_point_id: str | None = Field(default=None, max_length=255)


class MemoryGraphNodeUpdate(ShogunBase):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    display_name: str | None = Field(default=None, max_length=500)
    payload_json: dict | None = None
    sensitivity: GraphSensitivity | None = None
    status: GraphNodeStatus | None = None


class MemoryGraphNodeResponse(ShogunBase):
    id: uuid.UUID
    canonical_key: str
    node_type: str
    name: str
    display_name: str | None = None
    payload_json: dict = Field(default_factory=dict)
    scope_json: dict = Field(default_factory=dict)
    tenant_id: str
    user_id: str | None = None
    team_id: str | None = None
    workspace_id: str | None = None
    project_id: str | None = None
    agent_id: uuid.UUID | None = None
    topic_id: str | None = None
    sensitivity: GraphSensitivity
    status: GraphNodeStatus
    source_memory_id: uuid.UUID | None = None
    qdrant_point_id: str | None = None
    created_at: datetime
    updated_at: datetime


class MemoryGraphEdgeCreate(ShogunBase):
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    relationship_type: str = Field(..., min_length=1, max_length=60)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_memory_id: uuid.UUID | None = None
    payload_json: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def prevent_self_edge(self):
        if self.from_node_id == self.to_node_id:
            raise ValueError("A graph edge cannot connect a node to itself")
        return self


class MemoryGraphEdgeResponse(ShogunBase):
    id: uuid.UUID
    from_node_id: uuid.UUID
    to_node_id: uuid.UUID
    relationship_type: str
    weight: float
    confidence: float
    source_memory_id: uuid.UUID | None = None
    payload_json: dict = Field(default_factory=dict)
    status: str
    created_at: datetime
    updated_at: datetime


class MemoryConflictCreate(ShogunBase):
    memory_id_a: uuid.UUID
    memory_id_b: uuid.UUID
    conflict_type: str = Field(default="contradiction", min_length=1, max_length=50)

    @model_validator(mode="after")
    def prevent_self_conflict(self):
        if self.memory_id_a == self.memory_id_b:
            raise ValueError("A memory cannot conflict with itself")
        return self


class MemoryConflictResolve(ShogunBase):
    resolution_status: ConflictResolutionStatus = "resolved"
    resolved_by: str = Field(..., min_length=1, max_length=255)
    resolution_note: str = Field(..., min_length=1, max_length=4000)
    superseding_memory_id: uuid.UUID | None = None


class MemoryConflictResponse(ShogunBase):
    id: uuid.UUID
    memory_id_a: uuid.UUID
    memory_id_b: uuid.UUID
    conflict_type: str
    resolution_status: ConflictResolutionStatus
    resolved_by: str | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MemoryGraphBackfillRequest(ShogunBase):
    limit: int = Field(default=250, ge=1, le=5000)
    after_memory_id: uuid.UUID | None = None
    include_archived: bool = False


class MemoryGraphBackfillResponse(ShogunBase):
    scanned: int
    memory_nodes_created: int
    scope_nodes_created: int
    edges_created: int
    next_after_memory_id: uuid.UUID | None = None
    complete: bool


class MemoryGraphNeighborhoodResponse(ShogunBase):
    root_node_id: uuid.UUID
    nodes: list[MemoryGraphNodeResponse] = Field(default_factory=list)
    edges: list[MemoryGraphEdgeResponse] = Field(default_factory=list)
