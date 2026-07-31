"""Security routes — policies, assignments, simulation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from shogun.api.deps import get_security_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.security import (
    PermissionSimulateRequest,
    PermissionSimulateResponse,
    SecurityPolicyCreate,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
    SecurityPostureResponse,
    SecurityPostureSelectRequest,
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
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
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
                permissions = getattr(policy, "permissions", None) or {}
                posture["active_tier"] = policy.tier
                posture.update(TIER_CONSTRAINTS.get(policy.tier, {}))
                filesystem = permissions.get("filesystem", {})
                network = permissions.get("network", {})
                shell = permissions.get("shell", {})
                skills = permissions.get("skills", {})
                subagents = permissions.get("subagents", {})
                comms = permissions.get("comms", {})
                if "mode" in filesystem:
                    posture["filesystem_mode"] = filesystem["mode"]
                if "mode" in network:
                    posture["network_mode"] = network["mode"]
                if "enabled" in shell:
                    posture["shell_enabled"] = shell["enabled"]
                if "allow_auto_install" in skills:
                    posture["skill_auto_install"] = skills["allow_auto_install"]
                if "max_active" in subagents:
                    posture["max_active_subagents"] = subagents["max_active"]
                for permission_key, posture_key in (
                    ("allow_read_email", "comms_read_email"),
                    ("allow_send_email", "comms_send_email"),
                    ("allow_read_calendar", "comms_read_calendar"),
                    ("allow_create_events", "comms_create_events"),
                    ("allow_list_cron", "comms_list_cron"),
                    ("allow_manage_cron", "comms_manage_cron"),
                ):
                    if permission_key in comms:
                        posture[posture_key] = comms[permission_key]
                posture.update(
                    {
                        "active_policy_id": policy.id,
                        "active_policy_name": policy.name,
                        "active_policy_is_builtin": policy.is_builtin,
                        "active_policy_tier": policy.tier,
                        "active_policy_permissions": permissions,
                        "active_custom_permissions": bushido.get("custom_permissions"),
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
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
            )
            .limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return
        bushido = dict(agent.bushido_settings or {})
        stored_posture = dict(posture)
        for runtime_key in (
            "active_policy_id",
            "active_policy_name",
            "active_policy_is_builtin",
            "active_policy_tier",
            "active_policy_permissions",
            "active_custom_permissions",
        ):
            stored_posture.pop(runtime_key, None)
        bushido[_POSTURE_KEY] = stored_posture
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
    allowed_fields = set(_DEFAULT_POSTURE.keys()) - {"active_tier", "kill_switch_enabled"}
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


@router.put("/posture/active", response_model=ApiResponse)
async def select_active_security_posture(body: SecurityPostureSelectRequest):
    """Atomically select a built-in tier or assign a custom policy."""
    if (body.tier is None) == (body.policy_id is None):
        raise HTTPException(
            status_code=422,
            detail="Select exactly one built-in tier or custom policy",
        )

    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from shogun.db.models.security_policy import SecurityPolicy

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent)
            .where(
                Agent.agent_type == "shogun",
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
            )
            .limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise HTTPException(status_code=404, detail="Primary Shogun agent not found")

        bushido = dict(agent.bushido_settings or {})
        current = {**_DEFAULT_POSTURE, **bushido.get(_POSTURE_KEY, {})}
        old_label = str(
            current.get("active_policy_name")
            or current.get("active_tier", "tactical")
        )

        if body.policy_id is not None:
            policy = await db.get(SecurityPolicy, body.policy_id)
            if not policy or getattr(policy, "is_deleted", False):
                raise HTTPException(status_code=404, detail="Custom posture not found")
            if policy.is_builtin:
                raise HTTPException(
                    status_code=422,
                    detail="Built-in postures must be selected by tier",
                )
            if policy.tier in {"campaign", "ronin"} and not body.confirmed:
                raise HTTPException(status_code=409, detail="Explicit confirmation is required for elevated postures")
            agent.security_policy_id = policy.id
            current["active_tier"] = policy.tier
            current.update(TIER_CONSTRAINTS.get(policy.tier, {}))
            new_label = policy.name
        else:
            tier = body.tier.value
            if tier in {"campaign", "ronin"} and not body.confirmed:
                raise HTTPException(status_code=409, detail="Explicit confirmation is required for elevated postures")
            agent.security_policy_id = None
            current["active_tier"] = tier
            current.update(TIER_CONSTRAINTS[tier])
            new_label = tier

        bushido.pop("custom_permissions", None)
        for runtime_key in (
            "active_policy_id",
            "active_policy_name",
            "active_policy_is_builtin",
            "active_policy_tier",
            "active_policy_permissions",
            "active_custom_permissions",
        ):
            current.pop(runtime_key, None)
        bushido[_POSTURE_KEY] = current
        agent.bushido_settings = bushido
        await db.commit()

    selected = await _get_agent_posture()
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.posture_changed",
            f"Security posture changed: {old_label} → {new_label}",
            severity="warn"
            if selected.get("active_tier") in ("campaign", "ronin")
            else "info",
            detail={
                "old_posture": old_label,
                "new_posture": new_label,
                "policy_id": str(body.policy_id) if body.policy_id else None,
            },
        )
    except Exception:
        pass
    return ApiResponse(data=SecurityPostureResponse(**selected).model_dump())


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
    existing = await svc.get_by_id(policy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Policy not found")
    if existing.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot edit built-in policies")
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

    result = await svc.session.execute(select(Agent).where(Agent.security_policy_id == policy_id))
    agents = result.scalars().all()
    for agent in agents:
        agent.security_policy_id = None
        # Clear custom_permissions from bushido_settings if present
        if agent.bushido_settings and isinstance(agent.bushido_settings, dict):
            bs = dict(agent.bushido_settings)
            bs.pop("custom_permissions", None)
            stored_posture = {
                **_DEFAULT_POSTURE,
                **bs.get(_POSTURE_KEY, {}),
                "active_tier": record.tier,
            }
            stored_posture.update(TIER_CONSTRAINTS.get(record.tier, {}))
            for runtime_key in (
                "active_policy_id",
                "active_policy_name",
                "active_policy_is_builtin",
                "active_policy_tier",
                "active_policy_permissions",
                "active_custom_permissions",
            ):
                stored_posture.pop(runtime_key, None)
            bs[_POSTURE_KEY] = stored_posture
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

class ToolGateOverridesRequest(BaseModel):
    overrides: dict[str, str]


class ToolGateCapabilitiesRequest(BaseModel):
    permissions: dict


class ToolGateAdvancedRequest(BaseModel):
    enabled: bool = False
    rules: list[dict] = []


class ToolGateDetailRequest(BaseModel):
    allowed_internal_paths: list[str] = Field(default_factory=list)
    allowed_network_paths: list[str] = Field(default_factory=list)


class ToolGateSimulateRequest(BaseModel):
    tool_name: str
    args: dict = {}
    mode: str | None = None


def _toolgate_authority() -> dict:
    """Resolve policy ownership independently from transient connectivity."""
    try:
        from shogun.api.gensui_config import _get_client_status, _load_config

        config = _load_config()
        status = _get_client_status()
        managed = bool(config.get("enabled") and status.get("enrolled"))
        return {
            "mode": "gensui" if managed else "standalone",
            "editable": not managed,
            "enrolled": bool(status.get("enrolled")),
            "connected": bool(status.get("connected")),
            "server_url": config.get("server_url", ""),
            "last_sync_at": status.get("last_sync_at"),
            "effective_posture": status.get("effective_posture"),
        }
    except Exception:
        return {
            "mode": "standalone",
            "editable": True,
            "enrolled": False,
            "connected": False,
            "server_url": "",
            "last_sync_at": None,
            "effective_posture": None,
        }


async def _active_toolgate_context() -> tuple[dict, dict | None, str, dict]:
    from shogun.services.tool_gate import get_toolgate_scope

    posture = await _get_agent_posture()
    scope = get_toolgate_scope(posture)
    preset = None
    preset_key = posture.get("active_campaign_preset")
    if preset_key:
        from shogun.services.campaign_presets import get_preset

        preset = get_preset(preset_key)
    tier = scope["base_tier"]
    mode = "campaign" if tier == "campaign" else "ronin_desktop" if tier == "ronin" else "standard"
    return posture, preset, mode, scope


@router.get("/toolgate", response_model=ApiResponse)
async def get_toolgate_control():
    """Return ToolGate inventory, effective verdicts, ownership, and pending approvals."""
    from shogun.services.tool_gate import (
        MODE_THRESHOLDS,
        TOOL_RISK_REGISTRY,
        calculate_capability_risk,
        check_tool_access,
        get_gensui_advanced_controls,
        get_gensui_overrides,
        get_local_advanced_controls,
        get_local_overrides,
        get_local_tool_detail,
        resolve_explicit_overrides,
        tool_supports_path_controls,
    )
    from shogun.services.toolgate_confirm import list_pending_confirmations

    posture, preset, mode, scope = await _active_toolgate_context()
    local_overrides = get_local_overrides(scope["key"])
    gensui_overrides = get_gensui_overrides()
    authority = _toolgate_authority()
    advanced_controls = (
        get_gensui_advanced_controls()
        if authority["mode"] == "gensui"
        else get_local_advanced_controls(scope["key"])
    )
    effective_permissions = (
        posture.get("active_custom_permissions")
        or posture.get("active_policy_permissions")
        or {}
    )
    tools = []
    for tool_name, metadata in sorted(
        TOOL_RISK_REGISTRY.items(),
        key=lambda item: (item[1]["category"], item[0]),
    ):
        decision = await check_tool_access(
            mode,
            tool_name,
            {},
            campaign_preset=preset,
            local_scope=scope["key"],
        )
        _, _, layers = resolve_explicit_overrides(tool_name, preset, scope["key"])
        tools.append(
            {
                "name": tool_name,
                "category": metadata["category"],
                "risk": metadata["risk"],
                "default_action": MODE_THRESHOLDS[mode][metadata["risk"]].value,
                "local_override": local_overrides.get(tool_name),
                "campaign_override": layers["campaign"],
                "gensui_override": gensui_overrides.get(tool_name),
                "effective_action": decision.action.value,
                "reason": decision.reason,
                "supports_path_controls": tool_supports_path_controls(tool_name),
                "detail": get_local_tool_detail(tool_name, scope["key"]),
            }
        )

    return ApiResponse(
        data={
            "authority": authority,
            "active_tier": scope["base_tier"],
            "scope": scope,
            "capabilities": {
                "permissions": effective_permissions,
                "risk_score": calculate_capability_risk(effective_permissions),
                "editable": bool(
                    _toolgate_authority()["editable"]
                    and scope["kind"] == "custom_policy"
                ),
                "source": (
                    "agent_override"
                    if posture.get("active_custom_permissions")
                    else "custom_policy"
                    if scope["kind"] == "custom_policy"
                    else "builtin_tier"
                ),
            },
            "active_campaign_preset": posture.get("active_campaign_preset"),
            "mode": mode,
            "local_overrides": local_overrides,
            "advanced_controls": {
                **advanced_controls,
                "editable": bool(authority["editable"]),
                "source": "gensui" if authority["mode"] == "gensui" else "local",
            },
            "tools": tools,
            "pending_confirmations": list_pending_confirmations(),
        }
    )


@router.put("/toolgate/overrides", response_model=ApiResponse)
async def update_toolgate_overrides(body: ToolGateOverridesRequest):
    """Replace standalone overrides. Managed instances remain read-only even while offline."""
    authority = _toolgate_authority()
    if not authority["editable"]:
        raise HTTPException(
            status_code=423,
            detail="ToolGate is managed by Gensui. Edit the assigned posture in Gensui.",
        )

    from shogun.services.tool_gate import get_local_overrides, set_local_overrides

    _, _, _, scope = await _active_toolgate_context()

    try:
        set_local_overrides(body.overrides, scope["key"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.toolgate_overrides_updated",
            f"Standalone ToolGate overrides updated ({len(body.overrides)} rules)",
            policy_ref="toolgate:local",
            policy_decision="updated",
            detail={"scope": scope, "overrides": body.overrides},
        )
    except Exception:
        pass
    return ApiResponse(data={"scope": scope, "overrides": get_local_overrides(scope["key"])})


@router.put("/toolgate/tools/{tool_name}/detail", response_model=ApiResponse)
async def update_toolgate_tool_detail(tool_name: str, body: ToolGateDetailRequest):
    """Replace detailed standalone controls for one tool and policy scope."""
    authority = _toolgate_authority()
    if not authority["editable"]:
        raise HTTPException(
            status_code=423,
            detail="ToolGate is managed by Gensui. Edit detailed controls in Gensui.",
        )

    from shogun.services.tool_gate import (
        get_local_tool_detail,
        set_local_tool_detail,
        tool_supports_path_controls,
    )

    if not tool_supports_path_controls(tool_name):
        raise HTTPException(status_code=400, detail="This tool does not expose filesystem path controls.")
    _, _, _, scope = await _active_toolgate_context()
    try:
        set_local_tool_detail(tool_name, body.model_dump(), scope["key"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    saved = get_local_tool_detail(tool_name, scope["key"])
    return ApiResponse(data={"scope": scope, "tool_name": tool_name, "detail": saved})


@router.put("/toolgate/advanced", response_model=ApiResponse)
async def update_toolgate_advanced_controls(body: ToolGateAdvancedRequest):
    """Replace advanced content rules for the active standalone policy scope."""
    authority = _toolgate_authority()
    if not authority["editable"]:
        raise HTTPException(
            status_code=423,
            detail="ToolGate is managed by Gensui. Edit advanced controls in Gensui.",
        )

    from shogun.services.tool_gate import (
        get_local_advanced_controls,
        set_local_advanced_controls,
    )

    _, _, _, scope = await _active_toolgate_context()
    config = {"enabled": body.enabled, "rules": body.rules}
    try:
        set_local_advanced_controls(config, scope["key"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    saved = get_local_advanced_controls(scope["key"])
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.toolgate_advanced_updated",
            f"Advanced ToolGate controls updated ({len(saved['rules'])} rules)",
            policy_ref=scope["key"],
            policy_decision="updated",
            detail={"scope": scope, "enabled": saved["enabled"], "rule_count": len(saved["rules"])},
        )
    except Exception:
        pass
    return ApiResponse(data={"scope": scope, "advanced_controls": saved})


@router.put("/toolgate/capabilities", response_model=ApiResponse)
async def update_toolgate_capabilities(body: ToolGateCapabilitiesRequest):
    """Update capability boundaries on the assigned custom policy."""
    authority = _toolgate_authority()
    if not authority["editable"]:
        raise HTTPException(
            status_code=423,
            detail="ToolGate is managed by Gensui. Edit capabilities in Gensui.",
        )

    posture, _, _, scope = await _active_toolgate_context()
    if scope["kind"] != "custom_policy" or not posture.get("active_policy_id"):
        raise HTTPException(
            status_code=403,
            detail="Built-in tiers are protected presets. Create or assign a custom policy in Torii first.",
        )

    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from shogun.db.models.security_policy import SecurityPolicy
    from shogun.schemas.security import PolicyPermissions
    from shogun.services.tool_gate import calculate_capability_risk

    permissions = PolicyPermissions.model_validate(body.permissions).model_dump()
    async with async_session_factory() as db:
        policy = await db.get(SecurityPolicy, posture["active_policy_id"])
        if not policy or policy.is_builtin:
            raise HTTPException(status_code=403, detail="Only custom policies can be edited in ToolGate.")
        policy.permissions = permissions

        result = await db.execute(
            select(Agent)
            .where(
                Agent.agent_type == "shogun",
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
            )
            .limit(1)
        )
        agent = result.scalar_one_or_none()
        if agent and agent.bushido_settings:
            bushido = dict(agent.bushido_settings)
            bushido.pop("custom_permissions", None)
            agent.bushido_settings = bushido
        await db.commit()

    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_policy_event(
            "policy.capabilities_updated",
            f"ToolGate capability boundaries updated for {scope['label']}",
            policy_ref=scope["key"],
            policy_decision="updated",
            detail={"risk_score": calculate_capability_risk(permissions)},
        )
    except Exception:
        pass

    return ApiResponse(
        data={
            "scope": scope,
            "permissions": permissions,
            "risk_score": calculate_capability_risk(permissions),
        }
    )


@router.post("/toolgate/simulate", response_model=ApiResponse)
async def simulate_toolgate_call(body: ToolGateSimulateRequest):
    """Evaluate a proposed call without executing the tool."""
    from shogun.services.tool_gate import TOOL_RISK_REGISTRY, check_tool_access

    if body.tool_name not in TOOL_RISK_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown ToolGate tool '{body.tool_name}'")
    _, preset, default_mode, scope = await _active_toolgate_context()
    mode = body.mode or default_mode
    decision = await check_tool_access(
        mode,
        body.tool_name,
        body.args,
        campaign_preset=preset,
        local_scope=scope["key"],
    )
    return ApiResponse(
        data={
            "tool_name": decision.tool_name,
            "action": decision.action.value,
            "risk_level": decision.risk_level.value,
            "reason": decision.reason,
            "parameter_flags": decision.parameter_flags,
        }
    )


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
