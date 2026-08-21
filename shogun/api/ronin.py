"""Ronin API Router — FastAPI endpoints for desktop control.

All endpoints under /api/v1/ronin.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from shogun.config import settings
from shogun.schemas.common import ApiResponse
from shogun.schemas.ronin import (
    AppTrustEntryResponse,
    EnvironmentInfoResponse,
    RoninActionRequest,
    RoninActionResult,
    RoninApprovalRequest,
    RoninCapabilityResponse,
    RoninSessionCreate,
    RoninStatusResponse,
)

router = APIRouter(prefix="/ronin", tags=["Ronin"])


# ── Status ───────────────────────────────────────────────────────────


@router.get("/status")
async def get_ronin_status():
    """Get Ronin system status — enabled, posture, environment, Komainu."""
    try:
        from shogun.ronin.core.approval_gate import get_pending
        from shogun.ronin.core.capabilities_registry import list_capabilities
        from shogun.ronin.core.komainu import get_status as get_komainu_status
        from shogun.ronin.core.ronin_controller import get_controller
        from shogun.ronin.desktop.observation_service import get_observer

        controller = get_controller()
        env = controller.get_environment() or await controller.initialize()

        # Get posture
        try:
            from shogun.api.security import _get_agent_posture

            posture = await _get_agent_posture()
        except Exception:
            posture = {}

        # Count active sessions
        from sqlalchemy import func, select

        from shogun.db.engine import async_session_factory
        from shogun.db.models.ronin_session import RoninSession

        async with async_session_factory() as session:
            result = await session.execute(
                select(func.count(RoninSession.id)).where(
                    RoninSession.status.in_(["active", "paused", "idle"]),
                    RoninSession.is_deleted.is_(False),
                )
            )
            active_count = result.scalar() or 0

        return ApiResponse(
            success=True,
            data=RoninStatusResponse(
                ronin_enabled=posture.get("ronin_enabled", False),
                ronin_posture=posture.get("ronin_posture", "disabled"),
                active_sessions=active_count,
                environment=env.model_dump() if env else {},
                komainu=get_komainu_status(),
                pending_approvals=len(get_pending()),
                capabilities_count=len(list_capabilities()),
                active_tier=posture.get("active_tier", "tactical"),
                desktop_available=posture.get("active_tier") == "ronin",
                desktop_active=posture.get("active_tier") == "ronin" and posture.get("ronin_enabled", False),
                visible_indicator=posture.get("ronin_visible_indicator", True),
                runtime=get_observer().get_runtime_state(),
            ).model_dump(),
        )
    except Exception:
        return ApiResponse(
            success=True,
            data={
                "ronin_enabled": False,
                "ronin_posture": "disabled",
                "active_sessions": 0,
                "environment": {},
                "komainu": {"status": "inactive"},
                "pending_approvals": 0,
                "capabilities_count": 0,
            },
        )


# ── Sessions ─────────────────────────────────────────────────────────


@router.post("/sessions")
async def create_session(body: RoninSessionCreate):
    """Create a new Ronin desktop session."""
    from shogun.api.security import _get_agent_posture
    from shogun.db.engine import async_session_factory
    from shogun.db.models.ronin_session import RoninSession
    from shogun.ronin.core.audit_logger import RoninAuditLogger
    from shogun.ronin.core.ronin_controller import get_controller

    posture = await _get_agent_posture()
    if posture.get("active_tier") != "ronin" or not posture.get("ronin_enabled", False):
        raise HTTPException(
            status_code=403, detail="Enable Ronin Desktop Control in Ronin posture before starting a session"
        )

    controller = get_controller()
    env = await controller.initialize()

    new_session = RoninSession(
        name=body.name,
        agent_id=body.agent_id,
        posture=body.posture,
        status="idle",
        environment_type=env.environment_type.value,
        os_type=env.os_type,
        os_version=env.os_version,
        hostname=env.hostname,
        machine_id=env.machine_id,
        is_disposable=env.is_disposable,
        komainu_level=body.komainu_level,
        session_data={},
    )

    async with async_session_factory() as session:
        session.add(new_session)
        await session.commit()
        await session.refresh(new_session)

    await RoninAuditLogger.log_session_start(
        session_id=str(new_session.id),
        agent_id=str(body.agent_id) if body.agent_id else None,
        environment_type=env.environment_type.value,
        posture=body.posture,
    )

    return ApiResponse(success=True, data=_session_to_dict(new_session))


@router.get("/sessions")
async def list_sessions():
    """List all Ronin sessions."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.ronin_session import RoninSession

    async with async_session_factory() as session:
        result = await session.execute(
            select(RoninSession).where(RoninSession.is_deleted.is_(False)).order_by(RoninSession.created_at.desc())
        )
        sessions = result.scalars().all()

    return ApiResponse(
        success=True,
        data=[_session_to_dict(s) for s in sessions],
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: uuid.UUID):
    """Get a specific Ronin session."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.ronin_session import RoninSession

    async with async_session_factory() as session:
        result = await session.execute(select(RoninSession).where(RoninSession.id == session_id))
        ronin_session = result.scalar_one_or_none()

    if not ronin_session:
        raise HTTPException(status_code=404, detail="Ronin session not found")

    return ApiResponse(success=True, data=_session_to_dict(ronin_session))


@router.delete("/sessions/{session_id}")
async def close_session(session_id: uuid.UUID):
    """Close and destroy a Ronin session."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.ronin_session import RoninSession
    from shogun.ronin.core.audit_logger import RoninAuditLogger

    async with async_session_factory() as session:
        result = await session.execute(select(RoninSession).where(RoninSession.id == session_id))
        ronin_session = result.scalar_one_or_none()

        if not ronin_session:
            raise HTTPException(status_code=404, detail="Ronin session not found")

        ronin_session.status = "closed"
        ronin_session.is_deleted = True
        ronin_session.deleted_at = datetime.now(timezone.utc)
        await session.commit()

    await RoninAuditLogger.log_session_close(
        session_id=str(session_id),
        agent_id=str(ronin_session.agent_id) if ronin_session.agent_id else None,
        reason="operator_closed",
    )

    return ApiResponse(success=True, data={"closed": True, "session_id": str(session_id)})


