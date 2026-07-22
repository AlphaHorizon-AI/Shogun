"""Security routes — policies, assignments, simulation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_security_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.security import (
    PermissionSimulateRequest,
    PermissionSimulateResponse,
    SecurityPolicyCreate,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
    SecurityPostureResponse,
)
from shogun.services.security_service import SecurityService

router = APIRouter(prefix="/security", tags=["Security"])

# ── In-process posture store (persisted via Agent.bushido_settings) ──
_POSTURE_KEY = "security_posture"
_DEFAULT_POSTURE = {
    "active_tier": "tactical",
    "active_campaign_preset": None,
    "filesystem_mode": "scoped",
    "network_mode": "allowlist",
    "shell_enabled": False,
    "skill_auto_install": False,
    "max_active_subagents": 5,
    "kill_switch_enabled": True,
    "kill_switch_active": False,  # True when the kill switch has been triggered
    "comms_read_email": True,
    "comms_send_email": True,
    "comms_read_calendar": True,
    "comms_create_events": True,
    "comms_list_cron": True,
    "comms_manage_cron": True,
    # Mado browser automation
    "mado_enabled": True,
    "mado_headless_only": True,
    "mado_max_sessions": 3,
    "mado_autonomous_browsing": False,
    "mado_downloads_enabled": True,
    "mado_uploads_enabled": True,
    "mado_login_profiles_enabled": False,
    "mado_authenticated_sessions_enabled": False,
    "mado_form_submit_enabled": False,
    "mado_external_urls_enabled": False,
    "mado_capture_screenshots": True,
    "mado_require_verification": True,
    "mado_max_runtime_seconds": 1800,
    "mado_allowed_domains": [],
    # Ronin desktop automation
    "ronin_enabled": False,
    "ronin_posture": "disabled",
    "ronin_max_sessions": 0,
    "ronin_screenshots_enabled": False,
    "ronin_mouse_enabled": False,
    "ronin_keyboard_enabled": False,
    "ronin_native_apps_enabled": False,
    "ronin_window_management_enabled": False,
    "ronin_require_verification": True,
    "ronin_require_high_risk_approval": True,
    "ronin_block_critical_actions": True,
    "ronin_protected_applications": [
        "1Password",
        "Bitwarden",
        "KeePass",
        "Credential Manager",
        "Windows Security",
        "banking",
        "wallet",
    ],
    "ronin_visible_indicator": True,
    "ronin_shell_commands": False,
    "ronin_admin_escalation": False,
    "ronin_credential_entry": "blocked",
    "ronin_file_deletion": "blocked",
    "ronin_external_uploads": "blocked",
    "ronin_install_software": "blocked",
    "ronin_komainu_level": 1,
    "ronin_environment_policy": "any",
    # Office App Mode (Katana)
    "office_enabled": False,
    "office_excel_enabled": True,
    "office_word_enabled": True,
    "office_ppt_enabled": True,
    "office_outlook_enabled": True,
    "office_outlook_mode": "draft_only",
    # Agent Workspace
    "workspace_enabled": True,
    # Shogun IDE Mode is always opt-in and only valid in Campaign/Ronin.
    "ide_enabled": False,
}

# Constraint values that each tier enforces when selected
TIER_CONSTRAINTS: dict[str, dict] = {
    "shrine": {
        "filesystem_mode": "disabled",
        "network_mode": "disabled",
        "shell_enabled": False,
        "skill_auto_install": False,
        "max_active_subagents": 0,
        "comms_read_email": False,
        "comms_send_email": False,
        "comms_read_calendar": False,
        "comms_create_events": False,
        "comms_list_cron": False,
        "comms_manage_cron": False,
        "mado_enabled": False,
        "mado_headless_only": True,
        "mado_max_sessions": 0,
        "mado_autonomous_browsing": False,
        "mado_downloads_enabled": False,
        "mado_uploads_enabled": False,
        "mado_login_profiles_enabled": False,
        "mado_authenticated_sessions_enabled": False,
        "mado_form_submit_enabled": False,
        "mado_external_urls_enabled": False,
        "ronin_enabled": False,
        "ronin_posture": "disabled",
        "ronin_max_sessions": 0,
        "office_enabled": False,
        "workspace_enabled": False,
        "ide_enabled": False,
    },
    "guarded": {
        "filesystem_mode": "allowlist",
        "network_mode": "allowlist",
        "shell_enabled": False,
        "skill_auto_install": False,
        "max_active_subagents": 2,
        "comms_read_email": True,
        "comms_send_email": False,
        "comms_read_calendar": True,
        "comms_create_events": False,
        "comms_list_cron": True,
        "comms_manage_cron": False,
        "mado_enabled": True,
        "mado_headless_only": False,
        "mado_max_sessions": 1,
        "mado_autonomous_browsing": False,
        "mado_downloads_enabled": False,
        "mado_uploads_enabled": False,
        "mado_login_profiles_enabled": False,
        "mado_authenticated_sessions_enabled": False,
        "mado_form_submit_enabled": False,
        "mado_external_urls_enabled": False,
        "ronin_enabled": False,
        "ronin_posture": "disabled",
        "ronin_max_sessions": 0,
        "office_enabled": True,
        "office_outlook_mode": "draft_only",
        "workspace_enabled": True,
        "ide_enabled": False,
    },
    "tactical": {
        "filesystem_mode": "scoped",
        "network_mode": "allowlist",
        "shell_enabled": False,
        "skill_auto_install": False,
        "max_active_subagents": 5,
        "comms_read_email": True,
        "comms_send_email": True,
        "comms_read_calendar": True,
        "comms_create_events": True,
        "comms_list_cron": True,
        "comms_manage_cron": True,
        "mado_enabled": True,
        "mado_headless_only": True,
        "mado_max_sessions": 3,
        "mado_autonomous_browsing": False,
        "mado_downloads_enabled": True,
        "mado_uploads_enabled": True,
        "mado_login_profiles_enabled": False,
        "mado_authenticated_sessions_enabled": False,
        "mado_form_submit_enabled": False,
        "mado_external_urls_enabled": False,
        "ronin_enabled": False,
        "ronin_posture": "disabled",
        "ronin_max_sessions": 0,
        "office_enabled": True,
        "office_outlook_mode": "confirmed_send",
        "workspace_enabled": True,
        "ide_enabled": False,
    },
    "campaign": {
        "filesystem_mode": "full",
        "network_mode": "full",
        "shell_enabled": True,
        "skill_auto_install": True,
        "max_active_subagents": 15,
        "comms_read_email": True,
        "comms_send_email": True,
        "comms_read_calendar": True,
        "comms_create_events": True,
        "comms_list_cron": True,
        "comms_manage_cron": True,
        "mado_enabled": True,
        "mado_headless_only": False,
        "mado_max_sessions": 5,
        "mado_autonomous_browsing": True,
        "mado_downloads_enabled": True,
        "mado_uploads_enabled": True,
        "mado_login_profiles_enabled": True,
        "mado_authenticated_sessions_enabled": True,
        "mado_form_submit_enabled": True,
        "mado_external_urls_enabled": True,
        "ronin_enabled": False,
        "ronin_posture": "disabled",
        "ronin_max_sessions": 0,
        "office_enabled": True,
        "office_outlook_mode": "confirmed_send",
        "workspace_enabled": True,
        "ide_enabled": False,
    },
    "ronin": {
        "filesystem_mode": "full",
        "network_mode": "full",
        "shell_enabled": True,
        "skill_auto_install": True,
        "max_active_subagents": 50,
        "comms_read_email": True,
        "comms_send_email": True,
        "comms_read_calendar": True,
        "comms_create_events": True,
        "comms_list_cron": True,
        "comms_manage_cron": True,
        "mado_enabled": True,
        "mado_headless_only": False,
        "mado_max_sessions": 10,
        "mado_autonomous_browsing": True,
        "mado_downloads_enabled": True,
        "mado_uploads_enabled": True,
        "mado_login_profiles_enabled": True,
        "mado_authenticated_sessions_enabled": True,
        "mado_form_submit_enabled": True,
        "mado_external_urls_enabled": True,
        # Entering Ronin posture makes desktop control available, but does not
        # silently enable it. The operator must confirm enablement separately.
        "ronin_enabled": False,
        "ronin_posture": "disabled",
        "ronin_max_sessions": 0,
        "ronin_screenshots_enabled": False,
        "ronin_mouse_enabled": False,
        "ronin_keyboard_enabled": False,
        "ronin_native_apps_enabled": False,
        "ronin_window_management_enabled": False,
        "ronin_shell_commands": False,
        "ronin_admin_escalation": False,
        "ronin_credential_entry": "blocked",
        "ronin_file_deletion": "approval_required",
        "ronin_external_uploads": "approval_required",
        "ronin_install_software": "approval_required",
        "ronin_require_verification": True,
        "ronin_require_high_risk_approval": True,
        "ronin_block_critical_actions": True,
        "ronin_visible_indicator": True,
        "ronin_komainu_level": 1,
        "ronin_environment_policy": "any",
        "office_enabled": True,
        "office_outlook_mode": "confirmed_send",
        "workspace_enabled": True,
        "ide_enabled": False,
    },
}


async def _get_agent_posture() -> dict:
    """Read security posture from primary Shogun agent's bushido_settings."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent)
            .where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
            .limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return dict(_DEFAULT_POSTURE)
        bushido = agent.bushido_settings or {}
        stored = bushido.get(_POSTURE_KEY, {})
        posture = {**_DEFAULT_POSTURE, **stored}
        if agent.security_policy_id:
            from shogun.db.models.security_policy import SecurityPolicy

            policy = await db.get(SecurityPolicy, agent.security_policy_id)
            if policy:
                posture.update(
                    {
                        "active_policy_id": policy.id,
                        "active_policy_name": policy.name,
                        "active_policy_is_builtin": policy.is_builtin,
                    }
                )
        return posture


