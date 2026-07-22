"""Shared parsing, risk classification, and authorization for command channels."""

from __future__ import annotations

import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

ROLE_LEVEL = {
    "viewer": 0,
    "operator": 1,
    "senior_operator": 2,
    "admin": 3,
    "security_admin": 4,
}

COMMAND_POLICY = {
    "help": ("L0", "viewer"),
    "status": ("L0", "viewer"),
    "agents": ("L0", "viewer"),
    "workflows": ("L0", "viewer"),
    "logs": ("L0", "viewer"),
    "summarize": ("L0", "viewer"),
    "approvals": ("L0", "viewer"),
    # Team members may converse through the no-tools Governed Chat lane.
    "ask": ("L1", "viewer"),
    "run": ("L2", "operator"),
    "pause": ("L4", "operator"),
    "resume": ("L4", "operator"),
    "approve": ("L3", "senior_operator"),
    "reject": ("L3", "senior_operator"),
    "harakiri": ("L4", "admin"),
    "harakiri_control": ("L4", "admin"),
    "unknown": ("L0", "viewer"),
}


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    arguments: dict[str, Any]
    normalized_text: str
    risk_level: str
    requires_approval: bool


class SlidingWindowRateLimiter:
    """Small process-local limiter; production bridges should add a shared edge limiter."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.monotonic()
        events = self._events[key]
        while events and events[0] <= now - window_seconds:
            events.popleft()
        if len(events) >= limit:
            return False
        events.append(now)
        return True


teams_rate_limiter = SlidingWindowRateLimiter()


def strip_teams_mention(text: str) -> str:
    """Remove Teams HTML/plain-text bot mentions without touching other content."""
    clean = re.sub(r"<at\b[^>]*>.*?</at>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    clean = re.sub(r"^\s*@(?:Shogun(?:\s+AFM)?)\b[:,]?\s*", "", clean, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", clean).strip()


def parse_command(text: str) -> ParsedCommand:
    normalized = strip_teams_mention(text)
    lower = normalized.lower()
    name = "unknown"
    args: dict[str, Any] = {}

    if lower in {"++harakiri", "--harakiri"}:
        name, args = "harakiri_control", {
            "action": "activate" if lower == "++harakiri" else "reset",
        }
    elif lower == "help" or lower.startswith("help "):
        name, args = "help", {"topic": normalized[5:].strip() or None}
    elif lower in {"status", "fleet status"}:
        name = "status"
    elif lower in {"agents", "show agents", "show active agents"}:
        name, args = "agents", {"active_only": "active" in lower}
    elif lower.startswith("show agent "):
        name, args = "agents", {"agent": normalized[11:].strip()}
    elif lower in {"show workflows", "show active workflows"}:
        name, args = "workflows", {"active_only": "active" in lower}
    elif lower in {"show pending approvals", "approvals"}:
        name, args = "approvals", {"status": "pending"}
    elif lower.startswith("ask "):
        match = re.match(r"ask\s+(\S+)\s+(.+)", normalized, flags=re.IGNORECASE)
        if match:
            name, args = "ask", {"target": match.group(1), "message": match.group(2)}
    elif lower.startswith("route to "):
        match = re.match(r"route\s+to\s+(\S+)\s+(.+)", normalized, flags=re.IGNORECASE)
        if match:
            name, args = "ask", {"target": match.group(1), "message": match.group(2)}
    elif lower.startswith(("run ", "start ")):
        body = re.sub(r"^(run|start)\s+(workflow\s+)?", "", normalized, flags=re.IGNORECASE)
        parts = body.split()
        if parts:
            parameters = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            name, args = "run", {"workflow": parts[0], "parameters": parameters}
    elif lower.startswith(("pause ", "resume ")):
        match = re.match(r"(pause|resume)\s+(agent|group)\s+(\S+)", normalized, flags=re.IGNORECASE)
        if match:
            name = match.group(1).lower()
            args = {"scope": match.group(2).lower(), "target": match.group(3)}
    elif lower.startswith("harakiri "):
        match = re.match(r"harakiri\s+(agent|group|fleet)(?:\s+(\S+))?", normalized, flags=re.IGNORECASE)
        if match:
            name, args = "harakiri", {"scope": match.group(1).lower(), "target": match.group(2)}
    elif lower.startswith(("approve ", "reject ")):
        match = re.match(r"(approve|reject)\s+([A-Za-z0-9_-]+)", normalized, flags=re.IGNORECASE)
        if match:
            name, args = match.group(1).lower(), {"request_id": match.group(2)}
    elif lower.startswith("summarize "):
        name, args = "summarize", {"subject": normalized[10:].strip()}
    elif lower.startswith("show last ") or lower == "show errors":
        name, args = "logs", {"query": normalized}

    risk, _ = COMMAND_POLICY[name]
    return ParsedCommand(name, args, normalized, risk, risk in {"L3", "L4"})


def authorize(command: str, role: str, destructive_commands_enabled: bool = False) -> tuple[bool, str]:
    """Return an authorization decision; destructive execution remains Gensui-controlled."""
    _, required_role = COMMAND_POLICY.get(command, COMMAND_POLICY["unknown"])
    if ROLE_LEVEL.get(role, -1) < ROLE_LEVEL[required_role]:
        return False, f"requires_{required_role}"
    if command == "harakiri" and not destructive_commands_enabled:
        return False, "destructive_commands_disabled"
    return True, "allowed"
