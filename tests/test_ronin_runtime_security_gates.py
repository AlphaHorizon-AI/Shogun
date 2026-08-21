from __future__ import annotations

import asyncio
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from shogun.api import ronin as ronin_api
from shogun.api import security as security_api
from shogun.ronin.core import capabilities_registry
from shogun.ronin.core.action_router import route_action
from shogun.ronin.core.approval_gate import (
    action_digest,
    action_preview,
    get_pending,
    request_approval,
    respond_to_approval,
)
from shogun.ronin.core.desktop_permission_engine import DesktopPermissionDecision
from shogun.ronin.core.posture_guard import evaluate
from shogun.ronin.core.ronin_controller import RoninController
from shogun.ronin.policies.ronin_policy_schema import (
    AppTrustLevel,
    EnvironmentInfo,
    PostureDecision,
    RiskLevel,
    RoninAction,
    RoninActionStatus,
    RoninCapability,
    RoninPermissionGate,
    RoninPostureLevel,
    RoninResult,
)
from shogun.schemas.ronin import RoninApprovalRequest
from shogun.schemas.security import SecurityPostureResponse


def permissions(**overrides):
    result = {
        "active_tier": "ronin",
        "kill_switch_active": False,
        "ronin_enabled": True,
        "ronin_posture": "desktop_full",
        "ronin_screenshots_enabled": True,
        "ronin_mouse_enabled": True,
        "ronin_keyboard_enabled": True,
        "ronin_window_management_enabled": True,
        "ronin_native_apps_enabled": True,
        "ronin_require_verification": False,
        "ronin_require_high_risk_approval": True,
        "ronin_block_critical_actions": True,
        "ronin_admin_escalation": False,
        "ronin_credential_entry": "blocked",
        "ronin_file_deletion": "approval_required",
        "ronin_external_uploads": "approval_required",
        "ronin_install_software": "approval_required",
    }
    result.update(overrides)
    return result


def guard(
    *,
    action_type: str = "desktop.scroll",
    risk: str = "low",
    gates: tuple[RoninPermissionGate | str, ...] = (),
    posture: dict | None = None,
    requires_approval: bool = False,
    trust: AppTrustLevel = AppTrustLevel.RESTRICTED,
    posture_minimum: str = "desktop_limited",
    trust_minimum: str = "restricted",
) -> PostureDecision:
    return evaluate(
        action_type=action_type,
        agent_id="test",
        current_posture="desktop_full",
        posture_permissions=posture or permissions(),
        app_trust_level=trust,
        capability_posture_min=posture_minimum,
        capability_trust_min=trust_minimum,
        capability_risk=risk,
        capability_requires_approval=requires_approval,
        capability_permission_gates=gates,
    )


def test_unrelated_tri_state_gates_do_not_apply_to_safe_action():
    decision = guard()
    assert decision.allowed is True
    assert decision.approval_required is False


@pytest.mark.parametrize(
    ("gate", "permission_key"),
    [
        (RoninPermissionGate.CREDENTIAL_ENTRY, "ronin_credential_entry"),
        (RoninPermissionGate.FILE_DELETION, "ronin_file_deletion"),
        (RoninPermissionGate.EXTERNAL_UPLOADS, "ronin_external_uploads"),
        (RoninPermissionGate.INSTALL_SOFTWARE, "ronin_install_software"),
    ],
)
def test_action_specific_blocked_decisions_are_hard_denials(gate, permission_key):
    decision = guard(gates=(gate,), posture=permissions(**{permission_key: "blocked"}))
    assert decision.allowed is False
    assert decision.approval_required is False
    assert permission_key in decision.reason


@pytest.mark.parametrize(
    "gate",
    [
        RoninPermissionGate.FILE_DELETION,
        RoninPermissionGate.EXTERNAL_UPLOADS,
        RoninPermissionGate.INSTALL_SOFTWARE,
    ],
)
def test_mutating_semantic_gates_require_approval_in_builtin_policy(gate):
    decision = guard(gates=(gate,))
    assert decision.allowed is False
    assert decision.approval_required is True
    assert gate.value in decision.reason


