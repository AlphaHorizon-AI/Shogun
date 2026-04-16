"""Memory schemas — search, records, provenance, snapshots, and salience.

Implements full memory salience layer with:
- Dynamic relevance scoring with time-based decay
- Importance/confidence as separate dimensions
- Decay classes controlling decay rate
- Reinforcement tracking via access/use counters
- Reranking-aware search responses
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import Field

from shogun.schemas.common import DecayClass, MemoryType, ShogunBase, SnapshotType


# ── Memory Search ────────────────────────────────────────────


class MemorySearchFilters(ShogunBase):
    """Optional filters for memory search."""

    tags: list[str] | None = None
    pinned_only: bool = False
    min_relevance: float | None = None
    min_importance: float | None = None
    decay_class: DecayClass | None = None


class MemorySearchRequest(ShogunBase):
    """Request body for searching memory.

    Retrieval flow:
    1. Retrieve candidates via vector similarity (Qdrant)
    2. Optionally combine with sparse/keyword retrieval
    3. Rerank using weighted salience scoring
    """

    query: str = Field(..., min_length=1)
    memory_types: list[MemoryType] | None = None
    agent_id: uuid.UUID | None = None
    limit: int = Field(default=10, ge=1, le=100)
    filters: MemorySearchFilters | None = None
    # Allow caller to override reranking weights per query
    weight_overrides: dict[str, float] | None = None


class MemoryScores(ShogunBase):
    """Full scoring breakdown for a memory search result.

    Final score = weighted combination:
      (0.50 * semantic_similarity)
    + (0.20 * relevance_score)
    + (0.15 * importance_score)
    + (0.10 * recency_boost)
    + (0.05 * confidence_score)

    Weights are tuned per memory type:
    - Episodic: more recency-sensitive
    - Semantic: more importance-sensitive
    - Procedural: more relevance/use-sensitive
    """

    semantic_similarity: float = 0.0
    relevance_score: float = 0.0
    importance_score: float = 0.0
    confidence_score: float = 0.0
    recency_boost: float = 0.0
    final: float = 0.0


class MemorySearchResult(ShogunBase):
    """A single memory search result with salience metadata."""

    memory_id: uuid.UUID
    memory_type: MemoryType
    title: str
    content: str
    scores: MemoryScores
    # Salience metadata exposed for transparency
    decay_class: DecayClass = DecayClass.MEDIUM
    access_count: int = 0
    successful_use_count: int = 0
    is_pinned: bool = False
    last_confirmed_at: datetime | None = None


class MemorySearchResponse(ShogunBase):
    """Response model for a memory search."""

    results: list[MemorySearchResult] = Field(default_factory=list)


# ── Memory Record CRUD ───────────────────────────────────────


class MemoryRecordCreate(ShogunBase):
    """Request body for creating a memory record."""

    memory_type: MemoryType
    agent_id: uuid.UUID
    title: str
    content: str
    summary: str | None = None
    # Salience fields
    relevance_score: float = Field(default=0.7, ge=0.0, le=1.0)
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    decay_class: DecayClass = DecayClass.MEDIUM
    is_pinned: bool = False
    tags: list[str] = Field(default_factory=list)


class MemoryRecordUpdate(ShogunBase):
    """Request body for updating memory metadata."""

    title: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    # Allow manual salience adjustments
    relevance_score: float | None = None
    importance_score: float | None = None
    confidence_score: float | None = None
    decay_class: DecayClass | None = None


class MemoryRecordResponse(ShogunBase):
    """Response model for a memory metadata record with full salience data."""

    id: uuid.UUID
    qdrant_point_id: str | None = None
    memory_type: MemoryType
    agent_id: uuid.UUID
    source_type: str | None = None
    source_ref_id: uuid.UUID | None = None
    title: str
    content: str = ""
    summary: str | None = None
    # Salience scores
    relevance_score: float
    importance_score: float
    confidence_score: float
    # Decay
    decay_class: DecayClass
    is_pinned: bool = False
    # Access tracking
    access_count: int = 0
    successful_use_count: int = 0
    recall_count: int = 0
    # Temporal
    last_accessed_at: datetime | None = None
    last_confirmed_at: datetime | None = None
    last_recalled_at: datetime | None = None
    # Lifecycle
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime


# ── Reinforcement Events ─────────────────────────────────────


class MemoryReinforcementRequest(ShogunBase):
    """Report that a memory was used and should be reinforced (or penalized).

    Reinforcement events:
    - retrieved_and_used: Memory was injected into context and contributed
    - confirmed_by_operator: Operator explicitly confirmed usefulness
    - reused_across_sessions: Successfully reused in a different session
    - retrieved_not_used: Retrieved as candidate but not actually used
    """

    memory_id: uuid.UUID
    event_type: str = Field(
        ...,
        pattern="^(retrieved_and_used|confirmed_by_operator|reused_across_sessions|retrieved_not_used)$",
    )
    strength: float = Field(default=1.0, ge=0.0, le=2.0, description="Reinforcement multiplier. 1.0 = normal.")


# ── Memory Merge ─────────────────────────────────────────────


class MemoryMergeRequest(ShogunBase):
    """Request body for merging memories."""

    source_memory_ids: list[uuid.UUID] = Field(..., min_length=2)
    target_title: str
    preserve_provenance: bool = True


# ── Memory Provenance ────────────────────────────────────────


class MemoryProvenanceResponse(ShogunBase):
    """Response model for a memory provenance link."""

    id: uuid.UUID
    child_memory_id: uuid.UUID
    parent_memory_id: uuid.UUID
    link_type: str
    weight: float
    created_at: datetime


# ── Snapshots ────────────────────────────────────────────────


class SnapshotCreate(ShogunBase):
    """Request body for creating a snapshot."""

    snapshot_type: SnapshotType
    name: str = Field(..., min_length=1, max_length=255)


class SnapshotResponse(ShogunBase):
    """Response model for a snapshot."""

    id: uuid.UUID
    snapshot_type: SnapshotType
    name: str
    storage_path: str
    status: str
    created_by: str
    created_at: datetime
