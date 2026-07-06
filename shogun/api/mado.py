"""Mado API routes — browser automation session management and actions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_db, get_mado_session_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.mado import (
    MadoActionResult,
    MadoClickRequest,
    MadoExecuteJsRequest,
    MadoExtractRequest,
    MadoFillFormRequest,
    MadoNavigateRequest,
    MadoScreenshotRequest,
    MadoSecurityPolicy,
    MadoSessionCreate,
    MadoSessionListItem,
    MadoSessionResponse,
    MadoStatusResponse,
    MadoUploadRequest,
    MadoWaitRequest,
    DEFAULT_SECURITY_POLICY,
)
from shogun.services.mado_service_crud import MadoSessionService

router = APIRouter(prefix="/mado", tags=["Mado – Browser Automation"])


# ═══════════════════════════════════════════════════════════════
# STATUS & INSTALL
# ═══════════════════════════════════════════════════════════════


@router.get("/status", response_model=ApiResponse)
async def get_mado_status():
    """Get Mado subsystem status: Chromium installation and active sessions."""
    from shogun.services.mado_service import get_chromium_status, list_screenshots

    status = await get_chromium_status()
    screenshots = list_screenshots()

    return ApiResponse(
        data=MadoStatusResponse(**status),
        meta={"screenshots_count": len(screenshots)},
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
    from shogun.services.posture_guard import (
        check_mado_access,
        check_mado_browser_mode,
        check_mado_session_limit,
        get_posture_tool_filter,
    )

    await check_mado_access()
    await check_mado_session_limit()
    check_mado_browser_mode(body.browser_mode, await get_posture_tool_filter())

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
    from shogun.services.mado_service import close_browser

    # Close the browser if active
    await close_browser(str(session_id))

    success = await svc.delete(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Browser session not found")
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
    from shogun.services.mado_service import _active_contexts, launch_browser

    sid = str(session_id)
    if sid in _active_contexts:
        return  # Already running

    # Fetch session record to get profile and mode
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")

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


@router.post("/sessions/{session_id}/navigate", response_model=ApiResponse)
async def do_navigate(
    session_id: uuid.UUID,
    body: MadoNavigateRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Navigate to a URL in the browser session."""
    from shogun.services.mado_service import navigate
    from shogun.services.posture_guard import check_mado_access
    from shogun.services.mado_policy_guard import check_navigate_policy, increment_page_load_count

    await check_mado_access()
    await _ensure_browser_active(session_id, svc)

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    check_navigate_policy(record, body.url)

    # Domain allowlist comes from the session only (Torii controls on/off, not domains)
    allowlist = record.domain_allowlist or []

    result = await navigate(
        session_id=str(session_id),
        url=body.url,
        wait_until=body.wait_until,
        domain_allowlist=allowlist if allowlist else None,
    )

    if result.get("status") == "blocked":
        raise HTTPException(status_code=403, detail=result.get("reason", "Domain blocked"))

    # Update last URL + increment page load counter
    if result.get("url"):
        await svc.update_status(
            session_id, "active",
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

    result = await extract_content(
        session_id=str(session_id),
        selector=body.selector,
        extract_type=body.extract_type,
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

    result = await screenshot(
        session_id=str(session_id),
        full_page=body.full_page if body else False,
        selector=body.selector if body else None,
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
    from shogun.services.mado_service import fill_form
    from shogun.services.posture_guard import check_mado_access
    from shogun.services.mado_policy_guard import check_form_submit_policy

    await check_mado_access()

    # Per-session policy enforcement
    record = await svc.get_by_id(session_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Browser session not found")
    check_form_submit_policy(record)

    await _ensure_browser_active(session_id, svc)

    result = await fill_form(session_id=str(session_id), fields=body.fields)

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

    result = await click_element(session_id=str(session_id), selector=body.selector)

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/execute-js", response_model=ApiResponse)
async def do_execute_js(
    session_id: uuid.UUID,
    body: MadoExecuteJsRequest,
    svc: MadoSessionService = Depends(get_mado_session_service),
):
    """Execute JavaScript on the current page."""
    from shogun.services.mado_service import execute_js
    from shogun.services.posture_guard import check_mado_access
    from shogun.services.mado_policy_guard import check_js_execution_policy

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

    result = await upload_file(
        session_id=str(session_id),
        selector=body.selector,
        file_path=body.file_path,
    )

    await svc.update_status(session_id, "active", last_active_at=datetime.now(timezone.utc))
    return ApiResponse(data=result)


@router.post("/sessions/{session_id}/download", response_model=ApiResponse)
async def do_download(
    session_id: uuid.UUID,
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
    result = await download_file(
        session_id=str(session_id),
        profile_name=record.profile_name,
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
