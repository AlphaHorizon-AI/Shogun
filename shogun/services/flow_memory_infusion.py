"""Deterministic memory infusion for Agent Flow output nodes."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.schemas.agent_flow import MemoryInfusionConfig
from shogun.services.event_logger import EventLogger
from shogun.services.memory_service import MemoryService

_SENSITIVE_PATTERNS = (
    re.compile(
        r"(?i)\b(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|password|secret|authorization)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"\b(?:sk|ghp|github_pat)_[A-Za-z0-9_-]{16,}\b"),
)


@dataclass(slots=True)
class MemoryInfusionResult:
    action: str
    memory_id: str | None = None
    reason: str | None = None


def redact_sensitive_content(value: str) -> str:
    """Redact common credential shapes without logging or retaining the secret."""
    redacted = value
    for index, pattern in enumerate(_SENSITIVE_PATTERNS):
        if index == 0:
            redacted = pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def infer_output_status(predecessor_outputs: dict[str, Any]) -> str:
    """Infer success/partial/failed from structured predecessor status fields."""
    statuses: set[str] = set()

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str):
                statuses.add(status.lower())
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    collect(predecessor_outputs)
    if statuses & {"failed", "error", "blocked"}:
        return "failed"
    if statuses & {"partial", "warning", "completed_with_errors"}:
        return "partial"
    return "success"


def _output_payload(output: Any, predecessor_outputs: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {"result": output}
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            if isinstance(parsed, dict):
                payload.update(parsed)
        except (json.JSONDecodeError, TypeError):
            pass
    elif isinstance(output, dict):
        payload.update(output)

    for predecessor in predecessor_outputs.values():
        if isinstance(predecessor, dict):
            for key, value in predecessor.items():
                payload.setdefault(str(key), value)
    return payload


def _resolve_field(payload: dict[str, Any], field: str) -> tuple[bool, Any]:
    current: Any = payload
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _serialize_content(fields: list[tuple[str, Any]]) -> str:
    if len(fields) == 1 and fields[0][0] == "result":
        return str(fields[0][1])
    sections = []
    for name, value in fields:
        rendered = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False, default=str)
        sections.append(f"## {name}\n\n{rendered}")
    return "\n\n".join(sections)


def _render_title(template: str, values: dict[str, str]) -> str:
    placeholders = set(re.findall(r"{([^{}]+)}", template))
    unsupported = placeholders - set(values)
    if unsupported:
        raise ValueError(f"Unsupported memory title placeholders: {', '.join(sorted(unsupported))}")
    return template.format_map(values).strip()[:500]


async def _audit(result: MemoryInfusionResult, detail: dict[str, Any], agent_id: uuid.UUID | None = None) -> None:
    try:
        await EventLogger.emit(
            category="memory",
            event_type=f"memory.flow_infusion.{result.action}",
            action=f"Agent Flow memory infusion {result.action}",
            result="success" if result.action in {"stored", "deduplicated"} else "skipped",
            agent_id=str(agent_id) if agent_id else None,
            memory_ids=[result.memory_id] if result.memory_id else [],
            detail={**detail, "reason": result.reason},
        )
    except Exception:
        pass


async def infuse_flow_output_memory(
    *,
    session: AsyncSession,
    raw_config: dict[str, Any] | None,
    flow_id: uuid.UUID,
    flow_name: str,
    run_id: uuid.UUID,
    node_id: uuid.UUID,
    node_label: str,
    output: Any,
    predecessor_outputs: dict[str, Any],
) -> MemoryInfusionResult:
    """Store configured output fields as a governed, deduplicated memory."""
    config = MemoryInfusionConfig.model_validate(raw_config or {})
    if not config.enabled:
        return MemoryInfusionResult(action="disabled")

    output_status = infer_output_status(predecessor_outputs)
    if config.store_on != "always" and output_status != config.store_on:
        result = MemoryInfusionResult(action="status_skipped", reason=f"output status was {output_status}")
        await _audit(result, {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)})
        return result

    payload = _output_payload(output, predecessor_outputs)
    available: list[tuple[str, Any]] = []
    missing: list[str] = []
    for field in config.content_fields:
        found, value = _resolve_field(payload, field)
        if found and value not in (None, "", [], {}):
            available.append((field, value))
        else:
            missing.append(field)

    if missing and config.on_missing_field == "fail":
        raise ValueError(f"Memory infusion fields missing from output: {', '.join(missing)}")
    if missing and config.on_missing_field == "skip":
        result = MemoryInfusionResult(action="field_skipped", reason=f"missing fields: {', '.join(missing)}")
        await _audit(result, {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)})
        return result
    if not available:
        result = MemoryInfusionResult(action="field_skipped", reason="no configured fields contained data")
        await _audit(result, {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)})
        return result

    content = _serialize_content(available)
    if config.redact_sensitive:
        content = redact_sensitive_content(content)
    content = content[: config.max_content_length]
    digest = hashlib.sha256(" ".join(content.lower().split()).encode("utf-8")).hexdigest()

    agent = await session.scalar(
        select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)).limit(1)
    )
    if not agent:
        raise ValueError("Memory infusion requires an active primary Shogun agent")

    memory_service = MemoryService(session)
    if config.deduplication.mode != "none":
        exact = await session.scalar(
            select(MemoryRecord).where(
                MemoryRecord.agent_id == agent.id,
                MemoryRecord.content_hash == digest,
                MemoryRecord.is_archived.is_(False),
            )
        )
        if exact:
            await memory_service.reinforce(exact.id, "reused_across_sessions")
            result = MemoryInfusionResult(action="deduplicated", memory_id=str(exact.id), reason="exact match")
            await _audit(
                result,
                {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)},
                agent.id,
            )
            return result

    if config.deduplication.mode == "semantic":
        try:
            candidates = await memory_service.search(
                content,
                agent_id=agent.id,
                memory_types=[config.memory_type],
                limit=3,
            )
            duplicate = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.get("scores", {}).get("semantic_similarity", 0)
                    >= config.deduplication.semantic_threshold
                ),
                None,
            )
            if duplicate:
                duplicate_id = uuid.UUID(str(duplicate["memory_id"]))
                await memory_service.reinforce(duplicate_id, "reused_across_sessions")
                result = MemoryInfusionResult(
                    action="deduplicated",
                    memory_id=str(duplicate_id),
                    reason="semantic match",
                )
                await _audit(
                    result,
                    {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)},
                    agent.id,
                )
                return result
        except Exception as exc:
            # Exact deduplication already ran. A vector outage must not discard
            # an otherwise valid configured memory.
            await _audit(
                MemoryInfusionResult(action="semantic_unavailable", reason=type(exc).__name__),
                {"flow_id": str(flow_id), "run_id": str(run_id), "node_id": str(node_id)},
                agent.id,
            )

    now = datetime.now(timezone.utc)
    title = _render_title(
        config.title_template,
        {
            "flow_name": flow_name,
            "node_label": node_label,
            "timestamp": now.isoformat(timespec="seconds"),
            "run_id": str(run_id),
        },
    )
    tags = list(
        dict.fromkeys(
            [
                *config.tags,
                "auto-stored",
                "flow-output",
                f"flow:{flow_id}",
                f"node:{node_id}",
            ]
        )
    )[:30]
    summary_value = next((value for name, value in available if name == "summary"), None)
    summary = str(summary_value)[:1000] if summary_value is not None else None
    if summary and config.redact_sensitive:
        summary = redact_sensitive_content(summary)
    record = await memory_service.create_memory(
        agent_id=agent.id,
        memory_type=config.memory_type,
        title=title,
        content=content,
        summary=summary,
        source_type="flow_output",
        source_ref_id=run_id,
        source_system="agent_flow",
        source_external_id=f"{flow_id}:{node_id}:{run_id}",
        content_hash=digest,
        relevance_score=config.importance,
        importance_score=config.importance,
        confidence_score=0.8,
        decay_class=config.decay_type,
        is_pinned=config.decay_type == "pinned",
        tags=tags,
    )
    result = MemoryInfusionResult(action="stored", memory_id=str(record.id))
    await _audit(
        result,
        {
            "flow_id": str(flow_id),
            "flow_name": flow_name,
            "run_id": str(run_id),
            "node_id": str(node_id),
            "node_label": node_label,
            "content_fields": config.content_fields,
            "output_status": output_status,
            "redacted": config.redact_sensitive,
            "content_length": len(content),
        },
        agent.id,
    )
    return result
