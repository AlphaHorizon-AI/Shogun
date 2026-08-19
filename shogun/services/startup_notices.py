"""Persist sanitized, lifecycle-aware startup notices for the Tenshu dashboard."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shogun.config import PROJECT_ROOT

_LOCK = threading.RLock()
_NOTICE_PATH = PROJECT_ROOT / "data" / "startup_notices.json"
_RESOLVED_LIMIT = 20
_NOTICE_NAMESPACE = uuid.UUID("88366b3a-b7de-46a8-a560-f54ee5d11d4a")
_SEVERITIES = {"info", "warning", "error"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_code(value: Any) -> str:
    code = str(value or "startup_warning").strip()[:80]
    return code or "startup_warning"


def _stable_id(code: str) -> str:
    return uuid.uuid5(_NOTICE_NAMESPACE, code).hex


def _safe_count(value: Any) -> int:
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 1


def _read_payload() -> list[Any]:
    try:
        payload = json.loads(_NOTICE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    # Versioned/object storage was briefly used by development builds. Accept
    # it as well as the original top-level list so upgrades never lose notices.
    if isinstance(payload, dict):
        payload = payload.get("notices", [])
    return payload if isinstance(payload, list) else []


def _normalise_notice(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    code = _clean_code(raw.get("code"))
    first_seen = str(raw.get("first_seen_at") or raw.get("created_at") or _now())
    last_seen = str(raw.get("last_seen_at") or raw.get("updated_at") or first_seen)
    resolved_at = raw.get("resolved_at")
    active = bool(raw.get("active", raw.get("status") != "resolved" and not resolved_at))
    if active:
        resolved_at = None
    severity = raw.get("severity")
    return {
        "id": _stable_id(code),
        "code": code,
        "severity": severity if severity in _SEVERITIES else "warning",
        "message": str(raw.get("message") or "Startup initialization did not complete.")[:500],
        # Keep created_at for older clients while exposing explicit lifecycle fields.
        "created_at": first_seen,
        "first_seen_at": first_seen,
        "last_seen_at": last_seen,
        "occurrence_count": _safe_count(raw.get("occurrence_count")),
        "active": active,
        "status": "active" if active else "resolved",
        "resolved_at": None if active else str(resolved_at or last_seen),
    }


def _read() -> list[dict[str, Any]]:
    """Read and consolidate both legacy append-only and lifecycle records."""
    by_code: dict[str, dict[str, Any]] = {}
    for raw in _read_payload():
        notice = _normalise_notice(raw)
        if notice is None:
            continue
        previous = by_code.get(notice["code"])
        if previous is None:
            by_code[notice["code"]] = notice
            continue

        if notice["last_seen_at"] >= previous["last_seen_at"]:
            previous["message"] = notice["message"]
            previous["severity"] = notice["severity"]
        previous["first_seen_at"] = min(previous["first_seen_at"], notice["first_seen_at"])
        previous["created_at"] = previous["first_seen_at"]
        previous["last_seen_at"] = max(previous["last_seen_at"], notice["last_seen_at"])
        previous["occurrence_count"] += notice["occurrence_count"]
        previous["active"] = previous["active"] or notice["active"]
        previous["status"] = "active" if previous["active"] else "resolved"
        previous["resolved_at"] = (
            None
            if previous["active"]
            else max(str(previous["resolved_at"] or ""), str(notice["resolved_at"] or "")) or None
        )
    return list(by_code.values())


def _retained(notices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = [notice for notice in notices if notice["active"]]
    resolved = sorted(
        (notice for notice in notices if not notice["active"]),
        key=lambda notice: notice["last_seen_at"],
        reverse=True,
    )[:_RESOLVED_LIMIT]
    return sorted(active + resolved, key=lambda notice: notice["last_seen_at"])


def _write(notices: list[dict[str, Any]]) -> bool:
    """Atomically replace the notice file; callers already hold ``_LOCK``."""
    temporary_path: Path | None = None
    try:
        _NOTICE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=_NOTICE_PATH.parent,
            prefix=f".{_NOTICE_PATH.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(_retained(notices), temporary, indent=2)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, _NOTICE_PATH)
        return True
    except OSError:
        # A notice must never replace the original startup failure when the
        # data volume is unavailable or read-only.
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        return False


def record_startup_notice(code: str, message: str, severity: str = "warning") -> None:
    """Create or reactivate one operator-safe notice identified by stable code."""
    code = _clean_code(code)
    timestamp = _now()
    with _LOCK:
        notices = _read()
        notice = next((item for item in notices if item["code"] == code), None)
        if notice is None:
            notice = {
                "id": _stable_id(code),
                "code": code,
                "created_at": timestamp,
                "first_seen_at": timestamp,
                "occurrence_count": 0,
            }
            notices.append(notice)
        notice.update(
            {
                "severity": severity if severity in _SEVERITIES else "warning",
                "message": str(message)[:500],
                "last_seen_at": timestamp,
                "occurrence_count": _safe_count(notice.get("occurrence_count")) + 1
                if notice.get("occurrence_count")
                else 1,
                "active": True,
                "status": "active",
                "resolved_at": None,
            }
        )
        _write(notices)


def resolve_startup_notice(code: str) -> bool:
    """Resolve an existing notice after its corresponding startup stage succeeds."""
    code = _clean_code(code)
    with _LOCK:
        notices = _read()
        notice = next((item for item in notices if item["code"] == code), None)
        if notice is None or not notice["active"]:
            return False
        notice["active"] = False
        notice["status"] = "resolved"
        notice["resolved_at"] = _now()
        return _write(notices)


def list_startup_notices(*, active_only: bool = True) -> list[dict[str, Any]]:
    """List active notices by default, newest occurrence first."""
    with _LOCK:
        notices = _read()
        if active_only:
            notices = [notice for notice in notices if notice["active"]]
        return sorted(notices, key=lambda notice: notice["last_seen_at"], reverse=True)