def test_admin_escalation_is_enforced_as_hard_boolean_gate():
    blocked = guard(gates=(RoninPermissionGate.ADMIN_ESCALATION,))
    assert blocked.allowed is False
    assert blocked.approval_required is False
    assert "administrator escalation is disabled" in blocked.reason

    allowed = guard(
        gates=(RoninPermissionGate.ADMIN_ESCALATION,),
        posture=permissions(ronin_admin_escalation=True),
    )
    assert allowed.allowed is True


def test_invalid_tri_state_and_unknown_gate_fail_closed():
    invalid = guard(
        gates=(RoninPermissionGate.FILE_DELETION,),
        posture=permissions(ronin_file_deletion="sometimes"),
    )
    assert invalid.allowed is False
    assert invalid.risk_level == RiskLevel.CRITICAL

    unknown = guard(gates=("not_registered",))
    assert unknown.allowed is False
    assert unknown.risk_level == RiskLevel.CRITICAL


def test_invalid_capability_posture_and_trust_metadata_fail_closed():
    invalid_posture = guard(posture_minimum="unlimited")
    assert invalid_posture.allowed is False
    assert invalid_posture.risk_level == RiskLevel.CRITICAL

    invalid_trust = guard(trust_minimum="anything_goes")
    assert invalid_trust.allowed is False
    assert invalid_trust.risk_level == RiskLevel.CRITICAL


def test_high_risk_and_critical_controls_remain_non_bypassable():
    high = guard(risk="high", posture=permissions(ronin_require_high_risk_approval=True))
    assert high.approval_required is True

    critical = guard(
        risk="critical",
        posture=permissions(ronin_block_critical_actions=True),
        requires_approval=True,
    )
    assert critical.allowed is False
    assert critical.approval_required is False
    assert "blocked by policy" in critical.reason


def test_forbidden_app_and_kill_switch_remain_hard_blocks():
    forbidden = guard(trust=AppTrustLevel.FORBIDDEN)
    assert forbidden.allowed is False
    assert forbidden.approval_required is False

    killed = guard(posture=permissions(kill_switch_active=True))
    assert killed.allowed is False
    assert killed.approval_required is False
    assert "kill switch" in killed.reason


def test_capability_and_conservative_action_mapping_are_action_specific():
    click = capabilities_registry.get_capability("desktop.click")
    assert click is not None
    assert click.risk_level == RiskLevel.HIGH
    assert click.requires_approval is True

    assert capabilities_registry.resolve_permission_gates(
        RoninAction(agent_id="test", action_type="desktop.click", target="Save")
    ) == ()
    assert RoninPermissionGate.CREDENTIAL_ENTRY in capabilities_registry.resolve_permission_gates(
        RoninAction(agent_id="test", action_type="desktop.type", target="Password field", value="hidden")
    )
    assert RoninPermissionGate.FILE_DELETION in capabilities_registry.resolve_permission_gates(
        RoninAction(
            agent_id="test",
            action_type="desktop.hotkey",
            value="shift+delete",
            reason="Delete selected file",
        )
    )
    assert RoninPermissionGate.INSTALL_SOFTWARE in capabilities_registry.resolve_permission_gates(
        RoninAction(agent_id="test", action_type="os.app_launch", target="msiexec.exe")
    )
    assert RoninPermissionGate.ADMIN_ESCALATION in capabilities_registry.resolve_permission_gates(
        RoninAction(
            agent_id="test",
            action_type="os.app_launch",
            target="powershell.exe",
            metadata={"run_as_admin": True},
        )
    )


def test_registered_capability_can_declare_trusted_semantic_gate():
    name = "filesystem.delete"
    capability = RoninCapability(
        name=name,
        category="os",
        risk_level=RiskLevel.HIGH,
        posture_minimum=RoninPostureLevel.DESKTOP_FULL,
        app_trust_minimum=AppTrustLevel.RESTRICTED,
        permission_gates=[RoninPermissionGate.FILE_DELETION],
    )
    capabilities_registry.register_capability(capability)
    try:
        gates = capabilities_registry.resolve_permission_gates(
            RoninAction(agent_id="test", action_type=name)
        )
        assert gates == (RoninPermissionGate.FILE_DELETION,)
    finally:
        capabilities_registry.unregister_capability(name)


