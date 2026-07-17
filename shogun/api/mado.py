"""Mado API routes — browser automation session management and actions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_mado_session_service
from shogun.config import settings
from shogun.schemas.common import ApiResponse
from shogun.schemas.mado import (
    DEFAULT_SECURITY_POLICY,
    MadoActionRequest,
    MadoClickRequest,
    MadoExecuteJsRequest,
    MadoExtractRequest,
    MadoFillFormRequest,
    MadoNavigateRequest,
    MadoPressKeyRequest,
    MadoScreenshotRequest,
    MadoScrollRequest,
    MadoSecurityPolicy,
    MadoSelectRequest,
    MadoSessionCreate,
    MadoSessionListItem,
    MadoSessionResponse,
    MadoStatusResponse,
    MadoUploadRequest,
    MadoVerifyRequest,
    MadoWaitRequest,
)
from shogun.services.mado_service_crud import MadoSessionService

router = APIRouter(prefix="/mado", tags=["Mado – Browser Automation"])


# ═══════════════════════════════════════════════════════════════
# STATUS & INSTALL
# ═══════════════════════════════════════════════════════════════


@router.get("/status", response_model=ApiResponse)
async def get_mado_status():
    """Get Mado subsystem status: Chromium installation and active sessions."""
    from shogun.services.mado_hardening import mado_config, profile_manager, runtime_registry
    from shogun.services.mado_service import get_chromium_status, list_screenshots

    status = await get_chromium_status()
    screenshots = list_screenshots()

    return ApiResponse(
        data=MadoStatusResponse(**status),
        meta={
            "screenshots_count": len(screenshots),
            "runtime_sessions": runtime_registry.list(),
            "profiles": profile_manager.list(),
            "config": mado_config(),
        },
    )


@router.post("/install", response_model=ApiResponse)
async def install_chromium():
    """Trigger Playwright Chromium browser installation."""
    from shogun.services.mado_service import install_chromium as do_install

    result = await do_install()
    return ApiResponse(data=result)


# ═══════════════════════════════════════════════════════════════
# SESSION CRUD
# ═══════════════════════════════════════════════════════════════


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(
    status: str | None = None,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """List all browser sessions."""
    records, total = await svc.list_sessions(status=status)
    return ApiResponse(
        data=[MadoSessionListItem.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/sessions", response_model=ApiResponse, status_code=201)
async def create_session(
    body: MadoSessionCreate,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Create a new browser session (validates Torii permissions)."""
    from shogun.services.mado_hardening import emit_mado_event, mado_config, permission_guard, runtime_registry
    from shogun.services.posture_guard import (
        check_mado_access,
        check_mado_browser_mode,
        check_mado_session_limit,
        get_posture_tool_filter,
    )

    await check_mado_access()
    await check_mado_session_limit()
    check_mado_browser_mode(body.browser_mode, await get_posture_tool_filter())
    posture = await permission_guard.check(
        "mado.session.create", mode=body.browser_mode, persistent_profile=body.persistent_profile
    )
    if body.authenticated_session and not (
        posture.get("mado_authenticated_sessions_enabled", False)
        and mado_config().get("allow_authenticated_sessions", False)
    ):
        raise HTTPException(status_code=403, detail="Authenticated Mado sessions require explicit permission.")

    # Check for duplicate profile name
    existing = await svc.get_by_profile_name(body.profile_name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A session with profile name '{body.profile_name}' already exists.",
        )

    record = await svc.create(
        name=body.name,
        profile_name=body.profile_name,
        agent_id=body.agent_id,
        browser_mode=body.browser_mode,
        domain_allowlist=body.domain_allowlist,
        security_policy=body.security_policy.model_dump() if body.security_policy else DEFAULT_SECURITY_POLICY.copy(),
        session_data={
            "stack_run_id": str(body.stack_run_id) if body.stack_run_id else None,
            "step_run_id": str(body.step_run_id) if body.step_run_id else None,
            "posture": posture.get("active_tier"),
            "authenticated_session": body.authenticated_session,
            "persistent_profile": body.persistent_profile,
            "action_history": [],
            "artifacts": [],
        },
    )
    runtime_registry.register(
        str(record.id),
        profile_id=record.profile_name,
        posture=posture.get("active_tier"),
        mode=record.browser_mode,
        stack_run_id=body.stack_run_id,
        step_run_id=body.step_run_id,
        agent_id=body.agent_id,
    )
    await emit_mado_event(
        "mado.session.created",
        f"Mado session created: {record.name}",
        session_id=str(record.id),
        stack_run_id=str(body.stack_run_id) if body.stack_run_id else None,
        step_run_id=str(body.step_run_id) if body.step_run_id else None,
        agent_id=str(body.agent_id) if body.agent_id else None,
        detail={"profile": body.profile_name, "mode": body.browser_mode},
    )
    return ApiResponse(data=MadoSessionResponse.model_validate(record))