# ── Execute Action ───────────────────────────────────────────────────


@router.post("/execute")
async def execute_action(body: RoninActionRequest):
    """Execute a Ronin action through the full pipeline."""
    from shogun.ronin.core.ronin_controller import execute_action as _execute
    from shogun.ronin.policies.ronin_policy_schema import RoninAction

    action = RoninAction(
        agent_id=str(body.agent_id) if body.agent_id else "api",
        session_id=str(body.session_id) if body.session_id else None,
        action_type=body.action_type,
        target=body.target,
        value=body.value,
        reason=body.reason,
        metadata=body.metadata,
    )

    result = await _execute(action)

    return ApiResponse(
        success=result.status.value == "success",
        data=RoninActionResult(
            status=result.status.value,
            action_type=result.action_type,
            target=result.target,
            result_data=result.result_data,
            screenshot_before=result.screenshot_before,
            screenshot_after=result.screenshot_after,
            confidence=result.confidence,
            verified=result.verified,
            error=result.error,
            duration_ms=result.duration_ms,
            approval_id=result.approval_id,
        ).model_dump(),
    )


# Dedicated Order 11 desktop API -------------------------------------------------


@router.get("/desktop/status")
async def get_desktop_status():
    """Return enablement, permissions, current observation, and action timeline."""
    from shogun.api.security import _get_agent_posture
    from shogun.ronin.desktop.observation_service import get_observer

    posture = await _get_agent_posture()
    keys = (
        "active_tier",
        "ronin_enabled",
        "ronin_posture",
        "ronin_screenshots_enabled",
        "ronin_mouse_enabled",
        "ronin_keyboard_enabled",
        "ronin_window_management_enabled",
        "ronin_native_apps_enabled",
        "ronin_require_verification",
        "ronin_require_high_risk_approval",
        "ronin_block_critical_actions",
        "ronin_protected_applications",
        "ronin_visible_indicator",
        "kill_switch_active",
    )
    return ApiResponse(
        success=True,
        data={
            **{key: posture.get(key) for key in keys},
            "available": posture.get("active_tier") == "ronin",
            "active": posture.get("active_tier") == "ronin" and posture.get("ronin_enabled", False),
            "runtime": get_observer().get_runtime_state(),
        },
    )


