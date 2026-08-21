"""Consent-gated, operator-controlled ecosystem telemetry for OpenClaw College."""

from __future__ import annotations

import asyncio
import hashlib
import json
import locale
import logging
import os
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
CONSENT_NOTICE_VERSION = "1.0"
MODEL_USAGE_EVENT_FIELDS = (
    "eventId",
    "schemaVersion",
    "eventType",
    "occurredAt",
    "installationHash",
    "shogunVersion",
    "country",
    "model",
    "provider",
    "taskType",
    "locality",
    "success",
    "inputTokens",
    "outputTokens",
    "latency",
    "cost",
)
MODEL_USAGE_FIELD_DESCRIPTIONS = {
    "eventId": "random identifier generated for this event",
    "schemaVersion": "fixed event schema version 1",
    "eventType": "fixed value model_usage",
    "occurredAt": "UTC event timestamp rounded down to the hour",
    "installationHash": "pseudonymous installation hash rotated each ISO week",
    "shogunVersion": "installed Shogun version",
    "country": "country code derived from the OS or locale, or ZZ when unavailable",
    "model": "configured model identifier sent verbatim, truncated to 120 characters",
    "provider": "configured provider identifier sent verbatim, truncated to 80 characters",
    "taskType": "routing task type sent verbatim, truncated to 80 characters, or unclassified",
    "locality": "local or cloud",
    "success": "success boolean",
    "inputTokens": "bucketed input-token count",
    "outputTokens": "bucketed output-token count",
    "latency": "bucketed latency",
    "cost": "bucketed estimated cost",
}
_tasks: set[asyncio.Task] = set()
_last_status: dict[str, Any] = {"state": "never", "at": None, "error": None}


def _default_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "installation_salt": "",
        "schema_version": 1,
        "consent_notice_version": None,
        "consented_at": None,
    }


