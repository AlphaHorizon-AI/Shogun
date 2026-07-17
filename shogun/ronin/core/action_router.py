"""Action Router — routes approved Ronin actions to the correct controller.

Registry pattern mapping action_type prefixes to handler functions:
  browser.*       → PlaywrightController (Mado bridge)
  desktop.*       → PyAutoGUI Controllers
  desktop.read_*  → Vision Controller
  os.*            → OS Adapter
  ronin.*         → Internal (stop, harakiri)
"""

from __future__ import annotations

import logging

from shogun.ronin.policies.ronin_policy_schema import (
    RoninAction,
    RoninActionStatus,
    RoninResult,
)

log = logging.getLogger("shogun.ronin.router")


async def route_action(action: RoninAction) -> RoninResult:
    """Route an approved action to the correct handler.

    The action has already passed posture guard, app trust, and
    approval checks before reaching here.
    """
    action_type = action.action_type
    prefix = action_type.split(".")[0] if "." in action_type else action_type
    suffix = action_type.split(".", 1)[1] if "." in action_type else ""

    try:
        if prefix == "desktop":
            return await _route_desktop(action, suffix)
        elif prefix == "browser":
            return await _route_browser(action, suffix)
        elif prefix == "os":
            return await _route_os(action, suffix)
        elif prefix == "ronin":
            return await _route_ronin_internal(action, suffix)
        elif prefix == "app":
            return await _route_app(action, suffix)
        else:
            return RoninResult(
                status=RoninActionStatus.FAILED,
                action_type=action_type,
                error=f"Unknown action prefix: '{prefix}'",
            )
    except Exception as exc:
        log.error("Ronin: action '%s' failed with exception: %s", action_type, exc, exc_info=True)
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type=action_type,
            error=str(exc),
        )


async def _route_desktop(action: RoninAction, suffix: str) -> RoninResult:
    """Route desktop.* actions."""
    if suffix == "screenshot":
        from shogun.ronin.desktop.screenshot_controller import take_screenshot

        return await take_screenshot(action)

    elif suffix in ("move_mouse",):
        from shogun.ronin.desktop.mouse_controller import move_mouse

        return await move_mouse(action)

    elif suffix == "click":
        from shogun.ronin.desktop.mouse_controller import click

        return await click(action)

    elif suffix == "double_click":
        from shogun.ronin.desktop.mouse_controller import double_click

        return await double_click(action)

    elif suffix == "right_click":
        from shogun.ronin.desktop.mouse_controller import right_click

        return await right_click(action)

    elif suffix == "drag":
        from shogun.ronin.desktop.mouse_controller import drag

        return await drag(action)

    elif suffix == "scroll":
        from shogun.ronin.desktop.mouse_controller import scroll

        return await scroll(action)

    elif suffix == "type":
        from shogun.ronin.desktop.keyboard_controller import type_text

        return await type_text(action)

    elif suffix == "hotkey":
        from shogun.ronin.desktop.keyboard_controller import hotkey

        return await hotkey(action)

    elif suffix in ("key_down", "key_up"):
        from shogun.ronin.desktop.keyboard_controller import key_event

        return await key_event(action, down=suffix == "key_down")

    elif suffix == "state":
        from shogun.ronin.desktop.observation_service import get_observer

        state = await get_observer().capture_state(screenshot=True, prefix="state")
        return RoninResult(status=RoninActionStatus.SUCCESS, action_type=action.action_type, result_data=state)

    elif suffix == "locate_image":
        from shogun.ronin.desktop.vision_controller import locate_image

        return await locate_image(action)

    elif suffix == "read_screen":
        from shogun.ronin.desktop.vision_controller import read_screen

        return await read_screen(action)

    else:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type=action.action_type,
            error=f"Unknown desktop action: 'desktop.{suffix}'",
        )


async def _route_browser(action: RoninAction, suffix: str) -> RoninResult:
    """Route browser.* actions to the Mado bridge."""
    try:
        from shogun.ronin.browser.playwright_controller import (
            browser_click,
            browser_extract,
            browser_open,
            browser_screenshot,
            browser_type,
        )
    except ImportError:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type=action.action_type,
            error="Browser controller not available",
        )

    handlers = {
        "open": browser_open,
        "click": browser_click,
        "type": browser_type,
        "extract": browser_extract,
        "screenshot": browser_screenshot,
    }

    handler = handlers.get(suffix)
    if not handler:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type=action.action_type,
            error=f"Unknown browser action: 'browser.{suffix}'",
        )

    return await handler(action)