async def _save_agent_posture(posture: dict) -> None:
    """Persist security posture into primary Shogun agent's bushido_settings."""

    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent)
            .where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
            .limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return
        bushido = dict(agent.bushido_settings or {})
        bushido[_POSTURE_KEY] = posture
        agent.bushido_settings = bushido
        await db.commit()


# ── Posture endpoints ────────────────────────────────────────────────


@router.get("/posture", response_model=ApiResponse)
async def get_security_posture():
    posture = await _get_agent_posture()
    return ApiResponse(data=SecurityPostureResponse(**posture).model_dump())


@router.patch("/posture", response_model=ApiResponse)
async def update_security_posture(body: dict):
    """Update security posture fields. Persisted across restarts."""
    current = await _get_agent_posture()
    old_tier = current.get("active_tier", "tactical")
    allowed_fields = set(_DEFAULT_POSTURE.keys())
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    current.update(updates)
    # ── Apply tier-specific constraints when active_tier changes ──
    new_tier = current.get("active_tier", "tactical")
    if new_tier != old_tier and new_tier in TIER_CONSTRAINTS:
        current.update(TIER_CONSTRAINTS[new_tier])
    await _save_agent_posture(current)
    # ── EVENT: Auth — Posture Changed ──────────────────
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.posture_changed",
            f"Security posture changed: {old_tier.upper()} → {new_tier.upper()}",
            severity="warn" if new_tier in ("campaign", "ronin") else "info",
            detail={"old_tier": old_tier, "new_tier": new_tier, "updates": updates},
        )
    except Exception:
        pass
    return ApiResponse(data=SecurityPostureResponse(**current).model_dump())