def test_approval_payload_is_digest_bound_and_secret_aware():
    action = RoninAction(
        agent_id="test",
        action_type="desktop.type",
        target="Password field",
        value="super-secret",
        metadata={"field_name": "password", "trace_id": "trace-1"},
    )
    digest = action_digest(action)
    preview = action_preview(action, (RoninPermissionGate.CREDENTIAL_ENTRY,))
    assert len(digest) == 64
    assert "super-secret" not in str(preview)
    assert preview["value"] == "[REDACTED TEXT INPUT: 12 characters]"
    assert preview["permission_gates"] == ["credential_entry"]
    action.value = "changed"
    assert action_digest(action) != digest


def test_approval_decisions_and_posture_tri_states_are_typed():
    assert RoninApprovalRequest(decision="approved").decision == "approved"
    with pytest.raises(ValidationError):
        RoninApprovalRequest(decision="maybe")
    assert respond_to_approval("missing", "maybe") is False  # type: ignore[arg-type]

    payload = {**security_api._DEFAULT_POSTURE, "ronin_file_deletion": "invalid"}
    with pytest.raises(ValidationError):
        SecurityPostureResponse(**payload)
    stored = security_api._validated_stored_posture(
        {"ronin_enabled": "false", "ronin_file_deletion": "invalid", "ronin_admin_escalation": False}
    )
    assert "ronin_enabled" not in stored
    assert "ronin_file_deletion" not in stored
    assert stored["ronin_admin_escalation"] is False


@pytest.mark.asyncio
async def test_approval_is_first_decision_wins_and_target_is_redacted():
    waiting = asyncio.create_task(
        request_approval(
            action_type="desktop.type",
            target="password=do-not-expose",
            timeout_seconds=1,
        )
    )
    for _ in range(20):
        pending = get_pending()
        if pending:
            break
        await asyncio.sleep(0)
    assert pending
    approval_id = pending[0]["id"]
    assert "do-not-expose" not in (pending[0]["target"] or "")
    assert respond_to_approval(approval_id, "denied") is True
    assert respond_to_approval(approval_id, "approved") is False
    completed = await waiting
    assert completed.status == "denied"


def test_window_handle_is_part_of_approval_security_snapshot():
    controller = configured_controller()
    capability = capabilities_registry.get_capability("desktop.click")
    assert capability is not None
    action = RoninAction(agent_id="test", action_type="desktop.click", target="Save")
    common = {
        "action": action,
        "capability": capability,
        "posture_permissions": permissions(),
        "current_app": "explorer.exe",
        "app_trust_level": AppTrustLevel.RESTRICTED,
    }
    first = controller._security_snapshot(
        **common,
        active_window={"process": "explorer.exe", "title": "Documents", "hwnd": 100},
    )
    second = controller._security_snapshot(
        **common,
        active_window={"process": "explorer.exe", "title": "Documents", "hwnd": 200},
    )
    assert first != second


class FakeObserver:
    def __init__(self):
        self.paused_reason: str | None = None

    async def capture_state(self, **_kwargs):
        return {}

    def record(self, *_args, **_kwargs):
        return None

    def resume(self):
        return None

    def pause(self, reason):
        self.paused_reason = reason

    def set_next_action(self, *_args):
        return None

    def set_retry_count(self, *_args):
        return None


async def noop_async(*_args, **_kwargs):
    return "event-id"


def configured_controller() -> RoninController:
    controller = RoninController()
    controller._initialized = True
    controller._environment = EnvironmentInfo()
    return controller


def install_controller_fakes(monkeypatch, observer: FakeObserver, route_calls: list[RoninAction]):
    monkeypatch.setattr("shogun.ronin.core.ronin_controller.komainu_is_paused", lambda: False)
    monkeypatch.setattr("shogun.ronin.core.audit_logger.RoninAuditLogger.log_action", noop_async)
    monkeypatch.setattr("shogun.ronin.core.audit_logger.RoninAuditLogger.log_action_blocked", noop_async)
    monkeypatch.setattr("shogun.ronin.desktop.observation_service.get_observer", lambda: observer)
    monkeypatch.setattr("shogun.ronin.desktop.screenshot_controller.take_screenshot_raw", noop_async)

    async def route(action):
        route_calls.append(action)
        return RoninResult(status=RoninActionStatus.SUCCESS, action_type=action.action_type)

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.route_action", route)

    async def publish(*_args, **_kwargs):
        return None

    monkeypatch.setattr("shogun.ronin.telemetry.gensui_publisher.publish_action", publish)


