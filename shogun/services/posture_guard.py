"""Posture Guard — runtime enforcement of Security Posture constraints.

Every AI operation entry point (chat, agent creation, Telegram) calls into
this module before proceeding.  The guard reads the **live** posture from the
database (via ``_get_agent_posture``) and raises or returns enforcement
decisions.

Enforcement matrix
──────────────────
  kill_switch_active  →  block ALL AI operations (chat, spawn, Telegram)
  max_active_subagents →  block Samurai creation when limit reached
  skill_auto_install   →  strip model-management tools from LLM tool list
  shell_enabled        →  (reserved for future shell tools)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

log = logging.getLogger("shogun.posture_guard")


# ── Kill-switch gate ─────────────────────────────────────────────────

async def check_kill_switch() -> None:
    """Raise HTTP 503 if the global kill switch (HARAKIRI) is active.

    Call this at the top of every AI-facing entry point.
    Also checks Gensui posture if Gensui is enabled.
    """
    from shogun.api.security import _get_agent_posture

    posture = await _get_agent_posture()
    if posture.get("kill_switch_active", False):
        log.warning("[PostureGuard] Kill switch is ACTIVE — blocking operation")
        _emit_block_event("kill_switch", "Operation blocked: HARAKIRI kill switch is active")
        raise HTTPException(
            status_code=503,
            detail="⛩️ HARAKIRI active — all AI operations are suspended. "
                   "Deactivate the kill switch via the Torii to resume.",
        )

    # ── Gensui external posture enforcement ──────────────────
    from shogun.services.gensui_policy_guard import check_gensui_model_call
    await check_gensui_model_call()


# ── Subagent limit gate ─────────────────────────────────────────────

async def check_subagent_limit() -> None:
    """Raise HTTP 403 if creating another Samurai would exceed the tier limit.

    Call this before any Samurai agent creation (API endpoint + native skill).
    """
    from shogun.api.security import _get_agent_posture
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from sqlalchemy import select, func

    posture = await _get_agent_posture()
    max_agents = posture.get("max_active_subagents", 5)
    tier = posture.get("active_tier", "tactical")

    async with async_session_factory() as db:
        result = await db.execute(
            select(func.count()).select_from(Agent).where(
                Agent.agent_type == "samurai",
                Agent.status.in_(["active", "idle", "running"]),
                Agent.is_deleted == False,
            )
        )
        current_count = result.scalar() or 0

    if current_count >= max_agents:
        log.warning(
            "[PostureGuard] Subagent limit reached: %d/%d (tier=%s)",
            current_count, max_agents, tier,
        )
        _emit_block_event(
            "subagent_limit",
            f"Samurai creation blocked: {current_count}/{max_agents} active "
            f"(tier {tier.upper()} allows max {max_agents})",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] allows a maximum of "
                   f"{max_agents} active Samurai agents. Currently {current_count} "
                   f"are active. Change the security tier in the Torii to allow more.",
        )


async def check_subagent_limit_soft() -> str | None:
    """Non-raising variant for native skill execution — returns error string or None."""
    try:
        await check_subagent_limit()
        return None
    except HTTPException as exc:
        return exc.detail


# ── Tool filtering based on posture ──────────────────────────────────

async def get_posture_tool_filter() -> dict[str, Any]:
    """Return the current posture constraints relevant to tool gating.

    Returns a dict with:
        - kill_switch_active: bool
        - skill_auto_install: bool
        - shell_enabled: bool
        - max_active_subagents: int
        - active_tier: str
        - comms_read_email: bool
        - comms_send_email: bool
        - comms_read_calendar: bool
        - comms_create_events: bool
        - comms_list_cron: bool
        - comms_manage_cron: bool

    The caller uses these to strip tools from the LLM's available tool list.
    """
    from shogun.api.security import _get_agent_posture

    posture = await _get_agent_posture()
    tier = posture.get("active_tier", "tactical")

    # Derive Agent Flow permissions from tier
    agentflow_create = tier in ("tactical", "campaign", "ronin")
    agentflow_execute = tier in ("tactical", "campaign", "ronin")
    agentflow_autonomous = tier in ("campaign", "ronin")

    return {
        "kill_switch_active": posture.get("kill_switch_active", False),
        "skill_auto_install": posture.get("skill_auto_install", False),
        "shell_enabled": posture.get("shell_enabled", False),
        "max_active_subagents": posture.get("max_active_subagents", 5),
        "active_tier": tier,
        "comms_read_email": posture.get("comms_read_email", True),
        "comms_send_email": posture.get("comms_send_email", True),
        "comms_read_calendar": posture.get("comms_read_calendar", True),
        "comms_create_events": posture.get("comms_create_events", True),
        "comms_list_cron": posture.get("comms_list_cron", True),
        "comms_manage_cron": posture.get("comms_manage_cron", False),
        "agentflow_create": agentflow_create,
        "agentflow_execute": agentflow_execute,
        "agentflow_autonomous": agentflow_autonomous,
        # Mado browser automation
        "mado_enabled": posture.get("mado_enabled", False),
        "mado_headless_only": posture.get("mado_headless_only", True),
        "mado_max_sessions": posture.get("mado_max_sessions", 3),
        "mado_autonomous_browsing": posture.get("mado_autonomous_browsing", False),
        "mado_downloads_enabled": posture.get("mado_downloads_enabled", False),
        "mado_uploads_enabled": posture.get("mado_uploads_enabled", False),
        # Ronin desktop control
        "ronin_enabled": posture.get("ronin_enabled", False),
        "ronin_mouse_enabled": posture.get("ronin_mouse_enabled", False),
        "ronin_keyboard_enabled": posture.get("ronin_keyboard_enabled", False),
        "ronin_screenshots_enabled": posture.get("ronin_screenshots_enabled", True),
        # Office App Mode (Katana)
        "office_enabled": posture.get("office_enabled", False),
        "office_excel_enabled": posture.get("office_excel_enabled", True),
        "office_word_enabled": posture.get("office_word_enabled", True),
        "office_ppt_enabled": posture.get("office_ppt_enabled", True),
        "office_outlook_enabled": posture.get("office_outlook_enabled", True),
        "office_outlook_mode": posture.get("office_outlook_mode", "draft_only"),
    }


# ── Office App Mode access gate ─────────────────────────────────────

async def check_office_access() -> None:
    """Raise HTTP 403 if Office App Mode is disabled at current tier.

    Call this before any Office automation operation.
    """
    from shogun.api.security import _get_agent_posture

    posture = await _get_agent_posture()
    if not posture.get("office_enabled", False):
        tier = posture.get("active_tier", "tactical")
        log.warning("[PostureGuard] Office App Mode blocked (tier=%s)", tier)
        _emit_block_event(
            "office_disabled",
            f"Office automation blocked: Office App Mode is disabled at tier {tier.upper()}",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] does not permit Office automation. "
                   "Enable Office App Mode in the Katana settings.",
        )


# ── Workspace access gate ────────────────────────────────────────────

async def check_workspace_access() -> str:
    """Check if workspace access is allowed at the current posture tier.

    Returns the resolved workspace path string if access is permitted.
    Raises HTTP 403 if the posture is SHRINE (workspace disabled).
    """
    from shogun.api.security import _get_agent_posture
    from shogun.config import settings

    posture = await _get_agent_posture()
    if not posture.get("workspace_enabled", True):
        tier = posture.get("active_tier", "tactical")
        log.warning("[PostureGuard] Workspace access blocked (tier=%s)", tier)
        _emit_block_event(
            "workspace_disabled",
            f"Workspace access blocked: disabled at tier {tier.upper()}",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] does not permit workspace access. "
                   "Raise the security tier above SHRINE in the Torii to use the workspace.",
        )

    workspace_dir = settings.workspace_path
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return str(workspace_dir.resolve())


# ── Mado browser access gate ────────────────────────────────────────

async def check_mado_access() -> None:
    """Raise HTTP 403 if Mado browser access is disabled at current tier.

    Call this before any browser automation operation.
    """
    from shogun.api.security import _get_agent_posture

    posture = await _get_agent_posture()
    if not posture.get("mado_enabled", False):
        tier = posture.get("active_tier", "tactical")
        log.warning("[PostureGuard] Mado browser access blocked (tier=%s)", tier)
        _emit_block_event(
            "mado_disabled",
            f"Browser automation blocked: Mado is disabled at tier {tier.upper()}",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] does not permit browser automation. "
                   "Change the security tier in the Torii to enable Mado.",
        )

    # ── Gensui external Mado enforcement ─────────────────────
    from shogun.services.gensui_policy_guard import check_gensui_mado
    await check_gensui_mado()


def check_mado_browser_mode(browser_mode: str, posture: dict[str, Any]) -> None:
    """Reject visible browser sessions when the active posture is headless-only."""
    if browser_mode == "visible" and posture.get("mado_headless_only", True):
        tier = posture.get("active_tier", "tactical")
        _emit_block_event(
            "mado_visible_blocked",
            f"Visible browser session blocked at tier {tier.upper()}",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] permits headless Mado sessions only.",
        )


async def check_mado_session_limit() -> None:
    """Raise HTTP 403 if creating another browser session would exceed the tier limit."""
    from shogun.api.security import _get_agent_posture
    from shogun.db.engine import async_session_factory
    from shogun.services.mado_service import _active_contexts
    from shogun.services.mado_service_crud import MadoSessionService

    posture = await _get_agent_posture()
    max_sessions = posture.get("mado_max_sessions", 3)
    tier = posture.get("active_tier", "tactical")

    async with async_session_factory() as db:
        svc = MadoSessionService(db)
        persisted_count = await svc.count_active()

    # AgentFlow sessions are runtime-only and use ``flow_`` IDs. API/native
    # sessions are persisted and use UUID IDs, even while they are open.
    runtime_only_count = sum(
        1 for session_id in _active_contexts
        if str(session_id).startswith("flow_")
    )
    current_count = persisted_count + runtime_only_count

    if current_count >= max_sessions:
        log.warning(
            "[PostureGuard] Mado session limit reached: %d/%d (tier=%s)",
            current_count, max_sessions, tier,
        )
        _emit_block_event(
            "mado_session_limit",
            f"Browser session creation blocked: {current_count}/{max_sessions} active "
            f"(tier {tier.upper()} allows max {max_sessions})",
        )
        raise HTTPException(
            status_code=403,
            detail=f"Security posture [{tier.upper()}] allows a maximum of "
                   f"{max_sessions} browser sessions. Currently {current_count} "
                   "are active. Close sessions or change tier in the Torii.",
        )


async def get_posture_permissions() -> dict[str, Any]:
    """Alias for get_posture_tool_filter — used by flow engine and native skills."""
    return await get_posture_tool_filter()


def filter_tools_by_posture(tools: list[dict], posture: dict) -> tuple[list[dict], list[str]]:
    """Filter a tool list based on posture constraints.

    Returns (allowed_tools, denied_tool_names).
    """
    allowed = []
    denied = []

    for tool in tools:
        name = tool["function"]["name"]

        # spawn_samurai blocked when max_active_subagents == 0 (SHRINE)
        if name == "spawn_samurai" and posture.get("max_active_subagents", 5) == 0:
            denied.append(name)
            continue

        # Model management tools blocked when skill_auto_install is False
        if name in ("list_available_models", "update_model_settings"):
            if not posture.get("skill_auto_install", False):
                denied.append(name)
                continue

        # ── Comms: Email tools ──
        if name in ("fetch_inbox", "read_email") and not posture.get("comms_read_email", True):
            denied.append(name)
            continue
        if name == "send_email" and not posture.get("comms_send_email", True):
            denied.append(name)
            continue

        # ── Comms: Calendar tools ──
        if name == "list_calendar_events" and not posture.get("comms_read_calendar", True):
            denied.append(name)
            continue
        if name == "create_calendar_event" and not posture.get("comms_create_events", True):
            denied.append(name)
            continue

        # ── Comms: Cron job tools ──
        if name == "list_cron_jobs" and not posture.get("comms_list_cron", True):
            denied.append(name)
            continue
        if name in ("create_cron_job", "delete_cron_job") and not posture.get("comms_manage_cron", False):
            denied.append(name)
            continue

        # ── Mado: Browser tools ──
        if name in ("browse_web", "take_screenshot") and not posture.get("mado_enabled", False):
            denied.append(name)
            continue

        # ── Office: Katana tools ──
        if name.startswith("office_") and not posture.get("office_enabled", False):
            denied.append(name)
            continue
        # Per-app office tool gating
        if name.startswith("office_excel_") and not posture.get("office_excel_enabled", True):
            denied.append(name)
            continue
        if name.startswith("office_word_") and not posture.get("office_word_enabled", True):
            denied.append(name)
            continue
        if name.startswith("office_pptx_") and not posture.get("office_ppt_enabled", True):
            denied.append(name)
            continue
        if name.startswith("office_outlook_") and not posture.get("office_outlook_enabled", True):
            denied.append(name)
            continue

        # ── Ronin: Desktop control tools ──
        if name in ("desktop_screenshot", "desktop_click", "desktop_type") and not posture.get("ronin_enabled", False):
            denied.append(name)
            continue

        allowed.append(tool)

    return allowed, denied


# ── Event emission helper ────────────────────────────────────────────

def _emit_block_event(block_type: str, message: str) -> None:
    """Fire-and-forget compliance event for blocked operations."""
    try:
        import asyncio
        from shogun.services.event_logger import EventLogger

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(EventLogger.emit_policy_event(
            "policy.posture_blocked",
            message,
            severity="warn",
            policy_ref=f"posture_guard:{block_type}",
            policy_decision="denied",
            policy_reason=message,
        ))
        loop.create_task(EventLogger.emit_risk_event(
            "risk.posture_enforcement",
            message,
            severity="warn",
            risk_score="medium",
            detail={"block_type": block_type},
        ))
    except Exception:
        pass
