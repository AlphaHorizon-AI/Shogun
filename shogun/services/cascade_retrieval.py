"""Phase 1 governed, scoped cascade retrieval."""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.memory_retrieval import MemoryRetrievalRun
from shogun.schemas.memory import MemoryRetrievalMode, MemoryScopeEnvelope
from shogun.services.memory_scope import resolve_active_memory_scope
from shogun.services.memory_service import MemoryService


class CascadeRetrievalService:
    """Execute scoped stages while preserving a legacy/shadow cutover path."""

    STAGE_FIELDS = (
        ("topic_memory", "topic_id"),
        ("conversation_memory", "conversation_id"),
        ("workspace_memory", "workspace_id"),
        ("project_memory", "project_id"),
        ("workflow_memory", "workflow_id"),
        ("team_memory", "team_id"),
        ("user_memory", "user_id"),
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.memory = MemoryService(session)

    def plan(self, scope: MemoryScopeEnvelope) -> dict[str, Any]:
        stages = [
            {
                "name": name,
                "required_scope_field": field,
                "scope_value": getattr(scope, field),
                "max_results": settings.memory_cascade_stage_limit,
            }
            for name, field in self.STAGE_FIELDS
            if getattr(scope, field)
        ]
        stages.append(
            {
                "name": "agent_memory",
                "required_scope_field": None,
                "scope_value": None,
                "max_results": settings.memory_cascade_stage_limit,
            }
        )
        return {
            "strategy": "narrow_to_broad",
            "stop_after_results": settings.memory_cascade_min_results,
            "stages": stages[: settings.memory_cascade_max_stages],
        }

    async def _cascade(
        self,
        *,
        query: str,
        agent_id: uuid.UUID | None,
        scope: MemoryScopeEnvelope,
        limit: int,
        search_kwargs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
        plan = self.plan(scope)
        selected: list[dict[str, Any]] = []
        seen: set[str] = set()
        stage_diagnostics: list[dict[str, Any]] = []

        for stage in plan["stages"]:
            started = time.perf_counter()
            stage_results = await self.memory.search(
                query=query,
                agent_id=agent_id,
                scope=scope,
                required_scope_field=stage["required_scope_field"],
                limit=min(stage["max_results"], limit),
                **search_kwargs,
            )
            added = 0
            for item in stage_results:
                memory_id = str(item["memory_id"])
                if memory_id in seen:
                    continue
                seen.add(memory_id)
                item = {**item, "retrieval_stage": stage["name"]}
                selected.append(item)
                added += 1
                if len(selected) >= limit:
                    break
            stage_diagnostics.append(
                {
                    "name": stage["name"],
                    "required_scope_field": stage["required_scope_field"],
                    "candidate_count": len(stage_results),
                    "added_count": added,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                    "status": "completed",
                }
            )
            if len(selected) >= min(limit, settings.memory_cascade_min_results):
                break
        return selected[:limit], plan, stage_diagnostics

    async def run(
        self,
        *,
        query: str,
        agent_id: uuid.UUID | None,
        scope: MemoryScopeEnvelope | dict[str, Any] | None,
        mode: MemoryRetrievalMode | None = None,
        limit: int = 10,
        **search_kwargs: Any,
    ) -> tuple[list[dict[str, Any]], MemoryRetrievalRun | None]:
        effective_mode: MemoryRetrievalMode = mode or settings.memory_retrieval_mode
        memory_scope = resolve_active_memory_scope(scope)
        started = time.perf_counter()
        correlation_id = f"mem_{uuid.uuid4().hex}"
        diagnostic: MemoryRetrievalRun | None = None

        if effective_mode == "legacy":
            results = await self.memory.search(
                query=query, agent_id=agent_id, limit=limit, **search_kwargs
            )
            plan, stages, excluded = {"strategy": "legacy"}, [], []
        else:
            cascade_results, plan, stages = await self._cascade(
                query=query,
                agent_id=agent_id,
                scope=memory_scope,
                limit=limit,
                search_kwargs=search_kwargs,
            )
            excluded = []
            if effective_mode == "shadow":
                results = await self.memory.search(
                    query=query, agent_id=agent_id, limit=limit, **search_kwargs
                )
                cascade_ids = {str(item["memory_id"]) for item in cascade_results}
                excluded = [
                    {"memory_id": str(item["memory_id"]), "reason": "not_authorized_or_not_selected_by_cascade"}
                    for item in results
                    if str(item["memory_id"]) not in cascade_ids
                ]
                plan = {**plan, "shadow_result_memory_ids": list(cascade_ids)}
            else:
                results = cascade_results

        if settings.memory_cascade_diagnostics_enabled:
            now = datetime.now(timezone.utc)
            diagnostic = MemoryRetrievalRun(
                correlation_id=correlation_id,
                query_hash=hashlib.sha256(query.encode("utf-8")).hexdigest(),
                mode=effective_mode,
                status="completed",
                agent_id=agent_id,
                scope_json=memory_scope.model_dump(mode="json"),
                plan_json=plan,
                stages_json=stages,
                result_memory_ids=[str(item["memory_id"]) for item in results],
                excluded_json=excluded,
                duration_ms=round((time.perf_counter() - started) * 1000),
                completed_at=now,
            )
            self.session.add(diagnostic)
            await self.session.flush()
        return results, diagnostic
