"""Privacy-safe, operator-controlled ecosystem telemetry for OpenClaw College."""

from __future__ import annotations

import asyncio
import hashlib
import json
import locale
import logging
import secrets
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from shogun import __version__
from shogun.config import settings

log = logging.getLogger(__name__)

CONFIG_PATH = Path(settings.config_path) / "college_telemetry.json"
INGEST_URL = "https://www.openclawcollege.com/api/v1/intelligence/events"
_tasks: set[asyncio.Task] = set()
_last_status: dict[str, Any] = {"state": "never", "at": None, "error": None}


def _default_config() -> dict[str, Any]:
    return {"enabled": False, "installation_salt": "", "schema_version": 1}


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {**_default_config(), **data}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return _default_config()


def save_config(*, enabled: bool) -> dict[str, Any]:
    current = load_config()
    current["enabled"] = bool(enabled)
    current["installation_salt"] = current.get("installation_salt") or secrets.token_hex(32)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    return public_config(current)


def public_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    return {
        "enabled": bool(config.get("enabled", False)),
        "schema_version": 1,
        "endpoint": INGEST_URL,
        "shared_fields": [
            "model", "provider", "coarse task type", "success", "token/latency/cost buckets",
            "local or cloud", "Shogun version", "country code", "rotating anonymous installation hash",
        ],
        "never_shared": [
            "prompts", "outputs", "files", "agent names", "credentials", "exact IP addresses",
        ],
        "last_delivery": dict(_last_status),
    }


def _country_code() -> str:
    if sys.platform == "win32":
        try:
            import ctypes

            buffer = ctypes.create_unicode_buffer(16)
            if ctypes.windll.kernel32.GetUserDefaultGeoName(buffer, len(buffer)):
                value = buffer.value.upper()
                if len(value) == 2 and value.isalpha():
                    return value
        except Exception:
            pass
    try:
        language = locale.getlocale()[0] or ""
        region = language.replace("-", "_").split("_")[-1].upper()
        if len(region) == 2 and region.isalpha():
            return region
    except Exception:
        pass
    return "ZZ"


def _bucket(value: float, thresholds: list[tuple[float, str]], fallback: str) -> str:
    if value <= 0:
        return fallback
    for ceiling, label in thresholds:
        if value < ceiling:
            return label
    return thresholds[-1][1]


def build_model_usage_event(body: Any, decision: Any | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    config = load_config()
    salt = config.get("installation_salt") or secrets.token_hex(32)
    rotation = now.strftime("%G-W%V")
    installation_hash = hashlib.sha256(f"{salt}:{rotation}".encode()).hexdigest()[:32]
    provider = str(body.provider or "unknown")
    local_providers = {"ollama", "lmstudio", "lm-studio", "local", "llamacpp", "vllm"}
    return {
        "eventId": f"evt-{uuid.uuid4().hex}",
        "schemaVersion": 1,
        "eventType": "model_usage",
        "occurredAt": now.replace(minute=0, second=0, microsecond=0).isoformat(),
        "installationHash": installation_hash,
        "shogunVersion": __version__,
        "country": _country_code(),
        "model": str(body.model_id)[:120],
        "provider": provider[:80],
        "taskType": str(getattr(decision, "task_type", None) or "unclassified")[:80],
        "locality": "local" if provider.lower() in local_providers else "cloud",
        "success": bool(body.success),
        "inputTokens": _bucket(body.input_tokens, [(1000, "1-1k"), (4000, "1k-4k"), (16000, "4k-16k"), (float("inf"), "16k+")], "0"),
        "outputTokens": _bucket(body.output_tokens, [(500, "1-500"), (2000, "500-2k"), (8000, "2k-8k"), (float("inf"), "8k+")], "0"),
        "latency": _bucket(body.latency_ms, [(1000, "<1s"), (3000, "1-3s"), (10000, "3-10s"), (30000, "10-30s"), (float("inf"), "30s+")], "unknown"),
        "cost": _bucket(body.estimated_cost, [(0.0000001, "free"), (0.01, "<$0.01"), (0.1, "$0.01-0.10"), (1, "$0.10-1"), (float("inf"), "$1+")], "unknown"),
    }


async def _deliver(payload: dict[str, Any]) -> None:
    global _last_status
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(INGEST_URL, json={"events": [payload]})
            response.raise_for_status()
        _last_status = {"state": "delivered", "at": datetime.now(timezone.utc).isoformat(), "error": None}
    except Exception as exc:
        _last_status = {"state": "failed", "at": datetime.now(timezone.utc).isoformat(), "error": str(exc)[:240]}
        log.debug("College ecosystem telemetry delivery failed: %s", exc)


def queue_model_usage(body: Any, decision: Any | None = None) -> bool:
    if not load_config().get("enabled", False):
        return False
    task = asyncio.create_task(_deliver(build_model_usage_event(body, decision)))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True