@pytest.mark.asyncio
async def test_unknown_capability_is_rejected_before_router(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)
    result = await controller.execute(
        RoninAction(agent_id="test", action_type="desktop.unregistered", risk_level=RiskLevel.LOW)
    )
    assert result.status == RoninActionStatus.BLOCKED
    assert "Unknown or disabled" in (result.error or "")
    assert route_calls == []


@pytest.mark.asyncio
async def test_controller_uses_registry_risk_and_binds_approved_action(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)
    stable = permissions()

    async def context(_action):
        return dict(stable), "explorer.exe", AppTrustLevel.RESTRICTED, {
            "title": "Documents",
            "process": "explorer.exe",
        }

    monkeypatch.setattr(controller, "_collect_security_context", context)
    captured = {}

    async def approve(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status="approved", id="apr-test", action_digest=kwargs["action_digest"])

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.request_approval", approve)
    result = await controller.execute(
        RoninAction(
            agent_id="test",
            action_type="desktop.click",
            target="Save",
            risk_level=RiskLevel.LOW,
            metadata={"x": 10, "y": 20},
        )
    )
    assert result.status == RoninActionStatus.SUCCESS
    assert captured["risk_level"] == "high"
    assert captured["action_preview"]["action_type"] == "desktop.click"
    assert len(captured["action_digest"]) == 64
    assert len(route_calls) == 1


@pytest.mark.asyncio
async def test_action_mutation_while_approval_waits_is_denied(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)

    async def context(_action):
        return permissions(), "notepad.exe", AppTrustLevel.RESTRICTED, {
            "title": "Notes",
            "process": "notepad.exe",
        }

    monkeypatch.setattr(controller, "_collect_security_context", context)
    action = RoninAction(agent_id="test", action_type="desktop.type", target="Editor", value="original")

    async def mutate_then_approve(**kwargs):
        action.value = "mutated"
        return SimpleNamespace(status="approved", id="apr-mutated", action_digest=kwargs["action_digest"])

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.request_approval", mutate_then_approve)
    result = await controller.execute(action)
    assert result.status == RoninActionStatus.BLOCKED
    assert "changed while approval was pending" in (result.error or "")
    assert route_calls == []


@pytest.mark.asyncio
async def test_pre_route_recheck_blocks_toctou_posture_change(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)
    calls = 0

    async def context(_action):
        nonlocal calls
        calls += 1
        live = permissions(kill_switch_active=calls >= 3)
        return live, "explorer.exe", AppTrustLevel.RESTRICTED, {
            "title": "Documents",
            "process": "explorer.exe",
        }

    monkeypatch.setattr(controller, "_collect_security_context", context)

    async def approve(**kwargs):
        return SimpleNamespace(status="approved", id="apr-toctou", action_digest=kwargs["action_digest"])

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.request_approval", approve)
    result = await controller.execute(
        RoninAction(agent_id="test", action_type="desktop.click", target="Save", metadata={"x": 1, "y": 1})
    )
    assert calls >= 3
    assert result.status == RoninActionStatus.BLOCKED
    assert "changed after approval" in (result.error or "")
    assert route_calls == []


@pytest.mark.asyncio
async def test_pre_route_recheck_invalidates_same_title_different_window(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)
    calls = 0

    async def context(_action):
        nonlocal calls
        calls += 1
        return permissions(), "explorer.exe", AppTrustLevel.RESTRICTED, {
            "title": "Documents",
            "process": "explorer.exe",
            "hwnd": 100 if calls < 3 else 200,
        }

    monkeypatch.setattr(controller, "_collect_security_context", context)

    async def approve(**kwargs):
        return SimpleNamespace(status="approved", id="apr-window", action_digest=kwargs["action_digest"])

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.request_approval", approve)
    result = await controller.execute(
        RoninAction(agent_id="test", action_type="desktop.click", target="Save", metadata={"x": 1, "y": 1})
    )
    assert result.status == RoninActionStatus.BLOCKED
    assert "changed after approval" in (result.error or "")
    assert route_calls == []


