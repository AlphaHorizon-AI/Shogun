"""Data-driven model reasoning controls and request payload translation."""

from __future__ import annotations

import json
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "resources" / "model_reasoning_capabilities.json"
_EFFORTS = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    try:
        payload = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": 0, "providers": {}}
    return payload if isinstance(payload, dict) else {"version": 0, "providers": {}}


def _catalog_provider_and_model(provider_type: str, model_id: str) -> tuple[str, str]:
    provider = str(provider_type or "").strip().casefold()
    model = str(model_id or "").strip().casefold()
    if provider == "openrouter" and model.startswith("openai/"):
        return "openai", model.removeprefix("openai/")
    if provider == "custom" and model.startswith(("gpt-", "o1", "o3", "o4-")):
        return "openai", model
    return provider, model


def reasoning_capability(provider_type: str, model_id: str) -> dict[str, Any] | None:
    """Return the supported reasoning effort contract for one physical model."""

    provider, model = _catalog_provider_and_model(provider_type, model_id)
    rules = (_catalog().get("providers") or {}).get(provider) or []
    for rule in rules:
        patterns = rule.get("patterns") or []
        if any(fnmatchcase(model, str(pattern).casefold()) for pattern in patterns):
            supported = [
                str(value).casefold()
                for value in (rule.get("supported_efforts") or [])
                if str(value).casefold() in _EFFORTS
            ]
            if not supported:
                return None
            default = str(rule.get("provider_default") or "").casefold() or None
            return {
                "type": "effort_enum",
                "supported_efforts": supported,
                "provider_default": default if default in supported else None,
                "catalog_version": int(_catalog().get("version") or 0),
            }
    return None


def validate_reasoning_effort(provider_type: str, model_id: str, effort: str | None) -> str | None:
    """Validate a saved or per-request effort against the selected model."""

    if effort is None or not str(effort).strip():
        return None
    normalized = str(effort).strip().casefold()
    capability = reasoning_capability(provider_type, model_id)
    if not capability:
        raise ValueError(f"Model {model_id!r} has no configurable reasoning effort in the installed catalog")
    if normalized not in capability["supported_efforts"]:
        allowed = ", ".join(capability["supported_efforts"])
        raise ValueError(f"Model {model_id!r} does not support reasoning effort {normalized!r}; allowed: {allowed}")
    return normalized


def configured_reasoning_effort(
    provider_type: str,
    model_id: str,
    provider_config: dict[str, Any] | None,
    explicit_effort: str | None = None,
) -> str | None:
    """Resolve an explicit/profile effort before the provider-level model default."""

    configured = (provider_config or {}).get("model_reasoning") or {}
    selected = explicit_effort if explicit_effort is not None else configured.get(model_id)
    return validate_reasoning_effort(provider_type, model_id, selected) if selected else None


def validate_model_reasoning_config(provider_type: str, config: dict[str, Any] | None) -> dict[str, str]:
    """Validate every per-model reasoning default stored on a provider connection."""

    config = config or {}
    models = {str(value) for value in (config.get("models") or []) if value}
    raw = config.get("model_reasoning") or {}
    if not isinstance(raw, dict):
        raise ValueError("model_reasoning must be an object keyed by model ID")
    normalized: dict[str, str] = {}
    for model_id, effort in raw.items():
        model_id = str(model_id).strip()
        if not model_id or (models and model_id not in models):
            raise ValueError(f"Reasoning configuration references an unselected model: {model_id!r}")
        value = validate_reasoning_effort(provider_type, model_id, str(effort) if effort is not None else None)
        if value:
            normalized[model_id] = value
    return normalized


def apply_chat_reasoning(
    payload: dict[str, Any],
    *,
    provider_type: str,
    model_id: str,
    provider_config: dict[str, Any] | None,
    explicit_effort: str | None = None,
) -> str | None:
    """Apply reasoning to an OpenAI-compatible Chat Completions request safely."""

    effort = configured_reasoning_effort(provider_type, model_id, provider_config, explicit_effort)
    if not effort:
        return None
    payload["reasoning_effort"] = effort
    # GPT-5 family endpoints reject sampling controls at non-zero reasoning effort.
    if effort != "none" and _catalog_provider_and_model(provider_type, model_id)[0] == "openai":
        payload.pop("temperature", None)
        payload.pop("top_p", None)
        payload.pop("logprobs", None)
    return effort
