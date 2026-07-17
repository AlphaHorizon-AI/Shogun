from __future__ import annotations

import pytest
from fastapi import HTTPException

from shogun.api import ronin as ronin_api
from shogun.api import security as security_api
from shogun.api import setup as setup_api
from shogun.api.ronin import router as ronin_router
from shogun.api.security import TIER_CONSTRAINTS
from shogun.api.setup import RONIN_DESKTOP_DEFAULTS
from shogun.ronin.core.desktop_permission_engine import DesktopPermissionEngine
from shogun.ronin.desktop.dialog_service import DesktopDialogService
from shogun.ronin.desktop.recovery_service import DesktopRecoveryService
from shogun.ronin.desktop.verification_service import DesktopVerificationService
from shogun.ronin.policies.ronin_policy_schema import RoninAction


def permissions(**overrides):
    result = {
        "active_tier": "ronin",
        "ronin_enabled": True,
        "ronin_screenshots_enabled": True,
        "ronin_mouse_enabled": True,
        "ronin_keyboard_enabled": True,
        "ronin_window_management_enabled": True,
        "ronin_native_apps_enabled": True,
        "ronin_require_high_risk_approval": True,
        "ronin_block_critical_actions": True,
        "kill_switch_active": False,
    }
    result.update(overrides)
    return result


def action(action_type: str, **kwargs):
    return RoninAction(agent_id="test", action_type=action_type, **kwargs)


def test_ronin_tier_does_not_silently_enable_desktop_control():
    assert TIER_CONSTRAINTS["ronin"]["ronin_enabled"] is False
    assert TIER_CONSTRAINTS["ronin"]["ronin_posture"] == "disabled"


def test_setup_defaults_are_safe_and_complete():
    assert RONIN_DESKTOP_DEFAULTS["enabled"] is False
    assert RONIN_DESKTOP_DEFAULTS["minimum_posture"] == "ronin"
    assert RONIN_DESKTOP_DEFAULTS["verification_required"] is True
    assert RONIN_DESKTOP_DEFAULTS["critical_actions_blocked"] is True
    assert RONIN_DESKTOP_DEFAULTS["protected_applications"]


def test_order_11_desktop_api_surface_is_registered():
    paths = {route.path for route in ronin_router.routes}
    assert {
        "/ronin/desktop/status",
        "/ronin/desktop/enable",
        "/ronin/desktop/disable",
        "/ronin/desktop/screenshot",
        "/ronin/desktop/state",
        "/ronin/desktop/windows",
        "/ronin/desktop/click",
        "/ronin/desktop/type",
        "/ronin/desktop/hotkey",
        "/ronin/desktop/scroll",
        "/ronin/desktop/drag",
        "/ronin/desktop/focus-window",
        "/ronin/desktop/open-application",
        "/ronin/desktop/verify",
        "/ronin/desktop/wait-for-window",
        "/ronin/desktop/wait-for-file",
        "/ronin/desktop/kill-switch",
        "/ronin/desktop/demo/word-hello-world",
    } <= paths


@pytest.mark.asyncio
async def test_explicit_enable_and_disable_lifecycle(monkeypatch):
    state = {**permissions(ronin_enabled=False), "ronin_posture": "disabled"}

    async def get_posture():
        return dict(state)

    async def save_posture(updated):
        state.clear()
        state.update(updated)

    monkeypatch.setattr(security_api, "_get_agent_posture", get_posture)
    monkeypatch.setattr(security_api, "_save_agent_posture", save_posture)
    monkeypatch.setattr(setup_api, "_read_setup", lambda: {"ronin_desktop_control": dict(RONIN_DESKTOP_DEFAULTS)})
    monkeypatch.setattr(setup_api, "_write_setup", lambda _setup: None)
    monkeypatch.setattr("shogun.ronin.core.komainu.start_komainu", lambda level=1: True)
    monkeypatch.setattr("shogun.ronin.core.komainu.stop_komainu", lambda: None)
    monkeypatch.setattr(
        "shogun.ronin.core.audit_logger.RoninAuditLogger.log_action", lambda **_kwargs: _completed_string()
    )

    with pytest.raises(HTTPException):
        await ronin_api.enable_desktop_control({"confirmation": "wrong"})

    enabled = await ronin_api.enable_desktop_control({"confirmation": "ENABLE RONIN DESKTOP CONTROL"})
    assert enabled.data["active"] is True
    assert state["ronin_posture"] == "desktop_full"
    assert state["ronin_require_verification"] is True

    disabled = await ronin_api.disable_desktop_control()
    assert disabled.data["active"] is False
    assert state["ronin_enabled"] is False