@pytest.mark.asyncio
async def test_denied_approval_cannot_be_replayed_to_execute(monkeypatch):
    controller = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, FakeObserver(), route_calls)

    async def context(_action):
        return permissions(), "explorer.exe", AppTrustLevel.RESTRICTED, {
            "title": "Documents",
            "process": "explorer.exe",
            "hwnd": 100,
        }

    monkeypatch.setattr(controller, "_collect_security_context", context)

    async def deny_then_replay(**kwargs):
        async def responder():
            for _ in range(20):
                pending = get_pending()
                if pending:
                    approval_id = pending[0]["id"]
                    assert respond_to_approval(approval_id, "denied") is True
                    assert respond_to_approval(approval_id, "approved") is False
                    return
                await asyncio.sleep(0)
            raise AssertionError("approval request was not queued")

        responder_task = asyncio.create_task(responder())
        completed = await request_approval(**kwargs, timeout_seconds=1)
        await responder_task
        return completed

    monkeypatch.setattr("shogun.ronin.core.ronin_controller.request_approval", deny_then_replay)
    result = await controller.execute(
        RoninAction(agent_id="test", action_type="desktop.click", target="Save", metadata={"x": 1, "y": 1})
    )
    assert result.status == RoninActionStatus.APPROVAL_REQUIRED
    assert "denied" in (result.error or "")
    assert route_calls == []


def test_desktop_and_posture_decisions_combine_with_deny_precedence(monkeypatch):
    controller = configured_controller()
    screenshot = capabilities_registry.get_capability("desktop.screenshot")
    assert screenshot is not None

    class ApprovalEngine:
        def evaluate(self, *_args, **_kwargs):
            return DesktopPermissionDecision(False, "desktop approval", "high", approval_required=True)

    monkeypatch.setattr(
        "shogun.ronin.core.desktop_permission_engine.get_desktop_permission_engine",
        lambda: ApprovalEngine(),
    )
    approval, _ = controller._evaluate_security_context(
        RoninAction(agent_id="test", action_type="desktop.screenshot"),
        screenshot,
        permissions(),
        AppTrustLevel.TRUSTED,
        {"title": "Desktop", "process": "explorer.exe"},
    )
    assert approval.approval_required is True

    click = capabilities_registry.get_capability("desktop.click")
    assert click is not None

    class DenyEngine:
        def evaluate(self, *_args, **_kwargs):
            return DesktopPermissionDecision(False, "hard desktop denial", "critical")

    monkeypatch.setattr(
        "shogun.ronin.core.desktop_permission_engine.get_desktop_permission_engine",
        lambda: DenyEngine(),
    )
    denied, _ = controller._evaluate_security_context(
        RoninAction(agent_id="test", action_type="desktop.click"),
        click,
        permissions(),
        AppTrustLevel.RESTRICTED,
        {"title": "Desktop", "process": "explorer.exe"},
    )
    assert denied.allowed is False
    assert denied.approval_required is False
    assert denied.reason == "hard desktop denial"


@pytest.mark.asyncio
async def test_enable_cannot_reset_kill_switch_or_weaken_fixed_gates(monkeypatch):
    state = permissions(kill_switch_active=True, ronin_enabled=False, ronin_posture="disabled")

    async def get_posture():
        return dict(state)

    async def save_posture(updated):
        state.clear()
        state.update(updated)

    monkeypatch.setattr(security_api, "_get_agent_posture", get_posture)
    monkeypatch.setattr(security_api, "_save_agent_posture", save_posture)
    monkeypatch.setattr(ronin_api.settings, "deployment_mode", "desktop")
    with pytest.raises(Exception) as killed:
        await ronin_api.enable_desktop_control({"confirmation": "ENABLE RONIN DESKTOP CONTROL"})
    assert getattr(killed.value, "status_code", None) == 409
    assert state["kill_switch_active"] is True

    state["kill_switch_active"] = False
    with pytest.raises(Exception) as weakened:
        await ronin_api.enable_desktop_control(
            {
                "confirmation": "ENABLE RONIN DESKTOP CONTROL",
                "ronin_require_high_risk_approval": False,
            }
        )
    assert getattr(weakened.value, "status_code", None) == 422
    assert state["ronin_enabled"] is False


