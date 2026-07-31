from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from shogun.api.mado import router
from shogun.api.setup import MADO_DEFAULTS
from shogun.services import mado_hardening as hardening
from shogun.services.mado_service import _domain_matches


def _posture(**overrides):
    return {
        "active_tier": "campaign",
        "mado_enabled": True,
        "mado_headless_only": False,
        "mado_downloads_enabled": True,
        "mado_uploads_enabled": True,
        "mado_form_submit_enabled": True,
        "mado_external_urls_enabled": True,
        "kill_switch_active": False,
        **overrides,
    }


def test_setup_contains_safe_reliability_defaults():
    assert MADO_DEFAULTS["require_verification"] is True
    assert MADO_DEFAULTS["allow_external_urls"] is False
    assert MADO_DEFAULTS["allow_authenticated_sessions"] is False
    assert MADO_DEFAULTS["retry"]["max_attempts"] == 3
    assert MADO_DEFAULTS["dialog_policy"]["cookie_banner_policy"] == "accept_necessary_only"
    assert MADO_DEFAULTS["dialog_policy"]["permission_prompt_policy"] == "deny"


def test_domain_allowlist_supports_all_and_subdomain_wildcards():
    assert _domain_matches("anything.example", ["*.*"]) is True
    assert _domain_matches("api.openai.com", ["*.openai.com"]) is True
    assert _domain_matches("openai.com", ["*.openai.com"]) is True
    assert _domain_matches("not-openai.com", ["*.openai.com"]) is False


@pytest.mark.asyncio
async def test_permission_guard_blocks_disabled_posture(monkeypatch):
    async def posture():
        return _posture(mado_enabled=False)

    monkeypatch.setattr("shogun.services.posture_guard.get_posture_tool_filter", posture)
    with pytest.raises(HTTPException) as exc:
        await hardening.permission_guard.check("mado.page.observe")
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_permission_guard_blocks_kill_switch(monkeypatch):
    async def posture():
        return _posture(kill_switch_active=True)

    monkeypatch.setattr("shogun.services.posture_guard.get_posture_tool_filter", posture)
    with pytest.raises(HTTPException):
        await hardening.permission_guard.check("mado.action.click")


@pytest.mark.asyncio
async def test_url_allowlist_and_blocklist(monkeypatch):
    async def posture():
        return _posture(mado_external_urls_enabled=False, mado_allowed_domains=["allowed.example"])

    monkeypatch.setattr("shogun.services.posture_guard.get_posture_tool_filter", posture)
    monkeypatch.setattr(
        hardening,
        "mado_config",
        lambda: {**MADO_DEFAULTS, "blocked_domains": ["blocked.example"]},
    )
    await hardening.permission_guard.check("mado.navigation.open_url", url="https://app.allowed.example/report")
    with pytest.raises(HTTPException):
        await hardening.permission_guard.check("mado.navigation.open_url", url="https://blocked.example")
    with pytest.raises(HTTPException):
        await hardening.permission_guard.check("mado.navigation.open_url", url="https://other.example")


def test_profile_manager_isolates_and_locks_profiles(tmp_path):
    manager = hardening.MadoProfileManager()
    manager.root = tmp_path.resolve()
    path = manager.lock("client_portal", "session-a")
    assert path.parent == tmp_path
    with pytest.raises(HTTPException):
        manager.lock("client_portal", "session-b")
    manager.release("client_portal", "session-a")
    manager.lock("client_portal", "session-b")


def test_profile_name_cannot_escape_root(tmp_path):
    manager = hardening.MadoProfileManager()
    manager.root = tmp_path.resolve()
    path = manager.path_for("../../windows")
    assert path.parent == tmp_path
    assert ".." not in path.name