@router.get("/sessions/{session_id}", response_model=ApiResponse)
async def get_session(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Get a single browser session."""
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    return ApiResponse(data=MadoSessionResponse.model_validate(record))


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Close and soft-delete a browser session."""
    from shogun.services.mado_hardening import emit_mado_event
    from shogun.services.mado_service import close_browser

    # Close the browser if active
    await close_browser(str(session_id))

    success = await svc.delete(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Browser session not found")
    await emit_mado_event("mado.session.closed", "Mado session deleted", session_id=str(session_id))
    return ApiResponse(data={"deleted": True})


@router.patch("/sessions/{session_id}/policy", response_model=ApiResponse)
async def update_session_policy(
    session_id: uuid.UUID,
    body: MadoSecurityPolicy,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Update the security policy of an existing browser session."""
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")

    record.security_policy = body.model_dump()
    await svc.session.flush()
    await svc.session.refresh(record)
    await svc.session.commit()
    return ApiResponse(data=MadoSessionResponse.model_validate(record))


# ═══════════════════════════════════════════════════════════════
# BROWSER ACTIONS — All require an active browser session
# ═══════════════════════════════════════════════════════════════


async def _ensure_browser_active(
    session_id: uuid.UUID,
    svc: MadoSessionService,
) -> None:
    """Ensure the browser is launched for this session, launching if needed."""
    from shogun.services.mado_hardening import runtime_registry
    from shogun.services.mado_service import _active_contexts, close_browser, get_page_info, launch_browser

    sid = str(session_id)
    if sid in _active_contexts:
        health = await get_page_info(sid)
        if health.get("status") == "ok":
            return
        await close_browser(sid)

    # Fetch session record to get profile and mode
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")

    metadata = record.session_data or {}
    runtime_registry.register(
        str(session_id),
        profile_id=record.profile_name,
        mode=record.browser_mode,
        posture=metadata.get("posture"),
        stack_run_id=metadata.get("stack_run_id"),
        step_run_id=metadata.get("step_run_id"),
        agent_id=record.agent_id,
    )
    result = await launch_browser(
        session_id=sid,
        profile_name=record.profile_name,
        mode=record.browser_mode,
    )
    if result.get("status") == "error":
        raise HTTPException(
            status_code=500,
            detail=f"Failed to launch browser: {result.get('error', 'Unknown error')}",
        )

    # Update session status
    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))


async def _execute_governed(
    session_id: uuid.UUID,
    svc: MadoSessionService,
    action_type: str,
    operation,
    *,
    detail: dict | None = None,
    verification: dict | None = None,
):
    from shogun.services.mado_hardening import governed_action

    result = await governed_action(str(session_id), action_type, operation, detail=detail, verification=verification)
    record = await svc.get_by_id(session_id)
    if record:
        data = dict(record.session_data or {})
        history = list(data.get("action_history", []))
        history.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": action_type,
                "status": result.get("status", "ok"),
                "url": result.get("url"),
                "verification": result.get("verification"),
                "error": result.get("error"),
            }
        )
        data["action_history"] = history[-200:]
        data["last_action"] = action_type
        data["last_verification"] = result.get("verification")
        data["last_error"] = result.get("error")
        await svc.update_status(
            session_id,
            "error" if result.get("status") == "error" else "active",
            session_data=data,
            last_url=result.get("url") or record.last_url,
            last_active_at=datetime.now(timezone.utc),
        )
        await svc.session.commit()
    return result


@router.post("/sessions/{session_id}/navigate", response_model=ApiResponse)
@router.post("/sessions/{session_id}/open-url", response_model=ApiResponse)
async def do_navigate(
    session_id: uuid.UUID,
    body: MadoNavigateRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Navigate to a URL in the browser session."""
    from shogun.services.mado_hardening import permission_guard
    from shogun.services.mado_policy_guard import check_navigate_policy, increment_page_load_count
    from shogun.services.mado_service import navigate
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await permission_guard.check("mado.navigation.open_url", url=body.url)
    await _ensure_browser_active(session_id, svc)

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    check_navigate_policy(record, body.url)

    # Domain allowlist comes from the session only (Torii controls on/off, not domains)
    allowlist = record.domain_allowlist or []

    result = await _execute_governed(
        session_id,
        svc,
        "mado.navigation.open_url",
        lambda: navigate(
            session_id=str(session_id),
            url=body.url,
            wait_until=body.wait_until,
            domain_allowlist=allowlist if allowlist else None,
        ),
        detail={"url": body.url},
        verification={"verification_type": "no_error_banner"},
    )

    if result.get("status") == "blocked":
        raise HTTPException(status_code=403, detail=result.get("reason", "Domain blocked"))

    # Update last URL + increment page load counter
    if result.get("url"):
        await svc.update_status(
            session_id,
            "active",
            last_url=result["url"],
            last_active_at=datetime.now(timezone.utc),
        )
        await increment_page_load_count(record, svc)

    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/extract", response_model=ApiResponse)
async def do_extract(
    session_id: uuid.UUID,
    body: MadoExtractRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Extract content from the current page."""
    from shogun.services.mado_service import extract_content
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    result = await _execute_governed(
        session_id,
        svc,
        "mado.page.extract_text",
        lambda: extract_content(session_id=str(session_id), selector=body.selector, extract_type=body.extract_type),
        detail={"selector": body.selector, "extract_type": body.extract_type},
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/screenshot", response_model=ApiResponse)
async def do_screenshot(
    session_id: uuid.UUID,
    body: MadoScreenshotRequest | None = None,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Capture a screenshot of the current page."""
    from shogun.services.mado_service import screenshot
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    result = await _execute_governed(
        session_id,
        svc,
        "mado.page.screenshot",
        lambda: screenshot(
            session_id=str(session_id),
            full_page=body.full_page if body else False,
            selector=body.selector if body else None,
        ),
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/pdf", response_model=ApiResponse)
async def do_pdf(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Generate a PDF of the current page."""
    from shogun.services.mado_service import generate_pdf
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    result = await generate_pdf(session_id=str(session_id))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/fill-form", response_model=ApiResponse)
async def do_fill_form(
    session_id: uuid.UUID,
    body: MadoFillFormRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Fill form fields on the current page."""
    from shogun.services.mado_policy_guard import check_form_submit_policy
    from shogun.services.mado_service import fill_form
    from shogun.services.posture_guard import check_mado_access, get_posture_tool_filter

    await check_mado_access()

    posture = await get_posture_tool_filter()
    if not posture.get("mado_form_submit_enabled", False):
        raise HTTPException(status_code=403, detail="Form filling/submission is disabled by the current posture.")

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    check_form_submit_policy(record)

    await _ensure_browser_active(session_id, svc)

    result = await _execute_governed(
        session_id,
        svc,
        "mado.form.fill",
        lambda: fill_form(session_id=str(session_id), fields=body.fields),
        detail={"field_count": len(body.fields)},
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/click", response_model=ApiResponse)
async def do_click(
    session_id: uuid.UUID,
    body: MadoClickRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Click an element on the current page."""
    from shogun.services.mado_service import click_element
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    result = await _execute_governed(
        session_id,
        svc,
        "mado.action.click",
        lambda: click_element(session_id=str(session_id), selector=body.selector),
        detail={"selector": body.selector},
        verification=body.expected_result,
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/execute-js", response_model=ApiResponse)
async def do_execute_js(
    session_id: uuid.UUID,
    body: MadoExecuteJsRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Execute JavaScript on the current page."""
    from shogun.services.mado_policy_guard import check_js_execution_policy
    from shogun.services.mado_service import execute_js
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    check_js_execution_policy(record)

    await _ensure_browser_active(session_id, svc)

    result = await execute_js(session_id=str(session_id), script=body.script)

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/upload", response_model=ApiResponse)
async def do_upload(
    session_id: uuid.UUID,
    body: MadoUploadRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Upload a file to a form input."""
    from shogun.services.mado_service import upload_file
    from shogun.services.posture_guard import check_mado_access, get_posture_tool_filter

    await check_mado_access()

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")

    from shogun.services.mado_policy_guard import check_upload_policy

    check_upload_policy(record)

    # Check upload permission (global Torii)
    posture = await get_posture_tool_filter()
    if not posture.get("mado_uploads_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="File uploads are disabled at the current security tier.",
        )

    await _ensure_browser_active(session_id, svc)

    result = await _execute_governed(
        session_id,
        svc,
        "mado.upload.file",
        lambda: upload_file(session_id=str(session_id), selector=body.selector, file_path=body.file_path),
        detail={"selector": body.selector, "filename": Path(body.file_path).name},
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/download", response_model=ApiResponse)
async def do_download(
    session_id: uuid.UUID,
    body: dict | None = None,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Wait for and save a pending download."""
    from shogun.services.mado_service import download_file
    from shogun.services.posture_guard import check_mado_access, get_posture_tool_filter

    await check_mado_access()

    # Per-session policy enforcement
    record_pre = await svc.get_by_id(session_id)
    if not record_pre or record_pre.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")

    from shogun.services.mado_policy_guard import check_download_policy

    check_download_policy(record_pre)

    # Check download permission (global Torii)
    posture = await get_posture_tool_filter()
    if not posture.get("mado_downloads_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="File downloads are disabled at the current security tier.",
        )

    await _ensure_browser_active(session_id, svc)

    record = await svc.get_by_id(session_id)
    body = body or {}
    result = await _execute_governed(
        session_id,
        svc,
        "mado.download.file",
        lambda: download_file(
            session_id=str(session_id), profile_name=record.profile_name, selector=body.get("selector")
        ),
        detail={"selector": body.get("selector")},
        verification={"verification_type": "file_downloaded", "expected": body.get("filename_pattern", "*")},
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/wait", response_model=ApiResponse)
async def do_wait(
    session_id: uuid.UUID,
    body: MadoWaitRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Wait for a CSS selector to appear on the page."""
    from shogun.services.mado_service import wait_for_selector
    from shogun.services.posture_guard import check_mado_access

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    result = await wait_for_selector(
        session_id=str(session_id),
        selector=body.selector,
        timeout=body.timeout,
        state=body.state,
    )
    return ApiResponse(data=result)


@router.get("/config", response_model=ApiResponse)
async def get_mado_config():
    from shogun.services.mado_hardening import mado_config

    return ApiResponse(data=mado_config())


@router.patch("/config", response_model=ApiResponse)
async def update_mado_config(body: dict):
    from shogun.api.setup import _read_setup, _write_setup
    from shogun.services.mado_hardening import emit_mado_event, mado_config

    editable = {
        "enabled",
        "default_mode",
        "headless_allowed",
        "visible_allowed",
        "allowed_domains",
        "blocked_domains",
        "allow_external_urls",
        "allow_persistent_profiles",
        "allow_authenticated_sessions",
        "allow_file_downloads",
        "allow_file_uploads",
        "allow_form_submit",
        "require_verification",
        "max_pages_per_run",
        "max_runtime_seconds",
        "default_navigation_timeout_ms",
        "default_action_timeout_ms",
        "retry",
        "page_readiness",
        "audit",
    }
    unknown = set(body) - editable
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unsupported Mado settings: {', '.join(sorted(unknown))}")
    setup = _read_setup()
    setup["mado"] = {**setup.get("mado", {}), **{key: value for key, value in body.items() if key in editable}}
    _write_setup(setup)
    await emit_mado_event(
        "mado.config.updated", "Mado hardening configuration updated", detail={"changed_fields": sorted(body)}
    )
    return ApiResponse(data=mado_config())


@router.post("/sessions/{session_id}/close", response_model=ApiResponse)
async def close_session(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import emit_mado_event, runtime_registry
    from shogun.services.mado_service import close_browser

    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    result = await close_browser(str(session_id))
    runtime_registry.close(str(session_id))
    await svc.update_status(session_id, "closed", last_active_at=datetime.now(timezone.utc))
    await svc.session.commit()
    await emit_mado_event("mado.session.closed", "Mado session closed", session_id=str(session_id))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/pause", response_model=ApiResponse)
async def pause_session(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import emit_mado_event, runtime_registry

    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    state = runtime_registry.pause(str(session_id))
    await svc.update_status(session_id, "paused", last_active_at=datetime.now(timezone.utc))
    await svc.session.commit()
    await emit_mado_event("mado.session.paused", "Mado session paused", session_id=str(session_id))
    return ApiResponse(data=vars(state))


@router.post("/sessions/{session_id}/resume", response_model=ApiResponse)
async def resume_session(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import emit_mado_event, runtime_registry

    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    await _ensure_browser_active(session_id, svc)
    state = runtime_registry.resume(str(session_id))
    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    await svc.session.commit()
    await emit_mado_event("mado.session.resumed", "Mado session resumed", session_id=str(session_id))
    return ApiResponse(data=vars(state))


@router.get("/sessions/{session_id}/observe", response_model=ApiResponse)
async def observe_session(
    session_id: uuid.UUID,
    mode: str = "hybrid",
    screenshot: bool = True,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import observe_page

    await _ensure_browser_active(session_id, svc)
    return ApiResponse(data=await observe_page(str(session_id), screenshot=screenshot, mode=mode))


@router.get("/sessions/{session_id}/text", response_model=ApiResponse)
async def session_text(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    observed = (await observe_session(session_id, "text_extract", False, svc)).data
    return ApiResponse(
        data={"url": observed.get("url"), "title": observed.get("title"), "text": observed.get("visible_text")}
    )


@router.get("/sessions/{session_id}/forms", response_model=ApiResponse)
async def session_forms(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    observed = (await observe_session(session_id, "dom", False, svc)).data
    return ApiResponse(data=observed.get("forms", []))


@router.get("/sessions/{session_id}/tables", response_model=ApiResponse)
async def session_tables(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    observed = (await observe_session(session_id, "dom", False, svc)).data
    return ApiResponse(data=observed.get("tables", []))


@router.post("/sessions/{session_id}/reload", response_model=ApiResponse)
async def reload_session_page(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import reload_page

    await _ensure_browser_active(session_id, svc)
    return ApiResponse(
        data=await _execute_governed(session_id, svc, "mado.navigation.reload", lambda: reload_page(str(session_id)))
    )


@router.post("/sessions/{session_id}/back", response_model=ApiResponse)
async def back_session_page(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import go_back

    await _ensure_browser_active(session_id, svc)
    return ApiResponse(
        data=await _execute_governed(session_id, svc, "mado.navigation.back", lambda: go_back(str(session_id)))
    )


@router.post("/sessions/{session_id}/forward", response_model=ApiResponse)
async def forward_session_page(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import go_forward

    await _ensure_browser_active(session_id, svc)
    return ApiResponse(
        data=await _execute_governed(session_id, svc, "mado.navigation.forward", lambda: go_forward(str(session_id)))
    )


@router.post("/sessions/{session_id}/wait-for-ready", response_model=ApiResponse)
async def wait_session_ready(
    session_id: uuid.UUID,
    timeout: int = 30000,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import wait_for_ready

    await _ensure_browser_active(session_id, svc)
    return ApiResponse(data=await wait_for_ready(str(session_id), timeout=timeout))


@router.post("/sessions/{session_id}/select", response_model=ApiResponse)
async def select_session_option(
    session_id: uuid.UUID,
    body: MadoSelectRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import select_option

    await _ensure_browser_active(session_id, svc)
    result = await _execute_governed(
        session_id,
        svc,
        "mado.action.select",
        lambda: select_option(str(session_id), body.selector, body.value),
        detail={"selector": body.selector},
        verification=body.expected_result,
    )
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/type", response_model=ApiResponse)
async def type_in_session(
    session_id: uuid.UUID,
    body: dict,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import fill_form

    selector = str(body.get("selector") or "")
    label = str(body.get("label") or "")
    if not selector and not label:
        raise HTTPException(status_code=400, detail="Provide a selector or semantic field label.")
    await _ensure_browser_active(session_id, svc)
    result = await _execute_governed(
        session_id,
        svc,
        "mado.action.type",
        lambda: fill_form(
            str(session_id),
            [{"selector": selector, "label": label, "value": str(body.get("text") or body.get("value") or "")}],
        ),
        detail={"selector": selector, "label": label, "value": "[REDACTED]"},
        verification=body.get("expected_result"),
    )
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/hover", response_model=ApiResponse)
async def hover_in_session(
    session_id: uuid.UUID,
    body: dict,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import hover_element

    selector = str(body.get("selector") or "")
    await _ensure_browser_active(session_id, svc)
    return ApiResponse(
        data=await _execute_governed(
            session_id,
            svc,
            "mado.action.hover",
            lambda: hover_element(str(session_id), selector),
            detail={"selector": selector},
        )
    )


@router.post("/sessions/{session_id}/scroll", response_model=ApiResponse)
async def scroll_session_page(
    session_id: uuid.UUID,
    body: MadoScrollRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import scroll_page

    await _ensure_browser_active(session_id, svc)
    result = await _execute_governed(
        session_id,
        svc,
        "mado.action.scroll",
        lambda: scroll_page(str(session_id), body.delta_x, body.delta_y),
    )
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/press-key", response_model=ApiResponse)
async def press_session_key(
    session_id: uuid.UUID,
    body: MadoPressKeyRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_service import press_key

    await _ensure_browser_active(session_id, svc)
    result = await _execute_governed(
        session_id,
        svc,
        "mado.action.press_key",
        lambda: press_key(str(session_id), body.key, body.selector),
        detail={"key": body.key, "selector": body.selector},
    )
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/verify", response_model=ApiResponse)
async def verify_session(
    session_id: uuid.UUID,
    body: MadoVerifyRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import verify_page

    await _ensure_browser_active(session_id, svc)
    result = await verify_page(str(session_id), body.model_dump())
    return ApiResponse(success=result["passed"], data=result)


@router.get("/sessions/{session_id}/downloads", response_model=ApiResponse)
async def session_downloads(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_hardening import artifact_service

    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    root = Path(settings.mado_path) / "downloads" / record.profile_name
    data = [
        artifact_service.describe_file(str(session_id), item)
        for item in root.glob("*")
        if item.is_file() and not item.name.endswith(".crdownload")
    ]
    return ApiResponse(data=data)


@router.get("/sessions/{session_id}/artifacts", response_model=ApiResponse)
async def session_artifacts(session_id: uuid.UUID):
    from shogun.services.mado_hardening import artifact_service

    return ApiResponse(data=artifact_service.list(str(session_id)))


@router.get("/runtime", response_model=ApiResponse)
async def mado_runtime():
    from shogun.services.mado_hardening import runtime_registry

    return ApiResponse(data=runtime_registry.list())


@router.get("/profiles", response_model=ApiResponse)
async def mado_profiles():
    from shogun.services.mado_hardening import profile_manager

    return ApiResponse(data=profile_manager.list())


@router.delete("/profiles/{profile_id}", response_model=ApiResponse)
async def delete_mado_profile(profile_id: str):
    from shogun.services.mado_hardening import emit_mado_event, profile_manager
    from shogun.services.mado_service import delete_profile

    profile = next((item for item in profile_manager.list() if item["profile_id"] == profile_id), None)
    if profile and profile["locked"]:
        raise HTTPException(status_code=409, detail="Cannot delete a Mado profile while it is in use.")
    deleted = delete_profile(profile_manager.sanitize(profile_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Mado profile not found")
    await emit_mado_event("mado.profile.released", f"Mado profile deleted: {profile_id}")
    return ApiResponse(data={"deleted": True, "profile_id": profile_id})


@router.post("/kill-switch", response_model=ApiResponse)
async def mado_kill_switch():
    from shogun.services.mado_hardening import kill_all_mado_sessions

    return ApiResponse(data=await kill_all_mado_sessions())


@router.post("/sessions/{session_id}/demo", response_model=ApiResponse)
async def run_mado_demo(
    session_id: uuid.UUID,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    from shogun.services.mado_demo import run_mado_hardening_demo

    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    await _ensure_browser_active(session_id, svc)
    result = await run_mado_hardening_demo(str(session_id), record.profile_name)
    return ApiResponse(success=result["success"], data=result)


@router.post("/sessions/{session_id}/action", response_model=ApiResponse)
async def execute_structured_action(
    session_id: uuid.UUID,
    body: MadoActionRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Structured entrypoint used by Agent Stacks and the Stack Orchestrator."""
    action = body.action.removeprefix("mado.")
    if action in {"open_url", "page.open_url"}:
        return await do_navigate(session_id, MadoNavigateRequest(url=str(body.target or body.value)), svc)
    if action in {"click", "action.click"}:
        return await do_click(session_id, MadoClickRequest(selector=str(body.target)), svc)
    if action in {"type", "action.type"}:
        return await type_in_session(
            session_id,
            {"selector": body.target, "value": body.value, "expected_result": body.metadata.get("verification")},
            svc,
        )
    if action in {"select", "action.select"}:
        return await select_session_option(
            session_id,
            MadoSelectRequest(
                selector=str(body.target), value=str(body.value), expected_result=body.metadata.get("verification")
            ),
            svc,
        )
    if action in {"scroll", "action.scroll"}:
        return await scroll_session_page(
            session_id,
            MadoScrollRequest(delta_x=int(body.metadata.get("delta_x", 0)), delta_y=int(body.value or 600)),
            svc,
        )
    if action in {"fill_form", "action.fill_form"}:
        return await do_fill_form(session_id, MadoFillFormRequest(fields=body.metadata.get("fields", [])), svc)
    if action in {"download", "file.download"}:
        return await do_download(session_id, body.metadata, svc)
    if action in {"upload", "file.upload"}:
        return await do_upload(
            session_id,
            MadoUploadRequest(selector=str(body.target), file_path=str(body.value)),
            svc,
        )
    if action in {"press_key", "action.press_key"}:
        return await press_session_key(session_id, MadoPressKeyRequest(key=str(body.value), selector=body.target), svc)
    if action in {"observe", "page.observe"}:
        return await observe_session(session_id, str(body.metadata.get("mode", "hybrid")), True, svc)
    if action in {"verify", "page.verify"}:
        return await verify_session(
            session_id,
            MadoVerifyRequest(
                verification_type=str(body.metadata.get("verification_type", "no_error_banner")),
                expected=body.metadata.get("expected"),
            ),
            svc,
        )
    raise HTTPException(status_code=400, detail=f"Unsupported structured Mado action: {body.action}")


# ═══════════════════════════════════════════════════════════════
# SCREENSHOTS GALLERY
# ═══════════════════════════════════════════════════════════════


@router.get("/screenshots", response_model=ApiResponse)
async def list_screenshots():
    """List all captured screenshots."""
    from shogun.services.mado_service import list_screenshots as do_list

    screenshots = do_list()
    return ApiResponse(
        data=screenshots,
        meta={"total": len(screenshots)},
    )
