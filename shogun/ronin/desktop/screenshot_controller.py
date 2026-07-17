"""Screenshot Controller — cross-platform desktop screenshot capture.

Uses `mss` for fast, dependency-light screenshots.
Saves to data/ronin/screenshots/ with timestamps.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shogun.ronin.policies.ronin_policy_schema import (
    RoninAction,
    RoninActionStatus,
    RoninResult,
)

log = logging.getLogger("shogun.ronin.desktop.screenshot")


def _get_screenshots_dir() -> Path:
    """Get the screenshots directory, creating it if needed."""
    from shogun.config import settings
    ronin_path = getattr(settings, "ronin_path", None)
    if ronin_path:
        screenshots_dir = Path(ronin_path) / "screenshots"
    else:
        from shogun.config import PROJECT_ROOT
        screenshots_dir = PROJECT_ROOT / "data" / "ronin" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


async def take_screenshot(action: RoninAction) -> RoninResult:
    """Take a desktop screenshot — Ronin action handler."""
    try:
        metadata = action.metadata or {}
        path = await take_screenshot_raw(
            prefix=str(metadata.get("prefix", "ronin")),
            region=metadata.get("region"),
            monitor=int(metadata.get("monitor", 0)),
        )
        if path:
            return RoninResult(
                status=RoninActionStatus.SUCCESS,
                action_type="desktop.screenshot",
                result_data={"screenshot_path": path, "filename": Path(path).name},
            )
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.screenshot",
            error="Screenshot capture returned None",
        )
    except ImportError:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.screenshot",
            error="mss not installed. Install with: pip install mss",
        )
    except Exception as exc:
        return RoninResult(
            status=RoninActionStatus.FAILED,
            action_type="desktop.screenshot",
            error=f"Screenshot failed: {exc}",
        )


async def take_screenshot_raw(
    *,
    prefix: str = "screen",
    region: dict[str, int] | None = None,
    monitor: int = 0,
) -> str | None:
    """Take a screenshot and return the file path.

    Args:
        prefix: Filename prefix (e.g. "before", "after", "approval")
        region: Optional dict with top, left, width, height for region capture
        monitor: Monitor index (0 = all monitors)

    Returns the absolute path to the saved screenshot, or None on failure.
    """
    try:
        import mss
        import mss.tools
    except ImportError:
        log.warning("Ronin: mss not installed — screenshot unavailable")
        return None

    try:
        screenshots_dir = _get_screenshots_dir()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{prefix}_{timestamp}.png"
        filepath = screenshots_dir / filename

        with mss.mss() as sct:
            if region:
                monitor_area = {
                    "top": region.get("top", 0),
                    "left": region.get("left", 0),
                    "width": region.get("width", 1920),
                    "height": region.get("height", 1080),
                }
            else:
                # Use specified monitor or primary
                monitors = sct.monitors
                if monitor < len(monitors):
                    monitor_area = monitors[monitor]
                else:
                    monitor_area = monitors[0]

            screenshot = sct.grab(monitor_area)
            mss.tools.to_png(screenshot.rgb, screenshot.size, output=str(filepath))

        log.debug("Ronin: screenshot saved → %s", filepath)
        return str(filepath)

    except Exception as exc:
        log.error("Ronin: screenshot capture failed: %s", exc)
        return None
