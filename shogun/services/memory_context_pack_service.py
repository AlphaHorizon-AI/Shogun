"""Bounded, auditable context-pack construction for Phase 3 retrieval."""

from __future__ import annotations

import hashlib
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.memory_context_pack import MemoryContextPack
from shogun.schemas.memory import MemoryScopeEnvelope


class MemoryContextPackService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, pack_id: uuid.UUID) -> MemoryContextPack | None:
        return await self.session.get(MemoryContextPack, pack_id)

    async def by_correlation(self, correlation_id: str) -> MemoryContextPack | None:
        return await self.session.scalar(
            select(MemoryContextPack).where(MemoryContextPack.correlation_id == correlation_id)
        )

    async def build(
        self,
        *,
        correlation_id: str,
        query: str,
        scope: MemoryScopeEnvelope,
        agent_id: uuid.UUID | None,
        candidates: list[dict[str, Any]],
        excluded: list[dict[str, Any]],
        warnings: list[str],
        policy_notes: list[str],
    ) -> tuple[MemoryContextPack, list[dict[str, Any]], list[dict[str, Any]]]:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            delete(MemoryContextPack).where(
                MemoryContextPack.expires_at.is_not(None),
                MemoryContextPack.expires_at < now,
            )
        )
        max_chars = max(settings.memory_context_pack_max_tokens, 100) * 4
        scope_json = scope.model_dump(mode="json", exclude_none=True)
        base_chars = len(query) + len(str(scope_json)) + sum(map(len, warnings + policy_notes))
        remaining = max(max_chars - base_chars, 0)
        buckets: dict[str, list[dict[str, Any]]] = {
            "relevant_facts": [],
            "recent_context": [],
            "procedures": [],
            "preferences": [],
            "capabilities": [],
        }
        bucket_by_type = {
            "semantic": "relevant_facts",
            "episodic": "recent_context",
            "procedural": "procedures",
            "persona": "preferences",
            "skills": "capabilities",
        }
        included: list[dict[str, Any]] = []
        budget_excluded: list[dict[str, Any]] = []
        ordered = sorted(
            candidates,
            key=lambda item: float((item.get("scores") or {}).get("final", 0.0)),
            reverse=True,
        )
        for candidate in ordered:
            title = str(candidate.get("title") or "")[:500]
            content = str(candidate.get("content") or "")
            fixed_cost = len(title) + 120
            if remaining <= fixed_cost:
                budget_excluded.append(
                    {"memory_id": str(candidate["memory_id"]), "reason": "context_pack_token_budget"}
                )
                continue
            content = content[: min(len(content), remaining - fixed_cost, 4000)]
            item = {
                "memory_id": str(candidate["memory_id"]),
                "title": title,
                "content": content,
                "score": round(float((candidate.get("scores") or {}).get("final", 0.0)), 4),
                "retrieval_source": candidate.get("retrieval_source", "vector"),
                "retrieval_stage": candidate.get("retrieval_stage"),
            }
            bucket = bucket_by_type.get(str(candidate.get("memory_type")), "relevant_facts")
            buckets[bucket].append(item)
            included.append(candidate)
            remaining -= len(title) + len(content) + 120

        content_json = {
            "task_summary": query[:1000],
            "active_scope": scope_json,
            **buckets,
            "warnings": warnings,
            "policy_notes": policy_notes,
        }
        char_count = len(str(content_json))
        graph_ids = [
            str(item["memory_id"])
            for item in included
            if item.get("retrieval_source") == "memory_graph"
        ]
        pack = MemoryContextPack(
            correlation_id=correlation_id,
            query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
            agent_id=agent_id,
            scope_json=scope_json,
            content_json=content_json,
            included_memory_ids=[str(item["memory_id"]) for item in included],
            graph_expanded_memory_ids=graph_ids,
            excluded_json=[*excluded, *budget_excluded],
            warnings_json=warnings,
            policy_notes=policy_notes,
            token_estimate=math.ceil(char_count / 4),
            expires_at=now + timedelta(minutes=settings.memory_context_pack_retention_minutes),
        )
        self.session.add(pack)
        await self.session.flush()
        await self.session.refresh(pack)
        return pack, included, budget_excluded

    @staticmethod
    def render_prompt_block(pack: MemoryContextPack) -> str:
        content = pack.content_json or {}
        labels = (
            ("relevant_facts", "RELEVANT FACTS"),
            ("recent_context", "RECENT CONTEXT"),
            ("procedures", "PROCEDURES"),
            ("preferences", "PREFERENCES"),
            ("capabilities", "CAPABILITIES"),
        )
        lines = ["[KIROKU CONTEXT PACK — governed and verified]"]
        for key, label in labels:
            items = content.get(key) or []
            if not items:
                continue
            lines.append(f"\n{label}:")
            lines.extend(f"- {item['title']}: {item['content']}" for item in items)
        warnings = content.get("warnings") or []
        if warnings:
            lines.append("\nWARNINGS:")
            lines.extend(f"- {warning}" for warning in warnings)
        return "\n".join(lines)
