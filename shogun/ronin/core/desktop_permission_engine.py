"""Ronin-only desktop permission and protected-context evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from shogun.ronin.core.capabilities_registry import classify_risk
from shogun.ronin.policies.ronin_policy_schema import RiskLevel, RoninAction

DEFAULT_PROTECTED_KEYWORDS = (
    "password",
    "passcode",
    "credential",
    "banking",
    "payment",
    "checkout",
    "security settings",
    "user account control",
    "windows security",
    "wallet",
    "seed phrase",
    "private key",
    "recovery phrase",
)


@dataclass(slots=True)
class DesktopPermissionDecision:
    allowed: bool
    reason: str
    risk_tier: str
    approval_required: bool = False
    protected_context: bool = False

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class DesktopPermissionEngine:
    """Applies the non-bypassable Order 11 desktop safety gates."""

    def evaluate(
        self,
        action: RoninAction,
        permissions: dict[str, Any],
        *,
        active_window: dict[str, Any] | None = None,
    ) -> DesktopPermissionDecision:
        tier = str(permissions.get("active_tier", "")).lower()
        risk = classify_risk(action.action_type)
        if tier != "ronin":
            return DesktopPermissionDecision(False, "Desktop control is only available in Ronin posture", risk.value)
        if not permissions.get("ronin_enabled", False):
            return DesktopPermissionDecision(False, "Ronin Desktop Control is explicitly disabled", risk.value)
        if permissions.get("kill_switch_active", False):
            return DesktopPermissionDecision(False, "The global kill switch is active", risk.value)

        action_kind = action.action_type
        checks = {
            "ronin_screenshots_enabled": action_kind in {"desktop.screenshot", "desktop.state"},
            "ronin_mouse_enabled": action_kind
            in {
                "desktop.move_mouse",
                "desktop.click",
                "desktop.double_click",
                "desktop.right_click",
                "desktop.drag",
                "desktop.scroll",
            },
            "ronin_keyboard_enabled": action_kind
            in {"desktop.type", "desktop.hotkey", "desktop.key_down", "desktop.key_up"},
            "ronin_window_management_enabled": action_kind
            in {"os.list_windows", "os.active_window", "os.focus_window", "os.wait_for_window"},
            "ronin_native_apps_enabled": action_kind in {"os.app_launch", "os.app_close"},
        }
        for permission, applies in checks.items():
            if applies and not permissions.get(permission, False):
                return DesktopPermissionDecision(False, f"Permission disabled: {permission}", risk.value)

        protected_keywords = list(DEFAULT_PROTECTED_KEYWORDS)
        protected_keywords.extend(str(item).lower() for item in permissions.get("ronin_protected_applications", []))
        try:
            from shogun.api.setup import _read_setup

            setup_config = _read_setup().get("ronin_desktop_control", {})
            protected_keywords.extend(str(item).lower() for item in setup_config.get("protected_applications", []))
            protected_keywords.extend(
                str(item).lower() for item in setup_config.get("blocked_keywords_in_window_titles", [])
            )
        except Exception:
            pass

        context = " ".join(
            filter(
                None,
                [
                    str((active_window or {}).get("title", "")),
                    str((active_window or {}).get("process", "")),
                    action.target or "",
                    action.reason or "",
                    str(action.metadata.get("expected_window", "")),
                ],
            )
        ).lower()
        protected = any(keyword in context for keyword in protected_keywords)
        if protected:
            return DesktopPermissionDecision(
                False,
                "Protected or credential-related desktop context detected",
                RiskLevel.CRITICAL.value,
                protected_context=True,
            )

        if action_kind == "desktop.type":
            value = (action.value or action.target or "").lower()
            secret_markers = ("password=", "api_key=", "secret=", "private key", "seed phrase")
            if any(marker in value for marker in secret_markers):
                return DesktopPermissionDecision(
                    False, "Credential or secret entry is blocked", RiskLevel.CRITICAL.value, protected_context=True
                )

        if risk == RiskLevel.CRITICAL and permissions.get("ronin_block_critical_actions", True):
            return DesktopPermissionDecision(False, "Critical desktop actions are blocked by policy", risk.value)
        if risk == RiskLevel.HIGH and permissions.get("ronin_require_high_risk_approval", True):
            return DesktopPermissionDecision(
                False, "High-risk desktop action requires operator approval", risk.value, approval_required=True
            )

        return DesktopPermissionDecision(True, "Desktop action permitted", risk.value)


_permission_engine = DesktopPermissionEngine()


def get_desktop_permission_engine() -> DesktopPermissionEngine:
    return _permission_engine