@router.post("/desktop/enable")
async def enable_desktop_control(body: dict[str, Any]):
    """Explicitly enable full desktop control after a warning confirmation."""
    if settings.deployment_mode == "server":
        raise HTTPException(
            status_code=409,
            detail="Ronin host desktop control is unavailable in Shogun Server mode.",
        )

    from shogun.api.security import _get_agent_posture, _save_agent_posture
    from shogun.ronin.core.audit_logger import RoninAuditLogger
    from shogun.ronin.core.komainu import start_komainu
    from shogun.ronin.desktop.observation_service import get_observer

    posture = await _get_agent_posture()
    if posture.get("active_tier") != "ronin":
        raise HTTPException(status_code=403, detail="Ronin Desktop Control is only available in Ronin posture")
    if posture.get("kill_switch_active", False):
        raise HTTPException(
            status_code=409,
            detail="The global kill switch is active. Reset it through the dedicated recovery control first.",
        )
    if body.get("confirmation") != "ENABLE RONIN DESKTOP CONTROL":
        raise HTTPException(status_code=400, detail="Explicit warning confirmation is required")

    configurable_bool_fields = (
        "ronin_screenshots_enabled",
        "ronin_mouse_enabled",
        "ronin_keyboard_enabled",
        "ronin_window_management_enabled",
        "ronin_native_apps_enabled",
    )
    for field in configurable_bool_fields:
        if field in body and type(body[field]) is not bool:
            raise HTTPException(status_code=422, detail=f"'{field}' must be a boolean")
    non_negotiable_true = (
        "ronin_require_verification",
        "ronin_require_high_risk_approval",
        "ronin_block_critical_actions",
        "ronin_visible_indicator",
    )
    for field in non_negotiable_true:
        if field in body and body[field] is not True:
            raise HTTPException(status_code=422, detail=f"'{field}' cannot be weakened in Ronin posture")
    if "ronin_max_sessions" in body and type(body["ronin_max_sessions"]) is not int:
        raise HTTPException(status_code=422, detail="'ronin_max_sessions' must be an integer")
    protected = body.get("ronin_protected_applications")
    if protected is not None and (
        not isinstance(protected, list) or not all(isinstance(item, str) for item in protected)
    ):
        raise HTTPException(status_code=422, detail="'ronin_protected_applications' must be a list of strings")
    posture.update(
        {
            "ronin_enabled": True,
            "ronin_posture": "desktop_full",
            "ronin_max_sessions": max(1, min(body.get("ronin_max_sessions", 3), 10)),
            "ronin_require_verification": True,
            "ronin_require_high_risk_approval": True,
            "ronin_block_critical_actions": True,
            "ronin_visible_indicator": True,
            "ronin_admin_escalation": False,
            "ronin_credential_entry": "blocked",
            "ronin_file_deletion": "approval_required",
            "ronin_external_uploads": "approval_required",
            "ronin_install_software": "approval_required",
        }
    )
    defaults = {
        "ronin_screenshots_enabled": True,
        "ronin_mouse_enabled": True,
        "ronin_keyboard_enabled": True,
        "ronin_window_management_enabled": True,
        "ronin_native_apps_enabled": True,
    }
    for field in configurable_bool_fields:
        posture[field] = body.get(field, defaults[field])
    if protected is not None:
        posture["ronin_protected_applications"] = list(
            dict.fromkeys([*posture.get("ronin_protected_applications", []), *protected])
        )
    await _save_agent_posture(posture)
    try:
        from shogun.api.setup import _read_setup, _write_setup

        setup = _read_setup()
        config = dict(setup.get("ronin_desktop_control", {}))
        config.update(
            {
                "enabled": True,
                "minimum_posture": "ronin",
                "allow_mouse": posture["ronin_mouse_enabled"],
                "allow_keyboard": posture["ronin_keyboard_enabled"],
                "allow_window_management": posture["ronin_window_management_enabled"],
                "allow_application_launch": posture["ronin_native_apps_enabled"],
                "verification_required": posture["ronin_require_verification"],
                "high_risk_requires_approval": posture["ronin_require_high_risk_approval"],
                "critical_actions_blocked": posture["ronin_block_critical_actions"],
            }
        )
        setup["ronin_desktop_control"] = config
        _write_setup(setup)
    except Exception:
        pass
    started = start_komainu(level=int(posture.get("ronin_komainu_level", 1)))
    get_observer().resume()
    get_observer().record("ronin.desktop.enabled", "Ronin Desktop Control enabled by operator")
    await RoninAuditLogger.log_action(
        event_type="ronin.desktop.enabled",
        action="Ronin Desktop Control explicitly enabled",
        result="enabled",
        severity="warn",
        risk_level="high",
        detail={"guardian_started": started},
    )
    return await get_desktop_status()


