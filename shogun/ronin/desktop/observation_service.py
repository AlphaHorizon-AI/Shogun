"""Desktop observation and session telemetry for governed Ronin actions."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shogun.ronin.adapters.base_adapter import get_adapter
from shogun.ronin.desktop.screenshot_controller import take_screenshot_raw


class DesktopObservationService:
    """Captures desktop state and exposes a bounded operator timeline."""

    def __init__(self) -> None:
        self._timeline: deque[dict[str, Any]] = deque(maxlen=250)
        self._last_state: dict[str, Any] = {}
        self._next_action: dict[str, Any] | None = None
        self._retry_count = 0
        self._verification: dict[str, Any] | None = None
        self._paused_reason: str | None = None

    async def capture_state(self, *, screenshot: bool = True, prefix: str = "state") -> dict[str, Any]:
        adapter = get_adapter()
        active = adapter.get_active_window() if adapter else None
        windows = adapter.list_windows() if adapter else []
        screenshot_path = await take_screenshot_raw(prefix=prefix) if screenshot else None
        state = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "active_window": active,
            "windows": windows,
            "screenshot_path": screenshot_path,
            "screenshot_url": self.screenshot_url(screenshot_path),
        }
        self._last_state = state
        return state

    def record(self, event: str, message: str, **detail: Any) -> dict[str, Any]:
        item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "message": message,
            **detail,
        }
        self._timeline.append(item)
        return item

    def set_next_action(self, action: dict[str, Any] | None) -> None:
        self._next_action = action

    def set_retry_count(self, count: int) -> None:
        self._retry_count = count

    def set_verification(self, verification: dict[str, Any] | None) -> None:
        self._verification = verification

    def pause(self, reason: str) -> None:
        self._paused_reason = reason
        self.record("ronin.desktop.paused", reason)

    def resume(self) -> None:
        self._paused_reason = None

    def get_runtime_state(self) -> dict[str, Any]:
        return {
            **self._last_state,
            "next_action": self._next_action,
            "retry_count": self._retry_count,
            "verification": self._verification,
            "paused": self._paused_reason is not None,
            "paused_reason": self._paused_reason,
            "timeline": list(reversed(self._timeline)),
        }

    @staticmethod
    def screenshot_url(path: str | None) -> str | None:
        if not path:
            return None
        return f"/ronin/screenshots/{Path(path).name}"


_observer = DesktopObservationService()


def get_observer() -> DesktopObservationService:
    return _observer
