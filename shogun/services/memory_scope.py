"""Canonical Phase 1 memory scope authorization helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_record import MemoryRecord
from shogun.schemas.memory import MemoryScopeEnvelope

SENSITIVITY_ORDER = ("public", "internal", "confidential", "restricted")
SCOPE_FIELDS = (
    "user_id",
    "team_id",
    "workspace_id",
    "project_id",
    "workflow_id",
    "conversation_id",
    "topic_id",
)


def coerce_scope(scope: MemoryScopeEnvelope | dict[str, Any] | None) -> MemoryScopeEnvelope | None:
    if scope is None or isinstance(scope, MemoryScopeEnvelope):
        return scope
    return MemoryScopeEnvelope.model_validate(scope)


def resolve_active_memory_scope(
    scope: MemoryScopeEnvelope | dict[str, Any] | None = None,
) -> MemoryScopeEnvelope:
    """Resolve an explicit scope or the active connector request context."""
    explicit = coerce_scope(scope)
    if explicit is not None:
        return explicit
    try:
        from shogun.services.memory_routing_context import current_memory_routing

        connector_scope = current_memory_routing()
        if connector_scope:
            return MemoryScopeEnvelope.model_validate(connector_scope)
    except Exception:
        pass
    try:
        from shogun.services.telegram_routing_context import current_telegram_routing

        routing = current_telegram_routing() or {}
    except Exception:
        routing = {}
    chat_id = str(routing.get("chat_id") or "").strip()
    if chat_id:
        sender_id = str(routing.get("sender_id") or "").strip()
        chat_type = str(routing.get("chat_type") or "").strip().lower()
        thread_id = routing.get("message_thread_id")
        return MemoryScopeEnvelope(
            tenant_id="local",
            # Private chats are principal-scoped. Group/forum memories are
            # shared inside their conversation/topic boundary.
            user_id=f"telegram:{sender_id}" if sender_id and chat_type == "private" else None,
            conversation_provider="telegram",
            conversation_id=chat_id,
            topic_id=str(thread_id) if thread_id is not None else None,
        )
    return MemoryScopeEnvelope()


def allowed_sensitivities(ceiling: str) -> list[str]:
    try:
        index = SENSITIVITY_ORDER.index(ceiling)
    except ValueError as exc:
        raise ValueError(f"Unsupported memory sensitivity ceiling: {ceiling}") from exc
    return list(SENSITIVITY_ORDER[: index + 1])


def scope_values(scope: MemoryScopeEnvelope | None) -> dict[str, str | None]:
    if scope is None:
        return {}
    return {field: getattr(scope, field) for field in SCOPE_FIELDS}


def authorization_predicates(
    *,
    scope: MemoryScopeEnvelope,
    agent_id: uuid.UUID | None,
    required_scope_field: str | None = None,
) -> list[Any]:
    """Build deny-by-default relational predicates for a retrieval stage.

    Populated memory dimensions may only be read when the request carries the
    same dimension. A stage may require one exact dimension (for example,
    topic_id) while inherited/global records are reserved for later stages.
    """
    if required_scope_field and required_scope_field not in SCOPE_FIELDS:
        raise ValueError(f"Unsupported required scope field: {required_scope_field}")

    predicates: list[Any] = [
        MemoryRecord.tenant_id == scope.tenant_id,
        MemoryRecord.sensitivity.in_(allowed_sensitivities(scope.sensitivity_ceiling)),
        MemoryRecord.is_archived.is_(False),
    ]
    if agent_id is not None:
        predicates.append(MemoryRecord.agent_id == agent_id)

    for field in SCOPE_FIELDS:
        requested = getattr(scope, field)
        column = getattr(MemoryRecord, field)
        if field == required_scope_field:
            if requested is None:
                return [MemoryRecord.id.is_(None)]
            predicates.append(column == requested)
        elif requested is None:
            predicates.append(column.is_(None))
        else:
            predicates.append(or_(column.is_(None), column == requested))

    if not scope.include_legacy_agent_memory:
        predicates.append(MemoryRecord.scope_status != "agent_private")
    return predicates


async def authorized_memory_ids(
    session: AsyncSession,
    *,
    scope: MemoryScopeEnvelope,
    agent_id: uuid.UUID | None,
    required_scope_field: str | None = None,
    memory_types: list[str] | None = None,
    min_importance: float | None = None,
    pinned_only: bool = False,
) -> list[str]:
    predicates = authorization_predicates(
        scope=scope,
        agent_id=agent_id,
        required_scope_field=required_scope_field,
    )
    if memory_types:
        predicates.append(MemoryRecord.memory_type.in_(memory_types))
    if min_importance is not None:
        predicates.append(MemoryRecord.importance_score >= min_importance)
    if pinned_only:
        predicates.append(MemoryRecord.is_pinned.is_(True))
    rows = await session.scalars(select(MemoryRecord.id).where(*predicates))
    return [str(memory_id) for memory_id in rows]