async def _completed_string():
    return "event-id"


def test_desktop_is_blocked_below_ronin_even_if_flag_is_stale():
    decision = DesktopPermissionEngine().evaluate(action("desktop.screenshot"), permissions(active_tier="campaign"))
    assert decision.allowed is False
    assert "Ronin posture" in decision.reason


def test_desktop_is_blocked_until_explicitly_enabled():
    decision = DesktopPermissionEngine().evaluate(action("desktop.screenshot"), permissions(ronin_enabled=False))
    assert decision.allowed is False
    assert "explicitly disabled" in decision.reason


def test_individual_mouse_permission_is_enforced():
    decision = DesktopPermissionEngine().evaluate(
        action("desktop.click", metadata={"x": 10, "y": 20}),
        permissions(ronin_mouse_enabled=False),
    )
    assert decision.allowed is False
    assert "ronin_mouse_enabled" in decision.reason


def test_protected_window_context_is_hard_blocked():
    decision = DesktopPermissionEngine().evaluate(
        action("desktop.type", value="hello"),
        permissions(),
        active_window={"title": "Windows Security - Enter password", "process": "credentialui.exe"},
    )
    assert decision.allowed is False
    assert decision.protected_context is True
    assert decision.risk_tier == "critical"


def test_secret_shaped_keyboard_input_is_blocked():
    decision = DesktopPermissionEngine().evaluate(
        action("desktop.type", value="api_key=do-not-type-this"), permissions()
    )
    assert decision.allowed is False
    assert decision.protected_context is True


def test_high_risk_application_launch_requires_approval():
    decision = DesktopPermissionEngine().evaluate(action("os.app_launch", target="notepad.exe"), permissions())
    assert decision.allowed is False
    assert decision.approval_required is True


def test_kill_switch_blocks_every_desktop_action():
    decision = DesktopPermissionEngine().evaluate(action("desktop.screenshot"), permissions(kill_switch_active=True))
    assert decision.allowed is False
    assert "kill switch" in decision.reason


@pytest.mark.asyncio
async def test_file_verification_and_dynamic_wait(tmp_path):
    target = tmp_path / "hello_world.docx"
    target.write_text("Hello World", encoding="utf-8")
    verifier = DesktopVerificationService()
    verified = await verifier.verify("desktop.verify", {}, {}, {}, {"file_exists": str(target)})
    waited = await verifier.wait_for_file(str(target), timeout=0.1, interval=0.01)
    assert verified.passed is True
    assert waited.passed is True


def test_recovery_retries_then_pauses_safely():
    recovery = DesktopRecoveryService()
    assert recovery.decide(attempt=0, max_retries=2, error="missed").retry is True
    exhausted = recovery.decide(attempt=2, max_retries=2, error="missed")
    assert exhausted.retry is False
    assert exhausted.pause is True
    unknown = recovery.decide(attempt=0, max_retries=2, error=None, unknown_dialog=True)
    assert unknown.pause is True


def test_dialog_classifier_handles_save_as_but_pauses_unknown_and_protected():
    classifier = DesktopDialogService()
    assert classifier.classify({"title": "Save As"}).safe_to_handle is True
    assert classifier.classify({"title": "Unexpected warning dialog"}).safe_to_handle is False
    protected = classifier.classify({"title": "Windows Security - Password"})
    assert protected.detected is True
    assert protected.kind == "protected"
