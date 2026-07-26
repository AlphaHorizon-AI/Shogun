"""Persist sanitized startup notices for the Tenshu dashboard."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone

from shogun.config import PROJECT_ROOT

_LOCK = threading.Lock()
_NOTICE_PATH = PROJECT_ROOT / "data" / "startup_notices.json"
_LIMIT = 20


def _read() -> list[dict]:
    try:
        payload = json.loads(_NOTICE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    return payload if isinstance(payload, list) else []


def record_startup_notice(code: str, message: str, severity: str = "warning") -> None:
    """Record operator-safe text without persisting exception details."""
    notice = {
        "id": uuid.uuid4().hex,
        "code": code[:80],
        "severity": severity if severity in {"info", "warning", "error"} else "warning",
        "message": message[:500],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with _LOCK:
        notices = _read()
        notices.append(notice)
        try:
            _NOTICE_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = _NOTICE_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(notices[-_LIMIT:], indent=2), encoding="utf-8")
            temporary.replace(_NOTICE_PATH)
        except OSError:
            # A warning must never replace the original startup failure when
            # the data volume is unavailable or read-only.
            return


def list_startup_notices() -> list[dict]:
    with _LOCK:
        return list(reversed(_read()))
