"""Mouse Controller — mouse movement, clicks, and drag via PyAutoGUI.

All calls are wrapped with the Komainu _ronin_acting context manager
to distinguish Ronin-generated input from human input.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from shogun.ronin.core.komainu import ronin_acting, set_expected_position
from shogun.ronin.policies.ronin_policy_schema import (
    RoninAction,
    RoninActionStatus,
    RoninResult,
)

log = logging.getLogger("shogun.ronin.desktop.mouse")

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ronin-mouse")


def _get_pyautogui():
    """Lazy import pyautogui with safety settings."""
    import pyautogui
    pyautogui.FAILSAFE = True  # Move to corner to abort
    pyautogui.PAUSE = 0.05     # Small delay between actions
    return pyautogui


def _parse_coords(action: RoninAction) -> tuple[int, int] | None:
    """Extract (x, y) coordinates from action target or metadata."""
    meta = action.metadata or {}
    x = meta.get("x")
    y = meta.get("y")
    if x is not None and y is not None:
        return int(x), int(y)

    # Try parsing target as "x,y"
    if action.target and "," in action.target:
        try:
            parts = action.target.split(",")
            return int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            pass
    return None


async def move_mouse(action: RoninAction) -> RoninResult:
    """Move the mouse cursor to a position."""
    coords = _parse_coords(action)
    if not coords:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.move_mouse",
            error="No coordinates provided. Use metadata.x/y or target='x,y'",
        )

    x, y = coords
    duration = action.metadata.get("duration", 0.3) if action.metadata else 0.3

    try:
        def _do():
            pag = _get_pyautogui()
            with ronin_acting(expected_pos=(x, y)):
                pag.moveTo(x, y, duration=duration)
            set_expected_position(x, y)

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type="desktop.move_mouse",
            target=f"{x},{y}",
            result_data={"x": x, "y": y},
        )
    except ImportError:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.move_mouse",
            error="pyautogui not installed. Install with: pip install pyautogui",
        )
    except Exception as exc:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.move_mouse",
            error=str(exc),
        )


async def click(action: RoninAction) -> RoninResult:
    """Click at a position."""
    coords = _parse_coords(action)
    if not coords:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.click",
            error="No coordinates provided. Use metadata.x/y or target='x,y'",
        )

    x, y = coords
    button = action.metadata.get("button", "left") if action.metadata else "left"

    try:
        def _do():
            pag = _get_pyautogui()
            log.info(f"[Ronin Mouse] Smooth glide to ({x}, {y}) — duration=0.8s")
            with ronin_acting(expected_pos=(x, y)):
                # Smooth glide to target so the user can follow the cursor
                pag.moveTo(x, y, duration=0.8)
                import time
                time.sleep(0.1)  # brief pause before click for visual clarity
                pag.click(button=button)
            set_expected_position(x, y)
            log.info(f"[Ronin Mouse] Clicked at ({x}, {y})")

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type="desktop.click",
            target=f"{x},{y}",
            result_data={"x": x, "y": y, "button": button},
        )
    except ImportError:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.click",
            error="pyautogui not installed",
        )
    except Exception as exc:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.click",
            error=str(exc),
        )


async def double_click(action: RoninAction) -> RoninResult:
    """Double-click at a position."""
    coords = _parse_coords(action)
    if not coords:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.double_click",
            error="No coordinates provided",
        )

    x, y = coords
    try:
        def _do():
            pag = _get_pyautogui()
            log.info(f"[Ronin Mouse] Smooth glide to ({x}, {y}) for double-click")
            with ronin_acting(expected_pos=(x, y)):
                pag.moveTo(x, y, duration=0.8)
                import time
                time.sleep(0.1)
                pag.doubleClick(button='left')
            set_expected_position(x, y)

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type="desktop.double_click",
            target=f"{x},{y}",
        )
    except Exception as exc:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.double_click", error=str(exc))


async def right_click(action: RoninAction) -> RoninResult:
    """Right-click at a position."""
    coords = _parse_coords(action)
    if not coords:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.right_click", error="No coordinates")

    x, y = coords
    try:
        def _do():
            pag = _get_pyautogui()
            with ronin_acting(expected_pos=(x, y)):
                pag.moveTo(x, y, duration=0.4)
                pag.rightClick()
            set_expected_position(x, y)

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(status=RoninActionStatus.SUCCESS, action_type="desktop.right_click", target=f"{x},{y}")
    except Exception as exc:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.right_click", error=str(exc))


async def drag(action: RoninAction) -> RoninResult:
    """Drag from current position to target position."""
    coords = _parse_coords(action)
    if not coords:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.drag", error="No target coordinates")

    x, y = coords
    duration = action.metadata.get("duration", 0.5) if action.metadata else 0.5
    start_x = action.metadata.get("start_x") if action.metadata else None
    start_y = action.metadata.get("start_y") if action.metadata else None

    try:
        def _do():
            pag = _get_pyautogui()
            with ronin_acting(expected_pos=(x, y)):
                if start_x is not None and start_y is not None:
                    pag.moveTo(int(start_x), int(start_y), duration=0.25)
                pag.dragTo(x, y, duration=duration)
            set_expected_position(x, y)

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(status=RoninActionStatus.SUCCESS, action_type="desktop.drag", target=f"{x},{y}", result_data={"from": [start_x, start_y], "to": [x, y]})
    except Exception as exc:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.drag", error=str(exc))


async def scroll(action: RoninAction) -> RoninResult:
    """Scroll the mouse wheel."""
    clicks = action.metadata.get("clicks", 3) if action.metadata else 3

    try:
        def _do():
            pag = _get_pyautogui()
            with ronin_acting():
                pag.scroll(clicks)

        await asyncio.get_event_loop().run_in_executor(_executor, _do)
        return RoninResult(
            status=RoninActionStatus.SUCCESS,
            action_type="desktop.scroll",
            result_data={"clicks": clicks},
        )
    except Exception as exc:
        return RoninResult(status=RoninActionStatus.FAILED, action_type="desktop.scroll", error=str(exc))