@router.post("/desktop/disable")
async def disable_desktop_control():
    from shogun.api.security import _get_agent_posture, _save_agent_posture
    from shogun.ronin.core.audit_logger import RoninAuditLogger
    from shogun.ronin.core.komainu import stop_komainu
    from shogun.ronin.desktop.observation_service import get_observer

    posture = await _get_agent_posture()
    posture.update(
        {
            "ronin_enabled": False,
            "ronin_posture": "disabled",
            "ronin_max_sessions": 0,
            "ronin_screenshots_enabled": False,
            "ronin_mouse_enabled": False,
            "ronin_keyboard_enabled": False,
            "ronin_window_management_enabled": False,
            "ronin_native_apps_enabled": False,
        }
    )
    await _save_agent_posture(posture)
    try:
        from shogun.api.setup import _read_setup, _write_setup

        setup = _read_setup()
        config = dict(setup.get("ronin_desktop_control", {}))
        config["enabled"] = False
        setup["ronin_desktop_control"] = config
        _write_setup(setup)
    except Exception:
        pass
    stop_komainu()
    get_observer().pause("Desktop control disabled by operator")
    await RoninAuditLogger.log_action(
        event_type="ronin.desktop.disabled",
        action="Ronin Desktop Control disabled",
        result="disabled",
        severity="warn",
        risk_level="high",
    )
    return await get_desktop_status()


async def _run_desktop(action_type: str, body: dict[str, Any] | None = None):
    body = body or {}
    request = RoninActionRequest(
        action_type=action_type,
        target=body.get("target"),
        value=body.get("value"),
        reason=body.get("reason", "Desktop API action"),
        session_id=body.get("session_id"),
        agent_id=body.get("agent_id"),
        metadata=body.get("metadata", {}),
    )
    return await execute_action(request)


@router.post("/desktop/screenshot")
async def desktop_screenshot(body: dict[str, Any] | None = None):
    return await _run_desktop("desktop.screenshot", body)


@router.get("/desktop/state")
async def desktop_state():
    return await _run_desktop("desktop.state")


@router.get("/desktop/windows")
async def desktop_windows():
    return await _run_desktop("os.list_windows")


@router.post("/desktop/click")
async def desktop_click(body: dict[str, Any]):
    return await _run_desktop(
        "desktop.click",
        {
            **body,
            "target": body.get("target") or f"{body.get('x')},{body.get('y')}",
            "metadata": {**body.get("metadata", {}), "x": body.get("x"), "y": body.get("y")},
        },
    )


@router.post("/desktop/type")
async def desktop_type(body: dict[str, Any]):
    return await _run_desktop("desktop.type", {**body, "value": body.get("text") or body.get("value")})


@router.post("/desktop/hotkey")
async def desktop_hotkey(body: dict[str, Any]):
    return await _run_desktop("desktop.hotkey", {**body, "value": body.get("keys") or body.get("value")})


