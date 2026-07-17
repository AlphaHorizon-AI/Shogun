"""Base OS Adapter — abstract interface for platform-specific operations.

Each platform (Windows, macOS, Linux) implements this interface.
The get_adapter() factory returns the correct one for the current OS.
"""

from __future__ import annotations

import abc
import logging
import platform
from typing import Any

log = logging.getLogger("shogun.ronin.adapters")


class BaseOSAdapter(abc.ABC):
    """Abstract OS adapter interface."""

    @abc.abstractmethod
    def list_windows(self) -> list[dict[str, Any]]:
        """List all visible windows with title, process, and hwnd."""
        ...

    @abc.abstractmethod
    def get_active_window(self) -> dict[str, Any] | None:
        """Get the currently focused window."""
        ...

    @abc.abstractmethod
    def focus_window(self, title_or_id: str) -> bool:
        """Bring a window to the foreground. Returns True if successful."""
        ...

    @abc.abstractmethod
    def get_foreground_process(self) -> str | None:
        """Get the process name of the foreground window."""
        ...

    @abc.abstractmethod
    def get_window_controls(self, title_or_id: str) -> list[dict[str, Any]]:
        """Get UI controls/elements of a window (stub in v1)."""
        ...

    def open_application(self, application: str, arguments: list[str] | None = None) -> dict[str, Any]:
        """Launch an application without invoking a command shell."""
        raise NotImplementedError("Application launch is not supported on this platform")

    def close_window(self, title_or_id: str) -> bool:
        """Request a normal window close. Force termination is intentionally excluded."""
        return False

    def get_display_info(self) -> dict[str, Any]:
        """Return monitor and DPI metadata used for coordinate normalization."""
        return {"monitors": [], "dpi_aware": False}


def get_adapter() -> BaseOSAdapter | None:
    """Factory: return the correct OS adapter for the current platform."""
    system = platform.system()

    if system == "Windows":
        try:
            from shogun.ronin.adapters.windows_adapter import WindowsAdapter
            return WindowsAdapter()
        except ImportError as exc:
            log.debug("Windows adapter unavailable: %s", exc)

    elif system == "Darwin":
        try:
            from shogun.ronin.adapters.macos_adapter import MacOSAdapter
            return MacOSAdapter()
        except ImportError as exc:
            log.debug("macOS adapter unavailable: %s", exc)

    elif system == "Linux":
        try:
            from shogun.ronin.adapters.linux_adapter import LinuxAdapter
            return LinuxAdapter()
        except ImportError as exc:
            log.debug("Linux adapter unavailable: %s", exc)

    log.warning("Ronin: no OS adapter available for %s", system)
    return None
