"""Secret and host-path redaction for exported benchmark records."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{20,})\b"),
    re.compile(r"(?i)C:\\Users\\[^\\\s]+"),
    re.compile(r"/home/[^/\s]+"),
]


def redact(value: Any) -> Any:
    if isinstance(value, str):
        text = value
        for pattern in _PATTERNS:
            text = pattern.sub("[REDACTED]", text)
        return text
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]"
            if any(token in str(key).lower() for token in ("key", "token", "secret", "password"))
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
