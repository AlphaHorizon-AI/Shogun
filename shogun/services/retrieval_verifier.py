"""Deterministic Kiroku verifier interface for memory injection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.memory_graph import MemoryGraphNode
from shogun.services.tool_gate import evaluate_advanced_controls


@dataclass
class VerificationResult:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    policy_notes: list[str] = field(default_factory=list)


class RetrievalVerifier(Protocol):
    async def verify(self, candidates: list[dict[str, Any]]) -> VerificationResult: ...


class DeterministicRetrievalVerifier:
    """Fail closed for known graph lifecycle and policy conflicts."""

    BLOCKED_STATUSES = {"superseded", "conflicting", "needs_review", "deprecated", "expired"}

    def __init__(self, session: AsyncSession):
        self.session = session

    async def verify(self, candidates: list[dict[str, Any]]) -> VerificationResult:
        memory_ids = {uuid.UUID(str(item["memory_id"])) for item in candidates}
        nodes = list(
            (
                await self.session.scalars(
                    select(MemoryGraphNode).where(MemoryGraphNode.source_memory_id.in_(memory_ids))
                )
            ).all()
        ) if memory_ids else []
        statuses = {str(node.source_memory_id): node.status for node in nodes}
        result = VerificationResult()
        unlinked_count = 0
        for candidate in candidates:
            memory_id = str(candidate["memory_id"])
            graph_status = statuses.get(memory_id, candidate.get("graph_status"))
            if graph_status in self.BLOCKED_STATUSES:
                result.excluded.append(
                    {"memory_id": memory_id, "reason": f"graph_status_{graph_status}"}
                )
                result.warnings.append(
                    f"Memory {memory_id} was withheld because its graph status is {graph_status}."
                )
                continue
            if graph_status is None:
                unlinked_count += 1

            action, reason, flags = evaluate_advanced_controls(
                "memory_read",
                {"title": candidate.get("title", ""), "content": candidate.get("content", "")},
            )
            action_value = getattr(action, "value", None)
            if action_value in {"block", "confirm"}:
                result.excluded.append(
                    {
                        "memory_id": memory_id,
                        "reason": "gensui_policy_block" if action_value == "block" else "policy_confirmation_required",
                        "policy_flags": flags,
                    }
                )
                result.policy_notes.append(reason or f"Policy action: {action_value}")
                continue

            if candidate.get("retrieval_source") == "memory_graph":
                effective_relevance = float((candidate.get("scores") or {}).get("relevance_score", 0.0))
                if (
                    not candidate.get("is_pinned")
                    and effective_relevance < settings.memory_graph_stale_relevance_threshold
                ):
                    result.excluded.append({"memory_id": memory_id, "reason": "stale_graph_memory"})
                    result.warnings.append(f"Stale graph memory {memory_id} was withheld.")
                    continue
            result.accepted.append(candidate)
        if unlinked_count:
            result.policy_notes.append(
                f"{unlinked_count} vector candidate(s) had no graph node and were verified using legacy metadata."
            )
        return result
