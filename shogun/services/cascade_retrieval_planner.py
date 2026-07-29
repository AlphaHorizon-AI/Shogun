"""Explicit narrow-to-broad planner for governed cascade retrieval."""

from __future__ import annotations

from typing import Any

from shogun.config import settings
from shogun.schemas.memory import MemoryScopeEnvelope


class CascadeRetrievalPlanner:
    STAGE_FIELDS = (
        ("topic_memory", "topic_id"),
        ("conversation_memory", "conversation_id"),
        ("workspace_memory", "workspace_id"),
        ("project_memory", "project_id"),
        ("workflow_memory", "workflow_id"),
        ("team_memory", "team_id"),
        ("user_memory", "user_id"),
    )

    def build(self, scope: MemoryScopeEnvelope, *, graph_mode: str = "off") -> dict[str, Any]:
        stages = [
            {
                "name": name,
                "source": "qdrant_and_memory_records",
                "query_type": "semantic",
                "required_scope_field": field,
                "scope_value": getattr(scope, field),
                "max_results": settings.memory_cascade_stage_limit,
                "requires_verification": True,
                "policy_filter": True,
            }
            for name, field in self.STAGE_FIELDS
            if getattr(scope, field)
        ]
        stages.append(
            {
                "name": "agent_memory",
                "source": "qdrant_and_memory_records",
                "query_type": "semantic",
                "required_scope_field": None,
                "scope_value": None,
                "max_results": settings.memory_cascade_stage_limit,
                "requires_verification": True,
                "policy_filter": True,
            }
        )
        stages = stages[: settings.memory_cascade_max_stages]
        if graph_mode != "off":
            stages.extend(
                [
                    {
                        "name": "memory_graph_expansion",
                        "source": "memory_graph",
                        "query_type": "graph_expansion",
                        "max_depth": min(settings.memory_graph_max_depth, 2),
                        "max_results": settings.memory_graph_max_expansion_results,
                        "requires_verification": True,
                        "policy_filter": True,
                        "mode": graph_mode,
                    },
                    {
                        "name": "verification_and_policy",
                        "source": "kiroku_verifier",
                        "query_type": "deterministic_verification",
                        "requires_verification": True,
                        "policy_filter": True,
                    },
                    {
                        "name": "context_pack_construction",
                        "source": "context_pack_builder",
                        "query_type": "bounded_context_pack",
                        "max_tokens": settings.memory_context_pack_max_tokens,
                    },
                ]
            )
        return {
            "strategy": "narrow_to_broad",
            "stop_after_results": settings.memory_cascade_min_results,
            "graph_mode": graph_mode,
            "stages": stages,
        }
