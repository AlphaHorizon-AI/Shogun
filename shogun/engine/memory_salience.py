"""Memory salience engine — decay, reinforcement, and reranking.

This module implements Shogun's dynamic memory salience layer as a first-class
system. It does NOT replace vector similarity search — it acts as a reranking
signal after candidate retrieval.

Core principles:
  - Similarity finds candidates. Relevance decides what matters now.
  - Relevance decays over time and is reinforced by *successful use*, not mere retrieval.
  - Importance is intrinsic and separate from relevance.
  - Pinned memories bypass normal decay.
  - Repeated retrieval without use *reduces* effective salience.

Decay model:
  Uses exponential half-life decay per decay class:
    fast   = 6 hours       (temporary episodic details)
    medium = 3 days         (active workflows)
    slow   = 14 days        (durable facts)
    sticky = 90 days        (important long-term operational memories)
    pinned = no decay       (only manual or policy-driven)

Reinforcement:
  - retrieved_and_used: moderate boost toward ceiling
  - confirmed_by_operator: strong boost toward ceiling
  - reused_across_sessions: strong boost toward ceiling
  - retrieved_not_used: mild penalty (repeated non-use compounds)

Reranking weights (default, tuned per memory type):
  final_score = (w_sim * semantic_similarity)
              + (w_rel * relevance_score)
              + (w_imp * importance_score)
              + (w_rec * recency_boost)
              + (w_con * confidence_score)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import dataclass, field


# ── Half-life constants (in hours) ───────────────────────────

DECAY_HALF_LIFE_HOURS: dict[str, float] = {
    "fast": 6.0,
    "medium": 72.0,       # 3 days
    "slow": 336.0,        # 14 days
    "sticky": 2160.0,     # 90 days
    "pinned": float("inf"),
}

# ── Reinforcement constants ──────────────────────────────────

REINFORCEMENT_BOOST: dict[str, float] = {
    "retrieved_and_used": 0.08,
    "confirmed_by_operator": 0.15,
    "reused_across_sessions": 0.12,
    "retrieved_not_used": -0.02,  # mild penalty
}

# Ceiling: relevance can never be reinforced above this
RELEVANCE_CEILING = 0.98

# Floor: relevance will never decay below this (allows recovery)
RELEVANCE_FLOOR = 0.01

# ── Default reranking weights per memory type ────────────────

@dataclass
class RerankWeights:
    """Weights for the reranking scoring model."""

    w_similarity: float = 0.50
    w_relevance: float = 0.20
    w_importance: float = 0.15
    w_recency: float = 0.10
    w_confidence: float = 0.05


DEFAULT_WEIGHTS = RerankWeights()

# Per-type tuning: episodic is more recency-sensitive,
# semantic is more importance-sensitive,
# procedural is more relevance/use-sensitive
TYPE_WEIGHTS: dict[str, RerankWeights] = {
    "episodic": RerankWeights(
        w_similarity=0.40,
        w_relevance=0.15,
        w_importance=0.10,
        w_recency=0.30,
        w_confidence=0.05,
    ),
    "semantic": RerankWeights(
        w_similarity=0.45,
        w_relevance=0.15,
        w_importance=0.25,
        w_recency=0.05,
        w_confidence=0.10,
    ),
    "procedural": RerankWeights(
        w_similarity=0.35,
        w_relevance=0.30,
        w_importance=0.15,
        w_recency=0.05,
        w_confidence=0.15,
    ),
    "persona": RerankWeights(
        w_similarity=0.40,
        w_relevance=0.15,
        w_importance=0.25,
        w_recency=0.05,
        w_confidence=0.15,
    ),
    "skills": RerankWeights(
        w_similarity=0.45,
        w_relevance=0.25,
        w_importance=0.15,
        w_recency=0.05,
        w_confidence=0.10,
    ),
}


# ── Decay computation ────────────────────────────────────────


def compute_decayed_relevance(
    current_relevance: float,
    decay_class: str,
    last_confirmed_at: datetime | None,
    is_pinned: bool,
    now: datetime | None = None,
) -> float:
    """Compute the current effective relevance after time-based decay.

    Uses exponential decay with a half-life determined by the decay class.
    Pinned memories skip normal decay entirely.

    Args:
        current_relevance: The stored relevance score (last reinforced value).
        decay_class: One of fast/medium/slow/sticky/pinned.
        last_confirmed_at: Timestamp of last reinforcement event.
        is_pinned: If True, bypass decay regardless of decay_class.
        now: Current time (defaults to utcnow).

    Returns:
        Decayed relevance score, clamped to [RELEVANCE_FLOOR, current_relevance].
    """
    if is_pinned or decay_class == "pinned":
        return current_relevance

    if now is None:
        now = datetime.now(timezone.utc)

    # If never confirmed, decay from creation — use a conservative baseline
    if last_confirmed_at is None:
        # No confirmation ever: apply moderate decay from current value
        return max(current_relevance * 0.85, RELEVANCE_FLOOR)

    half_life_hours = DECAY_HALF_LIFE_HOURS.get(decay_class, 72.0)
    elapsed_hours = (now - last_confirmed_at).total_seconds() / 3600.0

    if elapsed_hours <= 0:
        return current_relevance

    # Exponential decay: R(t) = R_0 * (0.5 ^ (t / half_life))
    decay_factor = math.pow(0.5, elapsed_hours / half_life_hours)
    decayed = current_relevance * decay_factor

    return max(decayed, RELEVANCE_FLOOR)


# ── Reinforcement computation ────────────────────────────────


def compute_reinforced_relevance(
    current_relevance: float,
    event_type: str,
    strength: float = 1.0,
) -> float:
    """Compute new relevance after a reinforcement event.

    Does NOT hard-reset relevance to max. Instead applies a bounded
    boost toward the ceiling. Repeated reinforcements approach the
    ceiling asymptotically.

    For negative events (retrieved_not_used), the penalty compounds
    but is bounded by a floor.

    Args:
        current_relevance: Current stored relevance.
        event_type: Type of reinforcement event.
        strength: Multiplier for the boost/penalty (default 1.0).

    Returns:
        New relevance score, clamped to [RELEVANCE_FLOOR, RELEVANCE_CEILING].
    """
    base_boost = REINFORCEMENT_BOOST.get(event_type, 0.0)
    effective_boost = base_boost * strength

    if effective_boost >= 0:
        # Positive reinforcement: move toward ceiling, diminishing returns
        headroom = RELEVANCE_CEILING - current_relevance
        new_relevance = current_relevance + (headroom * effective_boost / (effective_boost + 0.1))
    else:
        # Negative: direct subtraction, bounded by floor
        new_relevance = current_relevance + effective_boost

    return max(min(new_relevance, RELEVANCE_CEILING), RELEVANCE_FLOOR)


# ── Recency boost ────────────────────────────────────────────


def compute_recency_boost(
    last_accessed_at: datetime | None,
    now: datetime | None = None,
    half_life_hours: float = 24.0,
) -> float:
    """Compute a recency boost based on time since last access.

    Returns a value in [0.0, 1.0] that decays exponentially.

    Args:
        last_accessed_at: When the memory was last accessed.
        now: Current time.
        half_life_hours: How fast the recency signal decays.

    Returns:
        Recency boost score.
    """
    if last_accessed_at is None:
        return 0.0

    if now is None:
        now = datetime.now(timezone.utc)

    elapsed_hours = (now - last_accessed_at).total_seconds() / 3600.0
    if elapsed_hours <= 0:
        return 1.0

    return math.pow(0.5, elapsed_hours / half_life_hours)


# ── Reranking scorer ─────────────────────────────────────────


@dataclass
class ScoredMemory:
    """A memory candidate with computed scores."""

    memory_id: str
    memory_type: str
    title: str
    content: str
    # Raw scores
    semantic_similarity: float = 0.0
    relevance_score: float = 0.0
    importance_score: float = 0.0
    confidence_score: float = 0.0
    recency_boost: float = 0.0
    # Final
    final_score: float = 0.0
    # Metadata for transparency
    decay_class: str = "medium"
    access_count: int = 0
    successful_use_count: int = 0
    is_pinned: bool = False
    last_confirmed_at: datetime | None = None


def rerank_candidates(
    candidates: list[ScoredMemory],
    weight_overrides: dict[str, float] | None = None,
) -> list[ScoredMemory]:
    """Rerank memory candidates using the salience-weighted scoring model.

    Applies per-memory-type weights unless overridden.

    Args:
        candidates: List of scored memory candidates (semantic_similarity
                     must already be populated from vector search).
        weight_overrides: Optional dict to override default weights.
                          Keys: w_similarity, w_relevance, w_importance,
                                w_recency, w_confidence.

    Returns:
        Candidates sorted by final_score descending.
    """
    for candidate in candidates:
        # Select weights based on memory type
        weights = TYPE_WEIGHTS.get(candidate.memory_type, DEFAULT_WEIGHTS)

        # Apply overrides if provided
        w_sim = weight_overrides.get("w_similarity", weights.w_similarity) if weight_overrides else weights.w_similarity
        w_rel = weight_overrides.get("w_relevance", weights.w_relevance) if weight_overrides else weights.w_relevance
        w_imp = weight_overrides.get("w_importance", weights.w_importance) if weight_overrides else weights.w_importance
        w_rec = weight_overrides.get("w_recency", weights.w_recency) if weight_overrides else weights.w_recency
        w_con = weight_overrides.get("w_confidence", weights.w_confidence) if weight_overrides else weights.w_confidence

        candidate.final_score = (
            (w_sim * candidate.semantic_similarity)
            + (w_rel * candidate.relevance_score)
            + (w_imp * candidate.importance_score)
            + (w_rec * candidate.recency_boost)
            + (w_con * candidate.confidence_score)
        )

    candidates.sort(key=lambda c: c.final_score, reverse=True)
    return candidates


# ── Batch decay processor ────────────────────────────────────


def apply_batch_decay(
    records: list[dict],
    now: datetime | None = None,
) -> list[dict]:
    """Apply time-based decay to a batch of memory records.

    Designed to be called by Bushido's nightly consolidation job.
    Returns records with updated relevance_score values.

    Args:
        records: List of dicts with keys: relevance_score, decay_class,
                 last_confirmed_at, is_pinned.
        now: Current time.

    Returns:
        Same list with relevance_score updated.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    for record in records:
        record["relevance_score"] = compute_decayed_relevance(
            current_relevance=record["relevance_score"],
            decay_class=record.get("decay_class", "medium"),
            last_confirmed_at=record.get("last_confirmed_at"),
            is_pinned=record.get("is_pinned", False),
            now=now,
        )

    return records
