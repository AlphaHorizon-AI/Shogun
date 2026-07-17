"""Ronin Capabilities Registry — extensible action/risk registration.

Instead of hardcoded action types, Ronin uses a capability registry where
each action is a registered capability with risk metadata, posture minimum,
and app trust requirements.

Future: Ronin Plugins / Skills / Integrations register themselves here.
"""

from __future__ import annotations

import logging
from typing import Any

from shogun.ronin.policies.ronin_policy_schema import (
    AppTrustLevel,
    RiskLevel,
    RoninCapability,
    RoninPostureLevel,
)

log = logging.getLogger("shogun.ronin.capabilities")

# ── Global registry ──────────────────────────────────────────────────

_registry: dict[str, RoninCapability] = {}


# ── Built-in capabilities ────────────────────────────────────────────

_BUILTIN_CAPABILITIES: list[dict[str, Any]] = [
    # ── Desktop: Observation ──
    {
        "name": "desktop.screenshot",
        "category": "desktop",
        "risk_level": "low",
        "description": "Capture a screenshot of the desktop or a region",
        "posture_minimum": "observe_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "desktop.locate_image",
        "category": "desktop",
        "risk_level": "low",
        "description": "Locate a UI element on screen using image template matching",
        "posture_minimum": "observe_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "desktop.read_screen",
        "category": "desktop",
        "risk_level": "low",
        "description": "Interpret screen contents using vision (OpenCV or LLM)",
        "posture_minimum": "observe_only",
        "app_trust_minimum": "trusted",
    },
    # ── Desktop: Interaction ──
    {
        "name": "desktop.move_mouse",
        "category": "desktop",
        "risk_level": "low",
        "description": "Move the mouse cursor to a position",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.click",
        "category": "desktop",
        "risk_level": "low",
        "description": "Click at a position or on a located element",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.double_click",
        "category": "desktop",
        "risk_level": "low",
        "description": "Double-click at a position or on a located element",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.right_click",
        "category": "desktop",
        "risk_level": "low",
        "description": "Right-click at a position",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.type",
        "category": "desktop",
        "risk_level": "medium",
        "description": "Type text using the keyboard",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.hotkey",
        "category": "desktop",
        "risk_level": "medium",
        "description": "Press a keyboard shortcut (e.g. Ctrl+S, Alt+F4)",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.drag",
        "category": "desktop",
        "risk_level": "medium",
        "description": "Drag from one position to another",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.scroll",
        "category": "desktop",
        "risk_level": "low",
        "description": "Scroll the mouse wheel",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "restricted",
    },
    {
        "name": "desktop.state",
        "category": "desktop",
        "risk_level": "low",
        "description": "Capture screenshot, active window, window list, and display state",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "desktop.key_down",
        "category": "desktop",
        "risk_level": "medium",
        "description": "Hold a keyboard key",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "desktop.key_up",
        "category": "desktop",
        "risk_level": "medium",
        "description": "Release a keyboard key",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    # ── Browser ──
    {
        "name": "browser.open",
        "category": "browser",
        "risk_level": "low",
        "description": "Open a URL in the browser (via Mado/Playwright)",
        "posture_minimum": "browser_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "browser.click",
        "category": "browser",
        "risk_level": "low",
        "description": "Click a DOM element in the browser",
        "posture_minimum": "browser_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "browser.type",
        "category": "browser",
        "risk_level": "medium",
        "description": "Type into a form field in the browser",
        "posture_minimum": "browser_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "browser.extract",
        "category": "browser",
        "risk_level": "low",
        "description": "Extract text or HTML from a page element",
        "posture_minimum": "browser_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "browser.screenshot",
        "category": "browser",
        "risk_level": "low",
        "description": "Capture a browser page screenshot",
        "posture_minimum": "browser_only",
        "app_trust_minimum": "trusted",
    },
    # ── OS ──
    {
        "name": "os.list_windows",
        "category": "os",
        "risk_level": "low",
        "description": "List all open windows",
        "posture_minimum": "observe_only",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.focus_window",
        "category": "os",
        "risk_level": "low",
        "description": "Bring a window to the foreground",
        "posture_minimum": "desktop_limited",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.active_window",
        "category": "os",
        "risk_level": "low",
        "description": "Read the active desktop window",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.wait_for_window",
        "category": "os",
        "risk_level": "low",
        "description": "Dynamically wait for a matching window",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.wait_for_file",
        "category": "os",
        "risk_level": "low",
        "description": "Dynamically wait for a file artifact",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.display_info",
        "category": "os",
        "risk_level": "low",
        "description": "Read DPI and multi-monitor geometry",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "os.app_launch",
        "category": "os",
        "risk_level": "high",
        "description": "Launch an application",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "restricted",
        "requires_approval": True,
    },
    {
        "name": "os.app_close",
        "category": "os",
        "risk_level": "high",
        "description": "Request a normal application window close",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "restricted",
        "requires_approval": True,
    },
    # ── App-specific (high-risk examples) ──
    {
        "name": "outlook.send_email",
        "category": "app",
        "risk_level": "critical",
        "description": "Send an email via Outlook",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "sensitive",
        "requires_approval": True,
    },
    {
        "name": "sap.create_purchase_order",
        "category": "app",
        "risk_level": "critical",
        "description": "Create a purchase order in SAP",
        "posture_minimum": "desktop_full",
        "app_trust_minimum": "sensitive",
        "requires_approval": True,
    },
    # ── Ronin control ──
    {
        "name": "ronin.stop",
        "category": "ronin",
        "risk_level": "low",
        "description": "Stop current Ronin session",
        "posture_minimum": "disabled",
        "app_trust_minimum": "trusted",
    },
    {
        "name": "ronin.harakiri",
        "category": "ronin",
        "risk_level": "low",
        "description": "Emergency stop all Ronin and Shogun activity",
        "posture_minimum": "disabled",
        "app_trust_minimum": "trusted",
    },
]


def _seed_builtins() -> None:
    """Register all built-in capabilities."""
    for cap_data in _BUILTIN_CAPABILITIES:
        cap = RoninCapability(
            name=cap_data["name"],
            category=cap_data["category"],
            risk_level=RiskLevel(cap_data["risk_level"]),
            description=cap_data.get("description", ""),
            posture_minimum=RoninPostureLevel(cap_data.get("posture_minimum", "desktop_limited")),
            app_trust_minimum=AppTrustLevel(cap_data.get("app_trust_minimum", "trusted")),
            requires_approval=cap_data.get("requires_approval", False),
            handler=cap_data.get("handler", ""),
            enabled=True,
        )
        _registry[cap.name] = cap


# Seed on import
_seed_builtins()


# ── Public API ───────────────────────────────────────────────────────


def get_capability(name: str) -> RoninCapability | None:
    """Look up a capability by name."""
    return _registry.get(name)


def list_capabilities(*, category: str | None = None) -> list[RoninCapability]:
    """List all registered capabilities, optionally filtered by category."""
    caps = list(_registry.values())
    if category:
        caps = [c for c in caps if c.category == category]
    return caps


def register_capability(capability: RoninCapability) -> None:
    """Register a new capability (future: plugins/skills use this)."""
    if capability.name in _registry:
        log.warning("Ronin: overwriting capability registration: %s", capability.name)
    _registry[capability.name] = capability
    log.info("Ronin: registered capability %s (risk=%s)", capability.name, capability.risk_level.value)


def unregister_capability(name: str) -> bool:
    """Remove a capability registration. Returns True if found."""
    return _registry.pop(name, None) is not None


def classify_risk(action_type: str) -> RiskLevel:
    """Get the risk level for an action type. Defaults to HIGH for unknown actions."""
    cap = _registry.get(action_type)
    if cap:
        return cap.risk_level
    log.warning("Ronin: unknown action type '%s' — defaulting to HIGH risk", action_type)
    return RiskLevel.HIGH