@pytest.mark.asyncio
async def test_harakiri_persists_fail_closed_gate_for_new_controller(monkeypatch):
    state = permissions(ronin_enabled=True, ronin_posture="desktop_full")
    setup_state = {"ronin_desktop_control": {"enabled": True}}
    observer = FakeObserver()

    async def get_posture():
        return dict(state)

    async def save_posture(updated):
        state.clear()
        state.update(updated)

    monkeypatch.setattr(security_api, "_get_agent_posture", get_posture)
    monkeypatch.setattr(security_api, "_save_agent_posture", save_posture)
    monkeypatch.setattr("shogun.api.setup._read_setup", lambda: dict(setup_state))

    def write_setup(updated):
        setup_state.clear()
        setup_state.update(updated)

    monkeypatch.setattr("shogun.api.setup._write_setup", write_setup)
    monkeypatch.setattr("shogun.ronin.desktop.observation_service.get_observer", lambda: observer)
    monkeypatch.setattr("shogun.ronin.core.approval_gate.cancel_all", lambda _reason: 0)
    monkeypatch.setattr("shogun.ronin.core.audit_logger.RoninAuditLogger.log_action", noop_async)
    monkeypatch.setattr("shogun.ronin.core.audit_logger.RoninAuditLogger.log_harakiri", noop_async)
    monkeypatch.setattr("shogun.ronin.core.audit_logger.RoninAuditLogger.log_action_blocked", noop_async)

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def execute(self, _statement):
            return None

        async def commit(self):
            return None

    db_engine_module = importlib.import_module("shogun.db.engine")
    monkeypatch.setattr(db_engine_module, "async_session_factory", lambda: Session())
    response = await ronin_api.ronin_harakiri()
    assert response.data["kill_switch_active"] is True
    assert state["kill_switch_active"] is True
    assert state["ronin_enabled"] is False
    assert setup_state["ronin_desktop_control"]["enabled"] is False
    assert observer.paused_reason

    # Simulate a process restart: a fresh controller reads the persisted state.
    restarted = configured_controller()
    route_calls: list[RoninAction] = []
    install_controller_fakes(monkeypatch, observer, route_calls)
    monkeypatch.setattr("shogun.ronin.adapters.base_adapter.get_adapter", lambda: None)
    result = await restarted.execute(RoninAction(agent_id="test", action_type="desktop.screenshot"))
    assert result.status == RoninActionStatus.BLOCKED
    assert route_calls == []


def test_setup_reader_restores_non_negotiable_ronin_controls(monkeypatch, tmp_path):
    from shogun.api import setup as setup_api

    path = tmp_path / "setup.json"
    path.write_text(
        '{"ronin_desktop_control":{"verification_required":false,'
        '"high_risk_requires_approval":false,"critical_actions_blocked":false,'
        '"require_visible_indicator":false,"allow_sensitive_apps":true}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_api, "SETUP_JSON", path)
    config = setup_api._read_setup()["ronin_desktop_control"]
    assert config["verification_required"] is True
    assert config["high_risk_requires_approval"] is True
    assert config["critical_actions_blocked"] is True
    assert config["require_visible_indicator"] is True
    assert config["allow_sensitive_apps"] is False


def test_approval_ui_renders_material_details_and_digest():
    source = Path("frontend/src/pages/Ronin.tsx").read_text(encoding="utf-8")
    assert "Material action details" in source
    assert "activeApproval.action_preview.value" in source
    assert "activeApproval.action_preview.permission_gates" in source
    assert "activeApproval.action_digest" in source
    assert "decided_by: 'operator'" not in source
    assert "Native apps, shell, admin" not in source


@pytest.mark.asyncio
async def test_internal_ronin_stop_actually_pauses_runtime(monkeypatch):
    calls: list[str] = []
    observer = FakeObserver()
    monkeypatch.setattr("shogun.ronin.core.komainu.pause_komainu", lambda: calls.append("paused"))
    monkeypatch.setattr("shogun.ronin.core.approval_gate.cancel_all", lambda reason: calls.append(reason) or 0)
    monkeypatch.setattr("shogun.ronin.desktop.observation_service.get_observer", lambda: observer)
    result = await route_action(RoninAction(agent_id="test", action_type="ronin.stop"))
    assert result.status == RoninActionStatus.SUCCESS
    assert result.result_data == {"paused": True, "scope": "ronin_runtime"}
    assert calls == ["paused", "ronin_stop"]
    assert observer.paused_reason == "Ronin stop action requested"