@router.post("/desktop/scroll")
async def desktop_scroll(body: dict[str, Any]):
    return await _run_desktop(
        "desktop.scroll", {**body, "metadata": {**body.get("metadata", {}), "clicks": body.get("clicks", 3)}}
    )


@router.post("/desktop/drag")
async def desktop_drag(body: dict[str, Any]):
    return await _run_desktop(
        "desktop.drag",
        {
            **body,
            "metadata": {
                **body.get("metadata", {}),
                "start_x": body.get("start_x"),
                "start_y": body.get("start_y"),
                "x": body.get("x"),
                "y": body.get("y"),
            },
        },
    )


@router.post("/desktop/focus-window")
async def desktop_focus_window(body: dict[str, Any]):
    return await _run_desktop("os.focus_window", {**body, "target": body.get("title") or body.get("target")})


@router.post("/desktop/open-application")
async def desktop_open_application(body: dict[str, Any]):
    metadata = {
        **body.get("metadata", {}),
        "arguments": body.get("arguments", []),
        "expected_window": body.get("expected_window"),
    }
    return await _run_desktop(
        "os.app_launch", {**body, "target": body.get("application") or body.get("target"), "metadata": metadata}
    )


@router.post("/desktop/verify")
async def desktop_verify(body: dict[str, Any]):
    from shogun.ronin.desktop.observation_service import get_observer
    from shogun.ronin.desktop.verification_service import get_verifier

    state = await get_observer().capture_state(screenshot=False)
    verification = await get_verifier().verify("desktop.verify", {}, state, state, body)
    get_observer().set_verification(verification.model_dump())
    return ApiResponse(success=verification.passed, data=verification.model_dump())


@router.post("/desktop/wait-for-window")
async def desktop_wait_for_window(body: dict[str, Any]):
    from shogun.api.setup import _read_setup

    default_timeout = _read_setup().get("ronin_desktop_control", {}).get("default_action_timeout_seconds", 20)
    return await _run_desktop(
        "os.wait_for_window",
        {
            **body,
            "target": body.get("title") or body.get("target"),
            "metadata": {**body.get("metadata", {}), "timeout": body.get("timeout", default_timeout)},
        },
    )


@router.post("/desktop/wait-for-file")
async def desktop_wait_for_file(body: dict[str, Any]):
    from shogun.api.setup import _read_setup

    default_timeout = _read_setup().get("ronin_desktop_control", {}).get("default_action_timeout_seconds", 20)
    return await _run_desktop(
        "os.wait_for_file",
        {
            **body,
            "target": body.get("path") or body.get("target"),
            "metadata": {**body.get("metadata", {}), "timeout": body.get("timeout", default_timeout)},
        },
    )


@router.post("/desktop/kill-switch")
async def desktop_kill_switch():
    from shogun.api.security import _get_agent_posture, _save_agent_posture
    from shogun.ronin.core.audit_logger import RoninAuditLogger
    from shogun.ronin.desktop.observation_service import get_observer

    posture = await _get_agent_posture()
    posture["kill_switch_active"] = True
    posture["ronin_enabled"] = False
    posture["ronin_posture"] = "disabled"
    await _save_agent_posture(posture)
    try:
        from shogun.api.setup import _read_setup, _write_setup

        setup = _read_setup()
        config = dict(setup.get("ronin_desktop_control", {}))
        config["enabled"] = False
        setup["ronin_desktop_control"] = config
        _write_setup(setup)
    except Exception:
        pass
    # Keep Komainu running: the guardian remains an additional safety layer
    # while the persisted kill switch blocks new governed actions.
    get_observer().pause("Ronin Desktop kill switch activated")
    await RoninAuditLogger.log_action(
        event_type="ronin.desktop.kill_switch_triggered",
        action="Ronin Desktop kill switch activated",
        result="stopped",
        severity="critical",
        risk_level="critical",
    )
    return ApiResponse(success=True, data={"stopped": True, "kill_switch_active": True})


