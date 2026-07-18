"""Validation and governance for agent-requested memory decay behavior."""

from __future__ import annotations

from typing import Any

from shogun.config import settings
from shogun.schemas.common import DecayClass

ALLOWED_DECAY_TYPES = tuple(item.value for item in DecayClass)


class MemoryDecayError(ValueError):
    """A decay request violates the canonical contract or memory policy."""

    def __init__(self, message: str, *, code: str, allowed_values: tuple[str, ...] = ()):
        super().__init__(message)
        self.code = code
        self.allowed_values = allowed_values

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "error", "error": self.code, "message": str(self)}
        if self.allowed_values:
            result["allowed_values"] = list(self.allowed_values)
        return result


def validate_decay_type(value: Any) -> str | None:
    """Return a canonical decay type, treating null as omitted."""
    if value is None:
        return None
    normalized = value.value if isinstance(value, DecayClass) else str(value).strip().lower()
    if normalized not in ALLOWED_DECAY_TYPES:
        raise MemoryDecayError(
            f"Invalid decay_type '{value}'.",
            code="invalid_decay_type",
            allowed_values=ALLOWED_DECAY_TYPES,
        )
    return normalized


def validate_agent_decay_request(
    value: Any,
    *,
    importance: float,
    memory_type: str,
) -> str | None:
    """Validate explicit decay control requested by an agent tool call."""
    decay_type = validate_decay_type(value)
    if decay_type != DecayClass.STICKY.value:
        return decay_type

    if not settings.memory_allow_agent_sticky_memory:
        raise MemoryDecayError(
            "Agent-created sticky memories are disabled by memory policy.",
            code="sticky_memory_not_allowed",
        )
    if importance < settings.memory_sticky_requires_min_importance:
        raise MemoryDecayError(
            "Sticky memory requires importance of at least "
            f"{settings.memory_sticky_requires_min_importance}.",
            code="sticky_memory_importance_too_low",
        )

    allowed_types = {
        item.strip().lower()
        for item in settings.memory_sticky_allowed_types.split(",")
        if item.strip()
    }
    if memory_type.lower() not in allowed_types:
        raise MemoryDecayError(
            f"Memory type '{memory_type}' is not allowed to be sticky.",
            code="sticky_memory_type_not_allowed",
            allowed_values=tuple(sorted(allowed_types)),
        )
    return decay_type
