"""Ronin Controller — main entry point for all Ronin desktop actions.

Orchestrates the full action pipeline:
  Action Request → Environment Check → Posture Guard → App Trust Check →
  Capability Lookup → Approval Gate (if needed) → Action Router →
  Verification → Audit Logger → Gensui Telemetry
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from shogun.ronin.core import app_trust_registry, capabilities_registry
from shogun.ronin.core.action_router import route_action
from shogun.ronin.core.approval_gate import request_approval
from shogun.ronin.core.audit_logger import RoninAuditLogger
from shogun.ronin.core.environment_detector import detect_environment
from shogun.ronin.core.komainu import (
    is_paused as komainu_is_paused,
)
from shogun.ronin.core.posture_guard import evaluate as evaluate_posture
from shogun.ronin.policies.ronin_policy_schema import (
    AppTrustLevel,
    EnvironmentInfo,
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
        cap_posture_min = capability.posture_minimum.value if capability else None
        cap_trust_min = capability.app_trust_minimum.value if capability else None
        cap_risk = (
            capability.risk_level.value if capability else action.risk_level.value if action.risk_level else "high"
        )
        cap_requires_approval = capability.requires_approval if capability else False

        if not capability:
            log.warning("Ronin: unknown capability '%s' — applying HIGH risk defaults", action_type)

        # ── 4. Get current foreground app and trust level ────────
        app_trust_level = AppTrustLevel.RESTRICTED
        current_app: str | None = None

        # Only check foreground app for desktop actions
        if action_type.startswith("desktop.") and action_type != "desktop.screenshot":
            try:
                from shogun.ronin.adapters.base_adapter import get_adapter

                adapter = get_adapter()
                if adapter:
                    fg_process = adapter.get_foreground_process()
                    if fg_process:
                        current_app = fg_process
                        app_trust_level = app_trust_registry.get_trust_level(fg_process)
            except Exception as exc:
                log.debug("Ronin: foreground app detection failed: %s", exc)

        # ── 5. Get posture permissions ───────────────────────────
        posture_permissions = await self._get_posture_permissions()

        # The full desktop surface has an additional, non-bypassable Ronin-only
        # permission gate. Browser actions remain governed by Mado.
        if action_type.startswith(("desktop.", "os.")):
            from shogun.ronin.core.desktop_permission_engine import get_desktop_permission_engine
            from shogun.ronin.desktop.observation_service import get_observer

            active_window = None
            try:
                from shogun.ronin.adapters.base_adapter import get_adapter

                adapter = get_adapter()
                active_window = adapter.get_active_window() if adapter else None
            except Exception:
                pass
            await RoninAuditLogger.log_action(
                event_type="ronin.desktop.action_requested",
                action=f"Desktop action requested: {action_type}",
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=action.target,
                risk_level=cap_risk,
                detail={
                    "posture": posture_permissions.get("active_tier"),
                    "stack_run_id": action.metadata.get("stack_run_id"),
                },
            )
            desktop_decision = get_desktop_permission_engine().evaluate(
                action, posture_permissions, active_window=active_window
            )
            if not desktop_decision.allowed and not desktop_decision.approval_required:
                get_observer().record(
                    "ronin.desktop.action_blocked",
                    desktop_decision.reason,
                    action_type=action_type,
                )
                await RoninAuditLogger.log_action_blocked(
                    action_type=action_type,
                    reason=desktop_decision.reason,
                    agent_id=action.agent_id,
                    session_id=action.session_id,
                    risk_level=desktop_decision.risk_tier,
                )
                return RoninResult(
                    status=RoninActionStatus.BLOCKED,
                    action_type=action_type,
                    error=desktop_decision.reason,
                )

        # ── 6. Posture guard evaluation ──────────────────────────
        decision = evaluate_posture(
            action_type=action_type,
            agent_id=action.agent_id,
            current_posture=posture_permissions.get("ronin_posture", "disabled"),
            posture_permissions=posture_permissions,
            app_trust_level=app_trust_level,
            environment_type=self._environment.environment_type if self._environment else None,
            capability_posture_min=cap_posture_min,
            capability_trust_min=cap_trust_min,
            capability_risk=cap_risk,
            capability_requires_approval=cap_requires_approval,
        )

        # ── 7. Handle blocked / approval-required ────────────────
        if not decision.allowed and not decision.approval_required:
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

        if decision.approval_required:
            # ── Request operator approval via WebSocket modal ────
            try:
                from shogun.ronin.desktop.screenshot_controller import take_screenshot_raw

                screenshot_path = await take_screenshot_raw(prefix="approval")
            except Exception:
                screenshot_path = None

            approval = await request_approval(
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=action.target,
                reason=decision.reason,
                risk_level=cap_risk,
                app_name=current_app,
                app_trust=app_trust_level.value,
                screenshot_path=screenshot_path,
            )

            if approval.status != "approved":
                return RoninResult(
                    status=RoninActionStatus.APPROVAL_REQUIRED,
                    action_type=action_type,
                    error=f"Action {approval.status}: {decision.reason}",
                    approval_id=approval.id,
                )

        if action_type.startswith(("desktop.", "os.")):
            await RoninAuditLogger.log_action(
                event_type="ronin.desktop.action_allowed",
                action=f"Desktop action allowed: {action_type}",
                agent_id=action.agent_id,
                session_id=action.session_id,
                action_type=action_type,
                target=action.target,
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
        observer.set_next_action({"action_type": action_type, "target": action.target})
        observer.record("ronin.desktop.action_started", f"Started {action_type}", target=action.target)
        non_repeatable = action_type in {
            "desktop.type",
            "desktop.hotkey",
            "desktop.key_down",
            "desktop.key_up",
            "os.app_launch",
            "os.app_close",
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
                            target=action.target,
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
                        target=action.target,
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
                    target=action.target,
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
                    target=action.target,
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
                    target=action.target,
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
            target=action.target,
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
                    target=action.target,
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