@router.post("/desktop/demo/word-hello-world")
async def desktop_word_hello_world(body: dict[str, Any] | None = None):
    """Run the canonical, fully governed Word acceptance demo."""
    from shogun.ronin.desktop.demo_service import run_word_hello_world

    body = body or {}
    result = await run_word_hello_world(
        output_path=body.get("output_path"), agent_id=str(body.get("agent_id", "operator"))
    )
    return ApiResponse(success=bool(result.get("success")), data=result)


# ── Approvals ────────────────────────────────────────────────────────


@router.get("/approvals")
async def list_approvals():
    """List pending approval requests."""
    from shogun.ronin.core.approval_gate import get_pending

    return ApiResponse(success=True, data=get_pending())


@router.post("/approvals/{approval_id}")
async def respond_approval(approval_id: str, body: RoninApprovalRequest):
    """Approve or deny a pending action."""
    from shogun.ronin.core.approval_gate import get_approval_status, respond_to_approval
    from shogun.ronin.core.audit_logger import RoninAuditLogger

    # The caller cannot choose its audit identity. This route is an operator
    # control-plane action; infrastructure authentication is enforced upstream.
    success = respond_to_approval(approval_id, body.decision, "operator")
    if not success:
        if get_approval_status(approval_id) is not None:
            raise HTTPException(status_code=409, detail=f"Approval request '{approval_id}' was already decided")
        raise HTTPException(status_code=404, detail=f"Approval request '{approval_id}' not found")

    await RoninAuditLogger.log_approval_response(
        approval_id=approval_id,
        decision=body.decision,
    )

    return ApiResponse(success=True, data={"approval_id": approval_id, "decision": body.decision})


# ── Harakiri ─────────────────────────────────────────────────────────


@router.post("/harakiri")
async def ronin_harakiri():
    """Persist the Ronin kill switch, then cancel supported active work."""
    from shogun.ronin.core.approval_gate import cancel_all
    from shogun.ronin.core.audit_logger import RoninAuditLogger

    # Persist the fail-closed gate before attempting best-effort cancellation.
    # If persistence fails, this endpoint fails instead of claiming safety.
    await desktop_kill_switch()

    # Cancel all pending approvals
    cancel_all("harakiri")

    # Close all active sessions
    from sqlalchemy import update

    from shogun.db.engine import async_session_factory
    from shogun.db.models.ronin_session import RoninSession

    async with async_session_factory() as session:
        await session.execute(
            update(RoninSession).where(RoninSession.status.in_(["active", "paused", "idle"])).values(status="closed")
        )
        await session.commit()

    await RoninAuditLogger.log_harakiri("api_triggered")

    return ApiResponse(
        success=True,
        data={
            "harakiri": True,
            "kill_switch_active": True,
            "message": (
                "New governed Ronin actions are blocked; pending approvals were cancelled "
                "and supported Ronin sessions were marked closed."
            ),
        },
    )


# ── Audit Trail ──────────────────────────────────────────────────────