# ── Policy endpoints ─────────────────────────────────────────────────


@router.get("/policies", response_model=ApiResponse)
async def list_policies(svc: SecurityService = Depends(get_security_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[SecurityPolicyResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/policies/{policy_id}", response_model=ApiResponse)
async def get_policy(policy_id: uuid.UUID, svc: SecurityService = Depends(get_security_service)):
    record = await svc.get_by_id(policy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.post("/policies", response_model=ApiResponse, status_code=201)
async def create_policy(
    body: SecurityPolicyCreate,
    svc: SecurityService = Depends(get_security_service),
):
    data = body.model_dump()
    data["permissions"] = (
        data["permissions"] if isinstance(data["permissions"], dict) else data["permissions"].model_dump()
    )
    record = await svc.create(**data)
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.patch("/policies/{policy_id}", response_model=ApiResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: SecurityPolicyUpdate,
    svc: SecurityService = Depends(get_security_service),
):
    update_data = body.model_dump(exclude_unset=True)
    if "permissions" in update_data and update_data["permissions"] is not None:
        update_data["permissions"] = (
            update_data["permissions"].model_dump()
            if hasattr(update_data["permissions"], "model_dump")
            else update_data["permissions"]
        )
    record = await svc.update(policy_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.delete("/policies/{policy_id}", response_model=ApiResponse)
async def delete_policy(
    policy_id: uuid.UUID,
    svc: SecurityService = Depends(get_security_service),
):
    record = await svc.get_by_id(policy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    if record.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in policies")

    # ── Unassign from any agents that reference this policy ──────
    from sqlalchemy import select

    from shogun.db.models.agent import Agent

    result = await svc.session.execute(select(Agent).where(Agent.security_policy_id == str(policy_id)))
    agents = result.scalars().all()
    for agent in agents:
        agent.security_policy_id = None
        # Clear custom_permissions from bushido_settings if present
        if agent.bushido_settings and isinstance(agent.bushido_settings, dict):
            bs = dict(agent.bushido_settings)
            bs.pop("custom_permissions", None)
            agent.bushido_settings = bs

    await svc.delete(policy_id)
    return ApiResponse(data={"deleted": str(policy_id), "unassigned_agents": len(agents)})


@router.post("/simulate", response_model=ApiResponse)
async def simulate_permissions(body: PermissionSimulateRequest):
    return ApiResponse(
        data=PermissionSimulateResponse(
            allowed=True, warnings=["Simulation not yet implemented"], denials=[]
        ).model_dump()
    )


@router.post("/kill-switch", response_model=ApiResponse)
async def activate_kill_switch():
    """Activate the global kill switch and cancel all registered live work."""
    from shogun.services.harakiri_runtime import cancel_active_runtime, engage_harakiri_latch

    # Fail closed before the first database or network await.
    engage_harakiri_latch()
    cancelled = await cancel_active_runtime()
    posture = await _get_agent_posture()
    posture["active_tier"] = "shrine"
    posture.update(TIER_CONSTRAINTS["shrine"])
    posture["kill_switch_active"] = True
    await _save_agent_posture(posture)
    try:
        from shogun.services.mado_hardening import kill_all_mado_sessions

        await kill_all_mado_sessions("Global HARAKIRI kill switch activated")
    except Exception:
        pass
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.kill_switch_activated",
            "HARAKIRI: Kill switch activated — all operations suspended",
            severity="critical",
            detail={"posture": "shrine", "kill_switch_active": True},
        )
        await EventLogger.emit_incident_event(
            "incident.kill_switch",
            "HARAKIRI: Emergency kill switch activated by operator",
            severity="critical",
            risk_score="critical",
            detail={"posture": "shrine", "trigger": "manual"},
        )
        await EventLogger.emit_oversight_event(
            "oversight.emergency_shutdown",
            "Operator initiated emergency shutdown of all AI operations",
            detail={"action": "kill_switch_activated", "new_posture": "shrine"},
        )
    except Exception:
        pass
    return ApiResponse(
        data={
            **posture,
            "cancelled": cancelled,
            "message": "All agent activity suspended. Posture set to SHRINE.",
        }
    )


@router.delete("/kill-switch", response_model=ApiResponse)
async def reset_kill_switch():
    """Deactivate kill switch and restore tactical posture."""
    posture = await _get_agent_posture()
    posture["active_tier"] = "tactical"
    posture.update(TIER_CONSTRAINTS["tactical"])
    posture["kill_switch_active"] = False
    await _save_agent_posture(posture)
    from shogun.services.harakiri_runtime import reset_harakiri_latch

    reset_harakiri_latch()
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.kill_switch_reset",
            "Kill switch deactivated — posture restored to TACTICAL",
            severity="warn",
            detail={"posture": "tactical", "kill_switch_active": False},
        )
    except Exception:
        pass
    return ApiResponse(data={**posture, "message": "Kill switch reset. Posture restored to TACTICAL."})


# ── Campaign Preset endpoints ────────────────────────────────────────


@router.get("/campaign-presets", response_model=ApiResponse)
async def list_campaign_presets():
    """List all available campaign presets (built-in + custom)."""
    from shogun.services.campaign_presets import list_presets

    presets = list_presets()
    return ApiResponse(data=presets)


@router.get("/campaign-presets/{preset_key}", response_model=ApiResponse)
async def get_campaign_preset(preset_key: str):
    """Get a specific campaign preset by key."""
    from shogun.services.campaign_presets import get_preset

    preset = get_preset(preset_key)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"Campaign preset '{preset_key}' not found")
    return ApiResponse(data=preset)


@router.post("/campaign-presets", response_model=ApiResponse, status_code=201)
async def create_campaign_preset(body: dict):
    """Create a new custom campaign preset."""
    from shogun.services.campaign_presets import create_custom_preset

    key = body.get("key", "").strip()
    name = body.get("name", "").strip()
    if not key or not name:
        raise HTTPException(status_code=400, detail="'key' and 'name' are required")
    try:
        preset = create_custom_preset(
            key=key,
            name=name,
            description=body.get("description", ""),
            timeout_minutes=body.get("timeout_minutes", 0),
            tool_overrides=body.get("tool_overrides"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # ── Audit ──
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.campaign_preset_created",
            f"Custom campaign preset created: {name} ({key})",
            policy_ref=key,
            policy_decision="created",
            detail={"preset": preset},
        )
    except Exception:
        pass
    return ApiResponse(data=preset)


@router.delete("/campaign-presets/{preset_key}", response_model=ApiResponse)
async def delete_campaign_preset(preset_key: str):
    """Delete a custom campaign preset."""
    from shogun.services.campaign_presets import delete_custom_preset

    try:
        deleted = delete_custom_preset(preset_key)
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Custom preset '{preset_key}' not found")
    # If this preset was active, clear it from posture
    posture = await _get_agent_posture()
    if posture.get("active_campaign_preset") == preset_key:
        posture["active_campaign_preset"] = None
        await _save_agent_posture(posture)
    # ── Audit ──
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.campaign_preset_deleted",
            f"Custom campaign preset deleted: {preset_key}",
            policy_ref=preset_key,
            policy_decision="deleted",
        )
    except Exception:
        pass
    return ApiResponse(data={"deleted": preset_key})


# ── ToolGate Confirmation ────────────────────────────────────────────

from pydantic import BaseModel


class ToolGateConfirmRequest(BaseModel):
    confirm_id: str
    approved: bool


@router.post("/toolgate/confirm")
async def toolgate_confirm(body: ToolGateConfirmRequest):
    """Resolve a pending ToolGate confirmation from the chat UI.

    The frontend calls this when the operator clicks Approve or Deny
    on a confirmation card in the chat stream.
    """
    from shogun.services.toolgate_confirm import resolve_confirmation

    found = resolve_confirmation(body.confirm_id, body.approved)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Confirmation '{body.confirm_id}' not found (expired or already resolved)",
        )

    # ── Audit ──
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.toolgate_confirmation_resolved",
            f"ToolGate confirmation {body.confirm_id}: {'approved' if body.approved else 'denied'}",
            policy_ref=f"toolgate:{body.confirm_id}",
            policy_decision="approved" if body.approved else "denied",
        )
    except Exception:
        pass

    return ApiResponse(
        data={
            "confirm_id": body.confirm_id,
            "approved": body.approved,
        }
    )
