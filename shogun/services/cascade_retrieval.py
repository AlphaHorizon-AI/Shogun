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
from shogun.services.cascade_retrieval_planner import CascadeRetrievalPlanner
from shogun.services.graph_retrieval import GraphRetrievalService
from shogun.services.memory_context_pack_service import MemoryContextPackService
from shogun.services.memory_scope import resolve_active_memory_scope
from shogun.services.memory_service import MemoryService
from shogun.services.retrieval_verifier import DeterministicRetrievalVerifier


class CascadeRetrievalService:
    """Execute scoped stages while preserving a legacy/shadow cutover path."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.memory = MemoryService(session)
        self.planner = CascadeRetrievalPlanner()

    def plan(self, scope: MemoryScopeEnvelope) -> dict[str, Any]:
        return self.planner.build(scope, graph_mode=settings.memory_graph_retrieval_mode)

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

        for stage in [item for item in plan["stages"] if item.get("query_type") == "semantic"]:
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
        # Connector and other classified requests must never fall back to the
        # unscoped legacy/shadow result set.  This is an authorization boundary,
        # not a rollout preference: the cascade pre-authorizes every candidate
        # against the active principal/conversation dimensions.
        if effective_mode != "cascade" and any(
            (
                memory_scope.user_id,
                memory_scope.team_id,
                memory_scope.workspace_id,
                memory_scope.project_id,
                memory_scope.workflow_id,
                memory_scope.conversation_provider,
                memory_scope.conversation_id,
                memory_scope.topic_id,
            )
        ):
            effective_mode = "cascade"
        started = time.perf_counter()
        correlation_id = f"mem_{uuid.uuid4().hex}"
        diagnostic: MemoryRetrievalRun | None = None
        context_pack_id: str | None = None
        active_graph_results: list[dict[str, Any]] | None = None
        policy_blocked = False

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
            graph_mode = settings.memory_graph_retrieval_mode
            if graph_mode != "off":
                graph_started = time.perf_counter()
                try:
                    from shogun.services.gensui_policy_guard import check_gensui_policy

                    await check_gensui_policy(
                        "MEMORY_READ",
                        {
                            "agent_id": str(agent_id) if agent_id else None,
                            "tenant_id": memory_scope.tenant_id,
                            "project_id": memory_scope.project_id,
                            "graph_mode": graph_mode,
                        },
                    )
                    expansion = await GraphRetrievalService(self.session).expand(
                        seed_results=cascade_results,
                        scope=memory_scope,
                        agent_id=agent_id,
                    )
                    combined: list[dict[str, Any]] = []
                    combined_seen: set[str] = set()
                    for item in [*cascade_results, *expansion.results]:
                        memory_id = str(item["memory_id"])
                        if memory_id in combined_seen:
                            continue
                        combined_seen.add(memory_id)
                        combined.append(
                            {
                                **item,
                                "retrieval_source": item.get("retrieval_source", "vector"),
                            }
                        )
                    verification = await DeterministicRetrievalVerifier(self.session).verify(combined)
                    pack, pack_results, budget_excluded = await MemoryContextPackService(
                        self.session
                    ).build(
                        correlation_id=correlation_id,
                        query=query,
                        scope=memory_scope,
                        agent_id=agent_id,
                        candidates=verification.accepted,
                        excluded=[*expansion.excluded, *verification.excluded],
                        warnings=verification.warnings,
                        policy_notes=verification.policy_notes,
                    )
                    context_pack_id = str(pack.id)
                    excluded.extend(expansion.excluded)
                    excluded.extend(verification.excluded)
                    excluded.extend(budget_excluded)
                    stages.extend(
                        [
                            {
                                "name": "memory_graph_expansion",
                                **expansion.diagnostics,
                                "duration_ms": round((time.perf_counter() - graph_started) * 1000),
                                "status": "completed",
                                "mode": graph_mode,
                            },
                            {
                                "name": "verification_and_policy",
                                "candidate_count": len(combined),
                                "accepted_count": len(verification.accepted),
                                "excluded_count": len(verification.excluded),
                                "status": "completed",
                            },
                            {
                                "name": "context_pack_construction",
                                "context_pack_id": context_pack_id,
                                "included_count": len(pack.included_memory_ids),
                                "token_estimate": pack.token_estimate,
                                "status": "completed",
                            },
                        ]
                    )
                    plan = {
                        **plan,
                        "context_pack_id": context_pack_id,
                        "graph_preview_memory_ids": pack.graph_expanded_memory_ids,
                    }
                    if graph_mode == "active":
                        active_graph_results = pack_results[:limit]
                    else:
                        plan["graph_shadow_result_memory_ids"] = [
                            str(item["memory_id"]) for item in pack_results[:limit]
                        ]
                except Exception as exc:
                    if getattr(exc, "status_code", None) == 403:
                        policy_blocked = True
                        cascade_results = []
                        active_graph_results = []
                    stages.append(
                        {
                            "name": "memory_graph_expansion",
                            "status": "failed_safe",
                            "error_type": type(exc).__name__,
                            "duration_ms": round((time.perf_counter() - graph_started) * 1000),
                        }
                    )
                    excluded.append(
                        {
                            "reason": "gensui_memory_read_blocked"
                            if policy_blocked
                            else "graph_retrieval_failed_safe",
                            "error_type": type(exc).__name__,
                        }
                    )
                    plan = {
                        **plan,
                        "graph_fallback": "policy_blocked"
                        if policy_blocked
                        else "scoped_vector_results",
                    }
            if effective_mode == "shadow":
                results = (
                    []
                    if policy_blocked
                    else await self.memory.search(
                        query=query, agent_id=agent_id, limit=limit, **search_kwargs
                    )
                )
                cascade_ids = {str(item["memory_id"]) for item in cascade_results}
                excluded.extend(
                    {
                        "memory_id": str(item["memory_id"]),
                        "reason": "not_authorized_or_not_selected_by_cascade",
                    }
                    for item in results
                    if str(item["memory_id"]) not in cascade_ids
                )
                plan = {**plan, "shadow_result_memory_ids": list(cascade_ids)}
            elif graph_mode == "active" and active_graph_results is not None:
                results = active_graph_results
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