def _persist_config(config: dict[str, Any]) -> None:
    """Persist the local telemetry choice and pseudonymous identity."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_name(
        f".{CONFIG_PATH.name}.{secrets.token_hex(8)}.tmp"
    )
    try:
        temporary.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(CONFIG_PATH)
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _has_current_consent(config: dict[str, Any]) -> bool:
    """Return true only for an explicit, current, time-stamped local opt-in."""
    if config.get("enabled") is not True:
        return False
    if config.get("consent_notice_version") != CONSENT_NOTICE_VERSION:
        return False
    salt = config.get("installation_salt")
    if (
        not isinstance(salt, str)
        or len(salt) != 64
        or any(character not in "0123456789abcdef" for character in salt)
    ):
        return False
    consented_at = config.get("consented_at")
    if not isinstance(consented_at, str):
        return False
    try:
        parsed = datetime.fromisoformat(consented_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            config = {**_default_config(), **data}
            # Older releases enabled this stream without recording affirmative
            # consent.  That state is deliberately not grandfathered in.
            if not _has_current_consent(config):
                sanitized = {
                    **config,
                    "enabled": False,
                    "installation_salt": "",
                    "consent_notice_version": None,
                    "consented_at": None,
                }
                if sanitized != config:
                    _persist_config(sanitized)
                config = sanitized
            return config
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    config = _default_config()
    try:
        _persist_config(config)
    except OSError:
        # Read-only or damaged installations remain safely opted out.
        pass
    return config


def save_config(
    *,
    enabled: bool,
    notice_version: str | None = None,
    confirmed: bool = False,
) -> dict[str, Any]:
    """Persist an explicit choice; enabling requires the current notice."""
    current = load_config()
    if enabled:
        if confirmed is not True or notice_version != CONSENT_NOTICE_VERSION:
            raise ValueError(
                "OpenClaw College telemetry requires explicit acceptance of "
                f"notice version {CONSENT_NOTICE_VERSION}."
            )
        current.update(
            enabled=True,
            installation_salt=secrets.token_hex(32),
            consent_notice_version=CONSENT_NOTICE_VERSION,
            consented_at=datetime.now(timezone.utc).isoformat(),
        )
    else:
        # Revocation is immediate and also rotates away the local pseudonymous
        # identifier so a later opt-in starts a fresh identity.
        current.update(
            enabled=False,
            installation_salt="",
            consent_notice_version=None,
            consented_at=None,
        )
    _persist_config(current)
    return public_config(current)


def public_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config()
    return {
        "enabled": _has_current_consent(config),
        "schema_version": 1,
        "consent_notice_version": CONSENT_NOTICE_VERSION,
        "consented_at": config.get("consented_at") if _has_current_consent(config) else None,
        "purpose": (
            "Contribute pseudonymous model/provider usage and bucketed performance "
            "metrics to OpenClaw College ecosystem benchmarks."
        ),
        "recipient": "OpenClaw College",
        "request_method": "POST",
        "endpoint": INGEST_URL,
        "request_envelope": "events[]",
        "network_disclosure": (
            "The exact IP address is not included in the application payload. "
            "As with any network request, the recipient and network intermediaries "
            "may process connection metadata under their applicable terms."
        ),
        "identifier_warning": (
            "Configured model, provider, and task identifiers are sent as text. "
            "Do not opt in if those identifiers contain tenant, customer, project, "
            "person, filename, prompt, credential, secret, or other sensitive values."
        ),
        "shared_fields": list(MODEL_USAGE_EVENT_FIELDS),
        "shared_field_details": [
            {
                "field": field,
                "description": MODEL_USAGE_FIELD_DESCRIPTIONS[field],
            }
            for field in MODEL_USAGE_EVENT_FIELDS
        ],
        "never_shared": [
            "prompt or output content as dedicated fields",
            "file content, filenames, or paths as dedicated fields",
            "agent name as a dedicated field",
            "credentials as dedicated fields",
            "exact IP address as an application payload field",
            "security and incident-reporting acknowledgement",
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
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
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
        "inputTokens": _bucket(
            body.input_tokens,
            [(1000, "1-1k"), (4000, "1k-4k"), (16000, "4k-16k"), (float("inf"), "16k+")],
            "0",
        ),
        "outputTokens": _bucket(
            body.output_tokens,
            [(500, "1-500"), (2000, "500-2k"), (8000, "2k-8k"), (float("inf"), "8k+")],
            "0",
        ),
        "latency": _bucket(
            body.latency_ms,
            [
                (1000, "<1s"),
                (3000, "1-3s"),
                (10000, "3-10s"),
                (30000, "10-30s"),
                (float("inf"), "30s+"),
            ],
            "unknown",
        ),
        "cost": _bucket(
            body.estimated_cost,
            [
                (0.0000001, "free"),
                (0.01, "<$0.01"),
                (0.1, "$0.01-0.10"),
                (1, "$0.10-1"),
                (float("inf"), "$1+"),
            ],
            "unknown",
        ),
    }


async def _deliver(payload: dict[str, Any]) -> None:
    global _last_status
    # Re-check immediately before network I/O so revocation also cancels a task
    # that was queued while consent was still active.
    if not _has_current_consent(load_config()):
        return
    if set(payload) != set(MODEL_USAGE_EVENT_FIELDS) or not all(
        isinstance(value, (str, int, bool)) for value in payload.values()
    ):
        _last_status = {
            "state": "rejected",
            "at": datetime.now(timezone.utc).isoformat(),
            "error": "Payload did not match the approved College telemetry schema.",
        }
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(INGEST_URL, json={"events": [payload]})
            response.raise_for_status()
        _last_status = {"state": "delivered", "at": datetime.now(timezone.utc).isoformat(), "error": None}
    except Exception as exc:
        _last_status = {"state": "failed", "at": datetime.now(timezone.utc).isoformat(), "error": str(exc)[:240]}
        log.debug("College ecosystem telemetry delivery failed: %s", exc)


def queue_model_usage(body: Any, decision: Any | None = None) -> bool:
    if not _has_current_consent(load_config()):
        return False
    task = asyncio.create_task(_deliver(build_model_usage_event(body, decision)))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True
