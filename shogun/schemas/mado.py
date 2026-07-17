"""Mado schemas — request/response models for browser automation API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from shogun.schemas.common import ShogunBase

# ═══════════════════════════════════════════════════════════════
# SECURITY POLICY
# ═══════════════════════════════════════════════════════════════


DEFAULT_SECURITY_POLICY = {
    "https_only": False,
    "downloads": "allowed",
    "uploads": "allowed",
    "form_submit": "allowed",
    "external_navigation": "allowed",
    "js_execution": "allowed",
    "max_page_loads": 0,
}


class MadoSecurityPolicy(ShogunBase):
    """Per-session security policy for Mado browser sessions."""

    https_only: bool = Field(False, description="Block non-HTTPS navigation")
    downloads: Literal["allowed", "blocked", "approval_required"] = Field("allowed", description="Download policy")
    uploads: Literal["allowed", "blocked", "approval_required"] = Field("allowed", description="Upload policy")
    form_submit: Literal["allowed", "blocked", "approval_required"] = Field(
        "allowed", description="Form submission policy"
    )
    external_navigation: Literal["allowed", "blocked"] = Field(
        "allowed", description="Block navigation outside domain allowlist"
    )
    js_execution: Literal["allowed", "blocked"] = Field("allowed", description="JavaScript execution policy")
    max_page_loads: int = Field(0, ge=0, description="Max navigations per session lifetime (0 = unlimited)")


# ═══════════════════════════════════════════════════════════════
# SESSION SCHEMAS
# ═══════════════════════════════════════════════════════════════


class MadoSessionCreate(ShogunBase):
    """Request body for creating a new browser session."""

    name: str = Field(..., min_length=1, max_length=255, description="Display name for the session")
    profile_name: str = Field(..., min_length=1, max_length=255, description="Unique filesystem profile name")
    agent_id: uuid.UUID | None = Field(None, description="Optional Samurai agent to link")
    browser_mode: str = Field("headless", description="Browser mode: 'headless' or 'visible'")
    domain_allowlist: list[str] = Field(default_factory=list, description="Allowed domains for this session")
    security_policy: MadoSecurityPolicy | None = Field(None, description="Per-session security policy")
    stack_run_id: uuid.UUID | None = None
    step_run_id: uuid.UUID | None = None
    persistent_profile: bool = True
    authenticated_session: bool = False


class MadoSessionResponse(ShogunBase):
    """Response model for a browser session."""

    id: uuid.UUID
    name: str
    profile_name: str
    agent_id: uuid.UUID | None = None
    status: str
    browser_mode: str
    last_url: str | None = None
    domain_allowlist: list[str] = Field(default_factory=list)
    session_data: dict[str, Any] = Field(default_factory=dict)
    security_policy: dict[str, Any] = Field(default_factory=lambda: DEFAULT_SECURITY_POLICY.copy())
    last_active_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MadoSessionListItem(ShogunBase):
    """Lightweight session list item."""

    id: uuid.UUID
    name: str
    profile_name: str
    agent_id: uuid.UUID | None = None
    status: str
    browser_mode: str
    last_url: str | None = None
    domain_allowlist: list[str] = Field(default_factory=list)
    security_policy: dict[str, Any] = Field(default_factory=lambda: DEFAULT_SECURITY_POLICY.copy())
    session_data: dict[str, Any] = Field(default_factory=dict)
    last_active_at: datetime | None = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
# ACTION SCHEMAS
# ═══════════════════════════════════════════════════════════════


class MadoNavigateRequest(ShogunBase):
    """Navigate to a URL."""

    url: str = Field(..., description="URL to navigate to")
    wait_until: str = Field("domcontentloaded", description="Wait strategy: 'load', 'domcontentloaded', 'networkidle'")


class MadoExtractRequest(ShogunBase):
    """Extract content from the page."""

    selector: str | None = Field(None, description="CSS selector (None for entire body)")
    extract_type: str = Field("text", description="'text', 'html', 'inner_text'")


class MadoScreenshotRequest(ShogunBase):
    """Capture a screenshot."""

    full_page: bool = Field(False, description="Capture full page or just viewport")
    selector: str | None = Field(None, description="CSS selector for element screenshot")


class MadoFillFormRequest(ShogunBase):
    """Fill form fields."""

    fields: list[dict[str, str]] = Field(
        ...,
        description="List of {selector, value, type?} dicts",
    )


class MadoClickRequest(ShogunBase):
    """Click an element."""

    selector: str = Field(..., description="CSS selector of element to click")
    expected_result: dict[str, Any] | None = None


class MadoSelectRequest(ShogunBase):
    selector: str
    value: str
    expected_result: dict[str, Any] | None = None


class MadoScrollRequest(ShogunBase):
    delta_x: int = 0
    delta_y: int = 600


class MadoPressKeyRequest(ShogunBase):
    key: str
    selector: str | None = None


class MadoVerifyRequest(ShogunBase):
    verification_type: str
    expected: Any = None


class MadoActionRequest(ShogunBase):
    action: str
    target: str | None = None
    value: Any = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MadoExecuteJsRequest(ShogunBase):
    """Execute JavaScript."""

    script: str = Field(..., description="JavaScript code to execute on the page")


class MadoUploadRequest(ShogunBase):
    """Upload a file to a form input."""

    selector: str = Field(..., description="CSS selector of file input")
    file_path: str = Field(..., description="Path to file to upload")


class MadoWaitRequest(ShogunBase):
    """Wait for a selector to appear."""

    selector: str = Field(..., description="CSS selector to wait for")
    timeout: int = Field(10000, description="Timeout in milliseconds")
    state: str = Field("visible", description="'visible', 'attached', 'detached', 'hidden'")


# ═══════════════════════════════════════════════════════════════
# STATUS SCHEMAS
# ═══════════════════════════════════════════════════════════════


class MadoStatusResponse(ShogunBase):
    """Mado subsystem status."""

    installed: bool
    version: str | None = None
    active_sessions: int = 0
    mado_path: str
    profiles_path: str
    screenshots_path: str
    downloads_path: str


class MadoActionResult(ShogunBase):
    """Generic action result wrapper."""

    status: str
    url: str | None = None
    title: str | None = None
    content: str | None = None
    path: str | None = None
    filename: str | None = None
    error: str | None = None
    detail: dict[str, Any] | None = None