def test_upload_path_is_restricted(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    approved = workspace / "approved.txt"
    approved.write_text("approved", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(hardening, "PROJECT_ROOT", workspace)
    assert hardening.validate_upload_path(str(approved)) == approved.resolve()
    with pytest.raises(HTTPException):
        hardening.validate_upload_path(str(outside))


def test_secret_redaction_masks_values():
    redacted = hardening._redact({"password": "dont-log-me", "message": "token=abc123", "authorization": "Bearer abc"})
    assert redacted["password"] == "[REDACTED]"
    assert "abc123" not in redacted["message"]
    assert redacted["authorization"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_text_verification_persists_artifact(monkeypatch, tmp_path):
    async def observed(_session_id, **_kwargs):
        return {
            "url": "https://example.test/dashboard",
            "title": "Dashboard",
            "visible_text": "Report generated successfully",
            "errors": [],
            "tables": [],
        }

    monkeypatch.setattr(hardening, "observe_page", observed)
    monkeypatch.setattr(hardening.artifact_service, "root", tmp_path)
    result = await hardening.verify_page(
        "test-session", {"verification_type": "text_contains", "expected": "generated successfully"}
    )
    assert result["passed"] is True
    assert Path(result["artifact"]["path"]).exists()


@pytest.mark.asyncio
async def test_governed_action_retries_and_verifies(monkeypatch):
    calls = 0

    async def allowed(*_args, **_kwargs):
        return _posture()

    async def verified(*_args, **_kwargs):
        return {"passed": True, "status": "passed", "verification_type": "no_error_banner"}

    async def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("stale element")
        return {"status": "ok"}

    monkeypatch.setattr(hardening.permission_guard, "check", allowed)
    monkeypatch.setattr(hardening, "verify_page", verified)
    monkeypatch.setattr(
        hardening,
        "mado_config",
        lambda: {**MADO_DEFAULTS, "retry": {"max_attempts": 2, "backoff_seconds": [0]}},
    )
    result = await hardening.governed_action("retry-test", "mado.action.click", operation)
    assert result["status"] == "ok"
    assert calls == 2
    assert hardening.runtime_registry.get("retry-test").retry_count == 1


def test_order_12_api_surface_is_registered():
    paths = {route.path for route in router.routes}
    required = {
        "/mado/sessions/{session_id}/open-url",
        "/mado/sessions/{session_id}/observe",
        "/mado/sessions/{session_id}/fill-form",
        "/mado/sessions/{session_id}/download",
        "/mado/sessions/{session_id}/upload",
        "/mado/sessions/{session_id}/verify",
        "/mado/sessions/{session_id}/pause",
        "/mado/sessions/{session_id}/resume",
        "/mado/sessions/{session_id}/close",
        "/mado/kill-switch",
    }
    assert required <= paths


@pytest.mark.asyncio
async def test_canonical_demo_end_to_end(monkeypatch, tmp_path):
    from shogun.config import settings
    from shogun.services import mado_service
    from shogun.services.mado_demo import run_mado_hardening_demo

    async def posture():
        return _posture()

    async def no_audit(*_args, **_kwargs):
        return "test-event"

    mado_root = tmp_path / "mado"
    monkeypatch.setattr(settings, "mado_path", mado_root)
    monkeypatch.setattr(hardening.profile_manager, "root", mado_root / "profiles")
    monkeypatch.setattr(hardening.artifact_service, "root", mado_root / "artifacts")
    hardening.profile_manager.root.mkdir(parents=True)
    hardening.artifact_service.root.mkdir(parents=True)
    monkeypatch.setattr("shogun.services.posture_guard.get_posture_tool_filter", posture)
    monkeypatch.setattr(hardening, "emit_mado_event", no_audit)
    monkeypatch.setattr(mado_service, "_emit_browser_event", no_audit)
    monkeypatch.setattr(
        hardening,
        "mado_config",
        lambda: {
            **MADO_DEFAULTS,
            "allow_external_urls": True,
            "allow_persistent_profiles": True,
            "allow_form_submit": "allowed",
            "allow_file_downloads": "allowed",
            "retry": {"max_attempts": 2, "backoff_seconds": [0]},
        },
    )
    session_id = "mado-e2e-demo"
    try:
        launched = await mado_service.launch_browser(session_id, "mado_e2e_demo", "headless")
        assert launched["status"] == "launched"
        result = await run_mado_hardening_demo(session_id, "mado_e2e_demo")
        assert result["success"] is True
        assert result["screenshot"]["status"] == "ok"
        downloaded = list((mado_root / "downloads" / "mado_e2e_demo").glob("mado_demo_report*.csv"))
        assert downloaded and downloaded[0].stat().st_size > 0
    finally:
        await mado_service.close_browser(session_id)
