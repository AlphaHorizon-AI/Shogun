"""Approval Gate — WebSocket-based real-time approval for high-risk Ronin actions.

When a Ronin action requires operator approval (based on posture, risk, or
app trust), the Approval Gate:
1. Creates an approval request with full context
2. Pushes it to the Tenshu UI via activity stream / WebSocket
3. Blocks the action until approved, denied, or timed out
4. Falls back to a queue if no WebSocket listener is connected
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from shogun.ronin.policies.ronin_policy_schema import RoninAction, RoninPermissionGate

log = logging.getLogger("shogun.ronin.approval_gate")

ApprovalDecision = Literal["approved", "denied"]

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(password|passcode|secret|token|api[_ -]?key|private[_ -]?key)\s*[:=]\s*\S+"
)
_SECRET_FLAG = re.compile(
    r"(?i)(--?(?:password|passcode|secret|token|api[_-]?key|private[_-]?key))\s+\S+"
)
_BEARER_TOKEN = re.compile(r"(?i)(bearer\s+)\S+")
_URL_USERINFO = re.compile(r"(://)[^/@\s]+@")


def action_digest(action: RoninAction) -> str:
    """Return a canonical digest binding approval to immutable action details."""
    payload = action.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _safe_preview_text(value: Any, *, limit: int = 240) -> str:
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", str(value))
    text = _SECRET_FLAG.sub(lambda match: f"{match.group(1)} [REDACTED]", text)
    text = _BEARER_TOKEN.sub(r"\1[REDACTED]", text)
    text = _URL_USERINFO.sub(r"\1[REDACTED]@", text)
    return text if len(text) <= limit else f"{text[:limit]}..."


def action_preview(
    action: RoninAction,
    permission_gates: tuple[RoninPermissionGate, ...],
) -> dict[str, Any]:
    """Build a bounded, secret-aware preview for the operator approval UI."""
    preview: dict[str, Any] = {
        "action_type": action.action_type,
        "target": action_target_preview(action, permission_gates),
        "permission_gates": [gate.value for gate in permission_gates],
    }
    if action.value is not None:
        if action.action_type in {"desktop.type", "browser.type"}:
            preview["value"] = f"[REDACTED TEXT INPUT: {len(action.value)} characters]"
        else:
            preview["value"] = _safe_preview_text(action.value)

    material_metadata: dict[str, Any] = {}
    for key in (
        "arguments",
        "button",
        "clicks",
        "elevated",
        "expected_window",
        "operation",
        "interval",
        "max_retries",
        "require_admin",
        "region",
        "run_as_admin",
        "semantic_intent",
        "start_x",
        "start_y",
        "verb",
        "x",
        "y",
    ):
        if key in action.metadata:
            material_metadata[key] = _safe_preview_text(action.metadata[key])
    if material_metadata:
        preview["metadata"] = material_metadata
    if set(action.metadata) - set(material_metadata):
        preview["other_metadata_present"] = True
    return preview


def action_target_preview(
    action: RoninAction,
    permission_gates: tuple[RoninPermissionGate, ...],
) -> str | None:
    """Return a bounded target safe for UI, runtime status, and audit events."""
    if action.target is None:
        return None
    if RoninPermissionGate.CREDENTIAL_ENTRY in permission_gates:
        return "[CREDENTIAL-ENTRY TARGET REDACTED]"
    return _safe_preview_text(action.target)


@dataclass
class ApprovalRequest:
    """A pending approval request for a high-risk Ronin action."""

    id: str = field(default_factory=lambda: f"apr_{uuid.uuid4().hex[:12]}")
    agent_id: str | None = None
    session_id: str | None = None
    action_type: str = ""
    target: str | None = None
    reason: str = ""
    risk_level: str = "high"
    app_name: str | None = None
    app_trust: str | None = None
    screenshot_path: str | None = None
    action_digest: str | None = None
    action_preview: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = "pending"  # pending | approved | denied | timeout
    decision_by: str | None = None  # operator, gensui, timeout
    decision_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "action_type": self.action_type,
            "target": self.target,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "app_name": self.app_name,
            "app_trust": self.app_trust,
            "screenshot_path": self.screenshot_path,
            "action_digest": self.action_digest,
            "action_preview": self.action_preview,
            "created_at": self.created_at,
            "status": self.status,
            "decision_by": self.decision_by,
            "decision_at": self.decision_at,
        }


# ── In-memory state ──────────────────────────────────────────────────

_pending: dict[str, ApprovalRequest] = {}
_waiters: dict[str, asyncio.Event] = {}
_history: list[ApprovalRequest] = []  # Last 100 decisions
_MAX_HISTORY = 100
_DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes


async def request_approval(
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    action_type: str,
    target: str | None = None,
    reason: str = "",
    risk_level: str = "high",
    app_name: str | None = None,
    app_trust: str | None = None,
    screenshot_path: str | None = None,
    action_digest: str | None = None,
    action_preview: dict[str, Any] | None = None,
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS,
) -> ApprovalRequest:
    """Create an approval request and wait for operator response.

    Blocks until approved, denied, or timeout. The operator responds
    via the API (POST /ronin/approvals/{id}).

    Returns the completed ApprovalRequest with status set.
    """
    req = ApprovalRequest(
        agent_id=agent_id,
        session_id=session_id,
        action_type=action_type,
        target=_safe_preview_text(target) if target else None,
        reason=reason,
        risk_level=risk_level,
        app_name=app_name,
        app_trust=app_trust,
        screenshot_path=screenshot_path,
        action_digest=action_digest,
        action_preview=action_preview or {},
    )

    event = asyncio.Event()
    _pending[req.id] = req
    _waiters[req.id] = event

    log.info(
        "Ronin: approval requested — id=%s action=%s risk=%s app=%s",
        req.id, action_type, risk_level, app_name,
    )

    # Emit audit event
    try:
        from shogun.ronin.core.audit_logger import RoninAuditLogger
        await RoninAuditLogger.log_approval_requested(
            action_type=action_type,
            reason=reason,
            approval_id=req.id,
            agent_id=agent_id,
            session_id=session_id,
            risk_level=risk_level,
        )
    except Exception:
        pass

    # Wait for operator response or timeout
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        req.status = "timeout"
        req.decision_by = "timeout"
        req.decision_at = datetime.now(timezone.utc).isoformat()
        log.warning("Ronin: approval timed out — id=%s action=%s", req.id, action_type)

    # Cleanup and archive
    _pending.pop(req.id, None)
    _waiters.pop(req.id, None)
    _history.append(req)
    if len(_history) > _MAX_HISTORY:
        _history.pop(0)

    return req


def respond_to_approval(
    approval_id: str,
    decision: ApprovalDecision,
    decided_by: str = "operator",
) -> bool:
    """Approve or deny a pending request. Called from the API.

    Args:
        approval_id: The approval request ID.
        decision: "approved" or "denied".
        decided_by: Who made the decision ("operator", "gensui").

    Returns True if the request was found and responded to.
    """
    if decision not in ("approved", "denied"):
        log.warning("Ronin: rejected invalid approval decision for id=%s", approval_id)
        return False
    req = _pending.get(approval_id)
    if not req:
        log.warning("Ronin: approval response for unknown id=%s", approval_id)
        return False
    if req.status != "pending":
        log.warning(
            "Ronin: replayed approval response rejected — id=%s existing=%s",
            approval_id,
            req.status,
        )
        return False

    req.status = decision
    req.decision_by = decided_by
    req.decision_at = datetime.now(timezone.utc).isoformat()

    event = _waiters.get(approval_id)
    if event:
        event.set()

    log.info(
        "Ronin: approval %s — id=%s by=%s action=%s",
        decision, approval_id, decided_by, req.action_type,
    )
    return True


def get_approval_status(approval_id: str) -> str | None:
    """Return current/recent status so the API can distinguish replay from 404."""
    pending = _pending.get(approval_id)
    if pending:
        return pending.status
    for request in reversed(_history):
        if request.id == approval_id:
            return request.status
    return None


def get_pending() -> list[dict[str, Any]]:
    """Return all pending approval requests as dicts."""
    return [req.to_dict() for req in _pending.values()]


def get_history(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent approval history."""
    return [req.to_dict() for req in _history[-limit:]]


def cancel_all(reason: str = "session_closed") -> int:
    """Cancel all pending approvals. Returns count cancelled."""
    count = 0
    for req_id in list(_pending.keys()):
        req = _pending[req_id]
        req.status = "denied"
        req.decision_by = reason
        req.decision_at = datetime.now(timezone.utc).isoformat()
        event = _waiters.get(req_id)
        if event:
            event.set()
        count += 1
    log.info("Ronin: cancelled %d pending approvals (%s)", count, reason)
    return count