@router.get("/audit")
async def get_audit_trail(limit: int = 50):
    """Get Ronin audit trail from execution events."""
    try:
        from sqlalchemy import text

        from shogun.db.engine import async_session_factory

        async with async_session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, event_type, action, result, severity, risk_score,
                           agent_id, created_at, detail
                    FROM execution_events
                    WHERE event_category = 'ronin'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            rows = result.fetchall()

        events = [
            {
                "id": str(row[0]),
                "event_type": row[1],
                "action": row[2],
                "result": row[3],
                "severity": row[4],
                "risk_score": row[5],
                "agent_id": str(row[6]) if row[6] else None,
                "created_at": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]
        return ApiResponse(success=True, data=events)
    except Exception:
        return ApiResponse(success=True, data=[])


# ── Screenshots ──────────────────────────────────────────────────────


@router.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """Serve a Ronin screenshot file."""
    from fastapi.responses import FileResponse

    from shogun.ronin.telemetry.screenshot_store import get_screenshots_dir

    screenshots_dir = get_screenshots_dir().resolve()
    filepath = (screenshots_dir / filename).resolve()
    if (
        Path(filename).name != filename
        or filepath.parent != screenshots_dir
        or filepath.suffix.casefold() != ".png"
        or not filepath.is_file()
    ):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(str(filepath), media_type="image/png")


# ── Capabilities ─────────────────────────────────────────────────────


@router.get("/capabilities")
async def list_capabilities(category: str | None = None):
    """List registered Ronin capabilities with risk levels."""
    from shogun.ronin.core.capabilities_registry import list_capabilities as _list

    caps = _list(category=category)
    return ApiResponse(
        success=True,
        data=[
            RoninCapabilityResponse(
                name=c.name,
                category=c.category,
                risk_level=c.risk_level.value,
                requires_approval=c.requires_approval,
                description=c.description,
                posture_minimum=c.posture_minimum.value,
                app_trust_minimum=c.app_trust_minimum.value,
                enabled=c.enabled,
            ).model_dump()
            for c in caps
        ],
    )


# ── App Trust ────────────────────────────────────────────────────────


@router.get("/trust")
async def get_trust_registry():
    """Get the current app trust registry."""
    from shogun.ronin.core.app_trust_registry import get_all_entries

    entries = get_all_entries()
    return ApiResponse(
        success=True,
        data=[
            AppTrustEntryResponse(
                process=e.process,
                process_pattern=e.process_pattern,
                name=e.name,
                trust_level=e.trust_level.value,
                platform=e.platform,
            ).model_dump()
            for e in entries
        ],
    )


@router.patch("/trust")
async def update_trust_entry(body: dict[str, Any]):
    """Update an app trust entry."""
    from shogun.ronin.core.app_trust_registry import update_trust_level
    from shogun.ronin.policies.ronin_policy_schema import AppTrustLevel

    process = body.get("process")
    level = body.get("trust_level")

    if not process or not level:
        raise HTTPException(status_code=400, detail="Both 'process' and 'trust_level' required")

    try:
        trust_level = AppTrustLevel(level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid trust level: {level}")

    updated = update_trust_level(process, trust_level)
    if not updated:
        # Add as new entry
        from shogun.ronin.core.app_trust_registry import add_entry
        from shogun.ronin.policies.ronin_policy_schema import AppTrustEntry

        add_entry(
            AppTrustEntry(
                process=process,
                name=body.get("name", process),
                trust_level=trust_level,
            )
        )

    return ApiResponse(success=True, data={"process": process, "trust_level": level})


# ── Environment ──────────────────────────────────────────────────────


@router.get("/environment")
async def get_environment():
    """Get detected execution environment info."""
    from shogun.ronin.core.ronin_controller import get_controller

    controller = get_controller()
    env = await controller.initialize()

    return ApiResponse(
        success=True,
        data=EnvironmentInfoResponse(
            environment_type=env.environment_type.value,
            os_type=env.os_type,
            os_version=env.os_version,
            hostname=env.hostname,
            machine_id=env.machine_id,
            is_disposable=env.is_disposable,
            hypervisor=env.hypervisor,
            details=env.details,
        ).model_dump(),
    )


# ── Helpers ──────────────────────────────────────────────────────────


def _session_to_dict(s) -> dict[str, Any]:
    """Convert a RoninSession ORM object to a response dict."""
    return {
        "id": str(s.id),
        "name": s.name,
        "agent_id": str(s.agent_id) if s.agent_id else None,
        "posture": s.posture,
        "status": s.status,
        "environment_type": s.environment_type,
        "os_type": s.os_type,
        "os_version": s.os_version,
        "hostname": s.hostname,
        "machine_id": s.machine_id,
        "is_disposable": s.is_disposable,
        "last_screenshot_path": s.last_screenshot_path,
        "last_action": s.last_action,
        "last_action_at": s.last_action_at.isoformat() if s.last_action_at else None,
        "current_app": s.current_app,
        "current_app_trust": s.current_app_trust,
        "action_count": s.action_count,
        "komainu_level": s.komainu_level,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
