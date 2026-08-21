"""Ronin Controller — main entry point for all Ronin desktop actions.

Orchestrates the full action pipeline:
  Action Request → Environment Check → Posture Guard → App Trust Check →
  Capability Lookup → Approval Gate (if needed) → Action Router →
  Verification → Audit Logger → Gensui Telemetry
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from shogun.ronin.core import app_trust_registry, capabilities_registry
from shogun.ronin.core.action_router import route_action
from shogun.ronin.core.approval_gate import (
    action_digest,
    action_preview,
    action_target_preview,
    request_approval,
)
from shogun.ronin.core.audit_logger import RoninAuditLogger
from shogun.ronin.core.environment_detector import detect_environment
from shogun.ronin.core.komainu import (
    is_paused as komainu_is_paused,
)
from shogun.ronin.core.posture_guard import evaluate as evaluate_posture
from shogun.ronin.policies.ronin_policy_schema import (
    AppTrustLevel,
    EnvironmentInfo,
    PostureDecision,
    RoninAction,
    RoninActionStatus,
    RoninResult,
)

log = logging.getLogger("shogun.ronin.controller")

# ── In-memory session state ──────────────────────────────────────────

_sessions: dict[str, dict[str, Any]] = {}
_environment: EnvironmentInfo | None = None


class RoninController:
    """Main orchestrator for Ronin desktop control actions."""

    def __init__(self):
        self._initialized = False
        self._environment: EnvironmentInfo | None = None

    async def initialize(self) -> EnvironmentInfo:
        """Initialize Ronin — detect environment and prepare subsystems."""
        if not self._initialized:
            self._environment = detect_environment()
            global _environment
            _environment = self._environment
            self._initialized = True
            log.info(
                "Ronin initialized: environment=%s, os=%s, hostname=%s",
                self._environment.environment_type.value,
                self._environment.os_type,
                self._environment.hostname,
            )
        return self._environment

    async def _collect_security_context(
        self,
        action: RoninAction,
    ) -> tuple[dict[str, Any], str | None, AppTrustLevel, dict[str, Any] | None]:
        """Read the live policy and foreground context used for a decision."""
        posture_permissions = await self._get_posture_permissions()
        current_app: str | None = None
        app_trust_level = AppTrustLevel.RESTRICTED
        active_window: dict[str, Any] | None = None
        if action.action_type.startswith(("desktop.", "os.")):
            try:
                from shogun.ronin.adapters.base_adapter import get_adapter

                adapter = get_adapter()
                if adapter:
                    active_window = adapter.get_active_window()
                    if action.action_type.startswith("desktop.") and action.action_type != "desktop.screenshot":
                        foreground_process = adapter.get_foreground_process()
                        if foreground_process:
                            current_app = foreground_process
                            app_trust_level = app_trust_registry.get_trust_level(foreground_process)
            except Exception as exc:
                log.debug("Ronin: foreground security context detection failed: %s", exc)
        return posture_permissions, current_app, app_trust_level, active_window

    def _evaluate_security_context(
        self,
        action: RoninAction,
        capability: Any,
        posture_permissions: dict[str, Any],
        app_trust_level: AppTrustLevel,
        active_window: dict[str, Any] | None,
    ) -> tuple[PostureDecision, Any | None]:
        """Combine desktop and posture decisions; any hard denial wins."""
        desktop_decision = None
        if action.action_type.startswith(("desktop.", "os.")):
            from shogun.ronin.core.desktop_permission_engine import get_desktop_permission_engine

            desktop_decision = get_desktop_permission_engine().evaluate(
                action,
                posture_permissions,
                active_window=active_window,
            )

        permission_gates = capabilities_registry.resolve_permission_gates(action)
        posture_decision = evaluate_posture(
            action_type=action.action_type,
            agent_id=action.agent_id,
            current_posture=posture_permissions.get("ronin_posture", "disabled"),
            posture_permissions=posture_permissions,
            app_trust_level=app_trust_level,
            environment_type=self._environment.environment_type if self._environment else None,
            capability_posture_min=capability.posture_minimum.value,
            capability_trust_min=capability.app_trust_minimum.value,
            capability_risk=capability.risk_level.value,
            capability_requires_approval=capability.requires_approval,
            capability_permission_gates=permission_gates,
        )
        if desktop_decision and not desktop_decision.allowed and not desktop_decision.approval_required:
            return (
                PostureDecision(
                    allowed=False,
                    reason=desktop_decision.reason,
                    risk_level=capability.risk_level,
                ),
                desktop_decision,
            )
        if not posture_decision.allowed and not posture_decision.approval_required:
            return posture_decision, desktop_decision

        approval_reasons = []
        if desktop_decision and desktop_decision.approval_required:
            approval_reasons.append(desktop_decision.reason)
        if posture_decision.approval_required:
            approval_reasons.append(posture_decision.reason)
        if approval_reasons:
            return (
                PostureDecision(
                    allowed=False,
                    approval_required=True,
                    reason=" ".join(dict.fromkeys(approval_reasons)),
                    risk_level=capability.risk_level,
                    app_trust=app_trust_level,
                    environment=self._environment.environment_type if self._environment else None,
                ),
                desktop_decision,
            )
        return posture_decision, desktop_decision

    @staticmethod
    def _window_identity(active_window: dict[str, Any] | None) -> dict[str, Any]:
        window = active_window or {}
        identifiers = {
            key: str(window[key])
            for key in ("handle", "hwnd", "id", "window_id")
            if window.get(key) not in (None, "")
        }
        return {
            "process": str(window.get("process", "")),
            "title": str(window.get("title", "")),
            "stable_identifiers": identifiers,
            "stable_identifier_available": bool(identifiers),
        }

    @staticmethod
    def _security_snapshot(
        *,
        action: RoninAction,
        capability: Any,
        posture_permissions: dict[str, Any],
        current_app: str | None,
        app_trust_level: AppTrustLevel,
        active_window: dict[str, Any] | None,
    ) -> str:
        """Bind an approval to the material policy and UI context it reviewed."""
        relevant_posture = {
            key: value
            for key, value in posture_permissions.items()
            if key.startswith("ronin_") or key in {"active_tier", "kill_switch_active"}
        }
        material = {
            "action_digest": action_digest(action),
            "capability": capability.model_dump(mode="json"),
            "posture": relevant_posture,
            "current_app": current_app,
            "app_trust": app_trust_level.value,
            "active_window": RoninController._window_identity(active_window),
        }
        return json.dumps(material, sort_keys=True, separators=(",", ":"), default=str)

    async def execute(self, action: RoninAction) -> RoninResult:
        """Execute a Ronin action through the full pipeline.

        This is the single entry point for all Ronin desktop operations.
        """
        start_time = time.monotonic()
        action_type = action.action_type

        # ── 1. Ensure initialized ────────────────────────────────
        if not self._initialized:
            await self.initialize()

        # ── 2. Komainu check — is Ronin paused? ──────────────────
        if komainu_is_paused():
            return RoninResult(
                status=RoninActionStatus.KOMAINU_PAUSED,
                action_type=action_type,
                error="Ronin is paused by Komainu guardian. Resume or stop session first.",
            )

        # ── 3. Capability lookup ─────────────────────────────────
        capability = capabilities_registry.get_capability(action_type)
        if capability is None or not capability.enabled:
            reason = f"Unknown or disabled Ronin capability '{action_type}' was blocked."
            log.warning("Ronin: %s", reason)
            await RoninAuditLogger.log_action_blocked(
                action_type=action_type,
                reason=reason,
                agent_id=action.agent_id,
                session_id=action.session_id,
                risk_level="critical",
            )
            return RoninResult(
                status=RoninActionStatus.BLOCKED,
                action_type=action_type,
                error=reason,
            )

        # Caller-provided risk metadata never lowers the registered capability.
        cap_risk = capability.risk_level.value
        permission_gates = capabilities_registry.resolve_permission_gates(action)
        safe_target = action_target_preview(action, permission_gates)
        posture_permissions, current_app, app_trust_level, active_window = (
            await self._collect_security_context(action)
        )

        if action_type.startswith(("desktop.", "os.")):
            await RoninAuditLogger.log_action(
                event_type="ronin.desktop.action_requested",
                action=f"Desktop action requested: {action_type}",
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=safe_target,
                risk_level=cap_risk,
                detail={
                    "posture": posture_permissions.get("active_tier"),
                    "stack_run_id": action.metadata.get("stack_run_id"),
                },
            )

        # ── 4. Combine desktop and posture decisions ─────────────
        decision, _desktop_decision = self._evaluate_security_context(
            action,
            capability,
            posture_permissions,
            app_trust_level,
            active_window,
        )

        # ── 5. Handle blocked / approval-required ────────────────
        if not decision.allowed and not decision.approval_required:
            if action_type.startswith(("desktop.", "os.")):
                from shogun.ronin.desktop.observation_service import get_observer

                get_observer().record(
                    "ronin.desktop.action_blocked",
                    decision.reason,
                    action_type=action_type,
                )
            await RoninAuditLogger.log_action_blocked(
                action_type=action_type,
                reason=decision.reason,
                agent_id=action.agent_id,
                session_id=action.session_id,
                app_trust=app_trust_level.value,
                risk_level=cap_risk,
            )
            return RoninResult(
                status=RoninActionStatus.POSTURE_DENIED
                if "posture" in decision.reason.lower()
                else RoninActionStatus.APP_FORBIDDEN
                if "FORBIDDEN" in decision.reason
                else RoninActionStatus.ENVIRONMENT_DENIED
                if "environment" in decision.reason.lower()
                else RoninActionStatus.BLOCKED,
                action_type=action_type,
                error=decision.reason,
            )

        initial_action_digest = action_digest(action)
        approval_snapshot = self._security_snapshot(
            action=action,
            capability=capability,
            posture_permissions=posture_permissions,
            current_app=current_app,
            app_trust_level=app_trust_level,
            active_window=active_window,
        )
        approval_id: str | None = None
        if decision.approval_required:
            try:
                from shogun.ronin.desktop.screenshot_controller import take_screenshot_raw

                screenshot_path = await take_screenshot_raw(prefix="approval")
            except Exception:
                screenshot_path = None

            preview = action_preview(action, permission_gates)
            preview["active_window"] = self._window_identity(active_window)
            approval_target = preview.get("target")
            preview["target"] = approval_target
            approval = await request_approval(
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=approval_target,
                reason=decision.reason,
                risk_level=cap_risk,
                app_name=current_app,
                app_trust=app_trust_level.value,
                screenshot_path=screenshot_path,
                action_digest=initial_action_digest,
                action_preview=preview,
            )
            approval_id = approval.id

            if approval.status != "approved":
                return RoninResult(
                    status=RoninActionStatus.APPROVAL_REQUIRED,
                    action_type=action_type,
                    error=f"Action {approval.status}: {decision.reason}",
                    approval_id=approval.id,
                )

            if approval.action_digest != initial_action_digest or action_digest(action) != initial_action_digest:
                reason = "Action details changed while approval was pending; the approval was invalidated."
                await RoninAuditLogger.log_action_blocked(
                    action_type=action_type,
                    reason=reason,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    risk_level=cap_risk,
                )
                return RoninResult(
                    status=RoninActionStatus.BLOCKED,
                    action_type=action_type,
                    error=reason,
                    approval_id=approval.id,
                )

            # Approval may remain open for five minutes. Re-read every material
            # security input before treating it as authorization.
            if komainu_is_paused():
                return RoninResult(
                    status=RoninActionStatus.KOMAINU_PAUSED,
                    action_type=action_type,
                    error="Ronin was paused while approval was pending.",
                    approval_id=approval.id,
                )
            refreshed_capability = capabilities_registry.get_capability(action_type)
            if refreshed_capability is None or not refreshed_capability.enabled:
                return RoninResult(
                    status=RoninActionStatus.BLOCKED,
                    action_type=action_type,
                    error="The capability was removed or disabled while approval was pending.",
                    approval_id=approval.id,
                )
            posture_permissions, current_app, app_trust_level, active_window = (
                await self._collect_security_context(action)
            )
            refreshed_decision, _ = self._evaluate_security_context(
                action,
                refreshed_capability,
                posture_permissions,
                app_trust_level,
                active_window,
            )
            refreshed_snapshot = self._security_snapshot(
                action=action,
                capability=refreshed_capability,
                posture_permissions=posture_permissions,
                current_app=current_app,
                app_trust_level=app_trust_level,
                active_window=active_window,
            )
            if (
                refreshed_snapshot != approval_snapshot
                or (not refreshed_decision.allowed and not refreshed_decision.approval_required)
            ):
                reason = "Security posture or active application context changed after approval; submit a new request."
                await RoninAuditLogger.log_action_blocked(
                    action_type=action_type,
                    reason=reason,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    risk_level=cap_risk,
                )
                return RoninResult(
                    status=RoninActionStatus.BLOCKED,
                    action_type=action_type,
                    error=reason,
                    approval_id=approval.id,
                )
            capability = refreshed_capability

        if action_type.startswith(("desktop.", "os.")):
            await RoninAuditLogger.log_action(
                event_type="ronin.desktop.action_allowed",
                action=f"Desktop action allowed: {action_type}",
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=safe_target,
                risk_level=cap_risk,
                detail={"posture": posture_permissions.get("active_tier"), "permission_result": "allowed"},
            )

        # ── 8. Take before-screenshot ────────────────────────────
        screenshot_before: str | None = None
        before_state: dict[str, Any] = {}
        from shogun.ronin.desktop.observation_service import get_observer

        observer = get_observer()
        if posture_permissions.get("ronin_screenshots_enabled", False):
            try:
                before_state = await observer.capture_state(screenshot=True, prefix="before")
                screenshot_before = before_state.get("screenshot_path")
            except Exception:
                pass

        # ── 9. Execute via action router ─────────────────────────
        from shogun.ronin.desktop.recovery_service import get_recovery_service
        from shogun.ronin.desktop.verification_service import get_verifier

        observer.resume()
        observer.set_next_action({"action_type": action_type, "target": safe_target})
        observer.record("ronin.desktop.action_started", f"Started {action_type}", target=safe_target)
        non_repeatable = action_type in {
            "desktop.type",
            "desktop.hotkey",
            "desktop.key_down",
            "desktop.key_up",
            "os.app_launch",
            "os.app_close",
            "ronin.stop",
            "ronin.harakiri",
        }
        try:
            from shogun.api.setup import _read_setup

            configured_retries = int(_read_setup().get("ronin_desktop_control", {}).get("max_action_retries", 3))
        except Exception:
            configured_retries = 3
        default_retries = 0 if non_repeatable else configured_retries
        max_retries = max(0, min(int(action.metadata.get("max_retries", default_retries)), 5))
        attempt = 0
        after_state: dict[str, Any] = {}
        while True:
            observer.set_retry_count(attempt)
            pre_route_error: str | None = None
            pre_route_status = RoninActionStatus.BLOCKED
            if komainu_is_paused():
                pre_route_error = "Ronin was paused before action execution."
                pre_route_status = RoninActionStatus.KOMAINU_PAUSED
            elif action_digest(action) != initial_action_digest:
                pre_route_error = "Action details changed after security evaluation; execution was blocked."
            else:
                live_capability = capabilities_registry.get_capability(action_type)
                if live_capability is None or not live_capability.enabled:
                    pre_route_error = "The registered capability was removed or disabled before execution."
                else:
                    live_posture, live_app, live_trust, live_window = await self._collect_security_context(action)
                    live_decision, _ = self._evaluate_security_context(
                        action,
                        live_capability,
                        live_posture,
                        live_trust,
                        live_window,
                    )
                    live_snapshot = self._security_snapshot(
                        action=action,
                        capability=live_capability,
                        posture_permissions=live_posture,
                        current_app=live_app,
                        app_trust_level=live_trust,
                        active_window=live_window,
                    )
                    if approval_id:
                        if live_snapshot != approval_snapshot:
                            pre_route_error = (
                                "Security posture or active application context changed after approval; "
                                "execution was blocked."
                            )
                        elif not live_decision.allowed and not live_decision.approval_required:
                            pre_route_error = live_decision.reason
                    elif not live_decision.allowed:
                        pre_route_error = (
                            f"Security re-check did not allow execution: {live_decision.reason}"
                        )
                    if pre_route_error is None:
                        capability = live_capability
                        posture_permissions = live_posture
                        current_app = live_app
                        app_trust_level = live_trust

            if pre_route_error is not None:
                await RoninAuditLogger.log_action_blocked(
                    action_type=action_type,
                    reason=pre_route_error,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    app_trust=app_trust_level.value,
                    risk_level=cap_risk,
                )
                result = RoninResult(
                    status=pre_route_status,
                    action_type=action_type,
                    target=safe_target,
                    error=pre_route_error,
                    approval_id=approval_id,
                )
                observer.pause(pre_route_error)
                break
            result = await route_action(action)
            try:
                after_state = await observer.capture_state(
                    screenshot=posture_permissions.get("ronin_screenshots_enabled", False),
                    prefix="after",
                )
            except Exception:
                after_state = {}

            after_window = after_state.get("active_window")
            if action_type.startswith(("desktop.", "os.")) and after_window:
                from shogun.ronin.core.desktop_permission_engine import get_desktop_permission_engine
                from shogun.ronin.desktop.dialog_service import get_dialog_service

                dialog = get_dialog_service().classify(after_window)
                if dialog.detected:
                    observer.record("ronin.desktop.dialog_detected", dialog.reason, dialog=dialog.model_dump())
                    await RoninAuditLogger.log_action(
                        event_type="ronin.desktop.dialog_detected",
                        action=dialog.reason,
                        agent_id=action.agent_id,
                        session_id=action.session_id,
                        action_type=action_type,
                        target=str(after_window.get("title", "")),
                        result="safe" if dialog.safe_to_handle else "paused",
                        severity="info" if dialog.safe_to_handle else "warn",
                        risk_level="low" if dialog.safe_to_handle else "high",
                        detail={"dialog": dialog.model_dump()},
                    )
                    if not dialog.safe_to_handle:
                        result = RoninResult(
                            status=RoninActionStatus.BLOCKED,
                            action_type=action_type,
                            target=safe_target,
                            error=dialog.reason,
                        )
                        observer.pause(dialog.reason)
                        break
                protected_decision = get_desktop_permission_engine().evaluate(
                    action, posture_permissions, active_window=after_window
                )
                if protected_decision.protected_context:
                    result = RoninResult(
                        status=RoninActionStatus.BLOCKED,
                        action_type=action_type,
                        target=safe_target,
                        error=protected_decision.reason,
                    )
                    observer.pause(protected_decision.reason)
                    break

            if result.status == RoninActionStatus.SUCCESS and posture_permissions.get(
                "ronin_require_verification", True
            ):
                observer.record(
                    "ronin.desktop.verification_started", f"Verifying {action_type}", action_type=action_type
                )
                await RoninAuditLogger.log_action(
                    event_type="ronin.desktop.verification_started",
                    action=f"Verifying desktop action: {action_type}",
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    action_type=action_type,
                    target=safe_target,
                    result="started",
                    risk_level=cap_risk,
                )
                verification = await get_verifier().verify(
                    action_type,
                    result.result_data,
                    before_state,
                    after_state,
                    action.metadata.get("expected_result"),
                )
                verification_data = verification.model_dump()
                observer.set_verification(verification_data)
                result.verified = verification.passed
                result.result_data["verification"] = verification_data
                observer.record(
                    "ronin.desktop.verification_passed" if verification.passed else "ronin.desktop.verification_failed",
                    verification.message,
                    action_type=action_type,
                )
            else:
                result.verified = result.status == RoninActionStatus.SUCCESS

            if result.status == RoninActionStatus.SUCCESS and result.verified:
                break
            recovery = get_recovery_service().decide(
                attempt=attempt,
                max_retries=max_retries,
                error=result.error or result.result_data.get("verification", {}).get("message"),
            )
            if recovery.retry:
                attempt += 1
                observer.record(
                    "ronin.desktop.retry_started", recovery.reason, action_type=action_type, attempt=attempt
                )
                await RoninAuditLogger.log_action(
                    event_type="ronin.desktop.retry_started",
                    action=recovery.reason,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    action_type=action_type,
                    target=safe_target,
                    result="retrying",
                    severity="warn",
                    risk_level=cap_risk,
                    detail={"attempt": attempt, "max_retries": max_retries},
                )
                await asyncio.sleep(min(0.25 * attempt, 1.0))
                continue
            if recovery.pause:
                observer.record(
                    "ronin.desktop.retry_exhausted", recovery.reason, action_type=action_type, attempt=attempt
                )
                await RoninAuditLogger.log_action(
                    event_type="ronin.desktop.retry_exhausted",
                    action=recovery.reason,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    action_type=action_type,
                    target=safe_target,
                    result="exhausted",
                    severity="warn",
                    risk_level=cap_risk,
                    detail={"attempt": attempt, "max_retries": max_retries},
                )
                observer.pause(recovery.reason)
            break
        observer.set_next_action(None)

        # ── 10. Take after-screenshot ────────────────────────────
        screenshot_after: str | None = after_state.get("screenshot_path")

        # ── 11. Record timing ────────────────────────────────────
        duration_ms = int((time.monotonic() - start_time) * 1000)
        result.screenshot_before = screenshot_before
        result.screenshot_after = screenshot_after
        result.duration_ms = duration_ms
        event_name = (
            "ronin.desktop.action_completed"
            if result.status == RoninActionStatus.SUCCESS
            else "ronin.desktop.action_failed"
        )
        observer.record(
            event_name, f"{action_type}: {result.status.value}", action_type=action_type, verified=result.verified
        )

        # ── 12. Audit log ────────────────────────────────────────
        await RoninAuditLogger.log_action(
            event_type=event_name if action_type.startswith(("desktop.", "os.")) else f"ronin.action.{action_type}",
            action=f"Ronin: {action_type} → {result.status.value}",
            agent_id=action.agent_id,
            session_id=action.session_id,
            action_type=action_type,
            target=safe_target,
            result=result.status.value,
            severity="info" if result.status == RoninActionStatus.SUCCESS else "warn",
            risk_level=cap_risk,
            app_trust=app_trust_level.value,
            environment_type=self._environment.environment_type.value if self._environment else None,
            screenshot_before=screenshot_before,
            screenshot_after=screenshot_after,
            confidence=result.confidence,
            verified=result.verified,
            duration_ms=duration_ms,
        )

        if action_type.startswith(("desktop.", "os.")):
            specific_events = {
                "desktop.screenshot": "ronin.desktop.screenshot_taken",
                "desktop.state": "ronin.desktop.state_observed",
                "desktop.click": "ronin.desktop.click",
                "desktop.double_click": "ronin.desktop.click",
                "desktop.right_click": "ronin.desktop.click",
                "desktop.type": "ronin.desktop.type_text",
                "desktop.hotkey": "ronin.desktop.hotkey",
                "desktop.scroll": "ronin.desktop.scroll",
                "os.focus_window": "ronin.desktop.window_focused",
                "os.app_launch": "ronin.desktop.application_opened",
            }
            specific_event = specific_events.get(action_type)
            if specific_event:
                await RoninAuditLogger.log_action(
                    event_type=specific_event,
                    action=f"Desktop primitive completed: {action_type}",
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    action_type=action_type,
                    target=safe_target,
                    result=result.status.value,
                    severity="info" if result.status == RoninActionStatus.SUCCESS else "warn",
                    risk_level=cap_risk,
                    screenshot_before=screenshot_before,
                    screenshot_after=screenshot_after,
                    verified=result.verified,
                    detail={
                        "posture": posture_permissions.get("active_tier"),
                        "stack_run_id": action.metadata.get("stack_run_id"),
                    },
                )
            if result.result_data.get("verification"):
                verification = result.result_data["verification"]
                await RoninAuditLogger.log_action(
                    event_type="ronin.desktop.verification_passed"
                    if verification.get("passed")
                    else "ronin.desktop.verification_failed",
                    action=verification.get("message", f"Verified {action_type}"),
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    action_type=action_type,
                    result="passed" if verification.get("passed") else "failed",
                    severity="info" if verification.get("passed") else "warn",
                    risk_level=cap_risk,
                    verified=bool(verification.get("passed")),
                    detail={"verification": verification},
                )

        # ── 13. Gensui telemetry ─────────────────────────────────
        try:
            from shogun.ronin.telemetry.gensui_publisher import publish_action

            await publish_action(action_type, result.status.value, current_app)
        except Exception:
            pass

        return result

    async def _get_posture_permissions(self) -> dict[str, Any]:
        """Get the current Ronin posture permissions from the Shogun posture store."""
        try:
            from shogun.api.security import _get_agent_posture

            posture = await _get_agent_posture()
            return posture
        except Exception as exc:
            log.error("Ronin: failed to get posture: %s", exc)
            return {"ronin_enabled": False, "ronin_posture": "disabled"}

    def get_environment(self) -> EnvironmentInfo | None:
        """Get the detected environment info."""
        return self._environment


# ── Module-level singleton ───────────────────────────────────────────

_controller: RoninController | None = None


def get_controller() -> RoninController:
    """Get or create the singleton RoninController."""
    global _controller
    if _controller is None:
        _controller = RoninController()
    return _controller


async def execute_action(action: RoninAction) -> RoninResult:
    """Convenience function — execute a Ronin action through the controller."""
    controller = get_controller()
    return await controller.execute(action)