async def _route_os(action: RoninAction, suffix: str) -> RoninResult:
    """Route os.* actions to the OS adapter."""
    try:
        from shogun.ronin.adapters import base_adapter

        adapter = base_adapter.get_adapter()
    except Exception:
        adapter = None

    if not adapter:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type=action.action_type,
            error="OS adapter not available for this platform",
        )

    if suffix == "list_windows":
        windows = adapter.list_windows()
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type=action.action_type,
            result_data={"windows": windows},
        )

    elif suffix == "active_window":
        active = adapter.get_active_window()
        return RoninResult(
            status=RoninActionStatus.SUCCESS if active else RoninActionStatus.TARGET_NOT_FOUND,
            action_type=action.action_type,
            result_data={"active_window": active},
        )

    elif suffix == "focus_window":
        success = adapter.focus_window(action.target or "")
        return RoninResult(
            status=RoninActionStatus.SUCCESS if success else RoninActionStatus.TARGET_NOT_FOUND,
            action_type=action.action_type,
            target=action.target,
        )

    elif suffix == "app_launch":
        launched = adapter.open_application(action.target or action.value or "", action.metadata.get("arguments"))
        expected_window = action.metadata.get("expected_window")
        if expected_window:
            launched["expected_window"] = expected_window
        return RoninResult(
            status=RoninActionStatus.SUCCESS, action_type=action.action_type, target=action.target, result_data=launched
        )

    elif suffix == "app_close":
        success = adapter.close_window(action.target or "")
        return RoninResult(
            status=RoninActionStatus.SUCCESS if success else RoninActionStatus.TARGET_NOT_FOUND,
            action_type=action.action_type,
            target=action.target,
        )

    elif suffix == "wait_for_window":
        from shogun.ronin.desktop.verification_service import get_verifier

        verification = await get_verifier().wait_for_window(
            action.target or "", timeout=float(action.metadata.get("timeout", 30))
        )
        return RoninResult(
            status=RoninActionStatus.SUCCESS if verification.passed else RoninActionStatus.TIMEOUT,
            action_type=action.action_type,
            target=action.target,
            verified=verification.passed,
            result_data={"verification": verification.model_dump()},
            error=None if verification.passed else verification.message,
        )

    elif suffix == "wait_for_file":
        from shogun.ronin.desktop.verification_service import get_verifier

        verification = await get_verifier().wait_for_file(
            action.target or "", timeout=float(action.metadata.get("timeout", 30))
        )
        return RoninResult(
            status=RoninActionStatus.SUCCESS if verification.passed else RoninActionStatus.TIMEOUT,
            action_type=action.action_type,
            target=action.target,
            verified=verification.passed,
            result_data={"verification": verification.model_dump()},
            error=None if verification.passed else verification.message,
        )

    elif suffix == "display_info":
        return RoninResult(
            status=RoninActionStatus.SUCCESS, action_type=action.action_type, result_data=adapter.get_display_info()
        )

    return RoninResult(
        status=RoninActionStatus.FAILED,
        action_type=action.action_type,
        error=f"Unknown OS action: 'os.{suffix}'",
    )


async def _route_ronin_internal(action: RoninAction, suffix: str) -> RoninResult:
    """Route ronin.* internal control actions."""
    if suffix == "stop":
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type=action.action_type,
            result_data={"stopped": True},
        )

    elif suffix == "harakiri":
        from shogun.ronin.core.komainu import _trigger_level3_harakiri

        _trigger_level3_harakiri("agent_requested")
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type=action.action_type,
            result_data={"harakiri": True},
        )

    return RoninResult(
        status=RoninActionStatus.FAILED,
        action_type=action.action_type,
        error=f"Unknown ronin action: 'ronin.{suffix}'",
    )


async def _route_app(action: RoninAction, suffix: str) -> RoninResult:
    """Route app.* actions (future: app-specific integrations)."""
    return RoninResult(
        status=RoninActionStatus.FAILED,
        action_type=action.action_type,
        error=f"App-specific action 'app.{suffix}' not yet implemented. Register via capabilities registry.",
    )
