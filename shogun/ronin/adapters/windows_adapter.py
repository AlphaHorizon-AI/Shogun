"""Windows OS Adapter — v1: basic get_foreground_process via ctypes.

Full pywinauto integration deferred to v2.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

from shogun.ronin.adapters.base_adapter import BaseOSAdapter

log = logging.getLogger("shogun.ronin.adapters.windows")


class WindowsAdapter(BaseOSAdapter):
    """Windows-specific OS adapter."""

    def list_windows(self) -> list[dict[str, Any]]:
        """List visible windows (stub — returns empty in v1)."""
        # TODO: implement via pywinauto or EnumWindows
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            windows: list[dict[str, Any]] = []

            def _enum_callback(hwnd, _):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        title = buf.value
                        if title.strip():
                            windows.append(
                                {
                                    "hwnd": hwnd,
                                    "title": title,
                                    "process": self._get_process_name_for_hwnd(hwnd),
                                }
                            )
                return True

            window_enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            user32.EnumWindows(window_enum_proc(_enum_callback), 0)
            return windows
        except Exception as exc:
            log.debug("Windows: list_windows failed: %s", exc)
            return []

    def get_active_window(self) -> dict[str, Any] | None:
        """Get the currently focused window."""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                length = user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                return {
                    "hwnd": hwnd,
                    "title": buf.value,
                    "process": self._get_process_name_for_hwnd(hwnd),
                }
        except Exception as exc:
            log.debug("Windows: get_active_window failed: %s", exc)
        return None

    def focus_window(self, title_or_id: str) -> bool:
        """Bring a matching visible window to the foreground."""
        try:
            import ctypes

            user32 = ctypes.windll.user32
            target = str(title_or_id).strip().lower()
            for window in self.list_windows():
                if target == str(window.get("hwnd")) or target in str(window.get("title", "")).lower():
                    hwnd = int(window["hwnd"])
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    return bool(user32.SetForegroundWindow(hwnd))
        except Exception as exc:
            log.debug("Windows: focus_window failed: %s", exc)
        return False

    def open_application(self, application: str, arguments: list[str] | None = None) -> dict[str, Any]:
        """Launch a Windows application with shell parsing disabled."""
        application = application.strip()
        if not application:
            raise ValueError("Application is required")
        args = [application, *(arguments or [])]
        try:
            process = subprocess.Popen(args, shell=False)
            return {"pid": process.pid, "application": application}
        except FileNotFoundError:
            if arguments:
                raise
            os.startfile(application)  # type: ignore[attr-defined]
            return {"pid": None, "application": application}

    def close_window(self, title_or_id: str) -> bool:
        try:
            import ctypes

            target = str(title_or_id).strip().lower()
            for window in self.list_windows():
                if target == str(window.get("hwnd")) or target in str(window.get("title", "")).lower():
                    return bool(ctypes.windll.user32.PostMessageW(int(window["hwnd"]), 0x0010, 0, 0))
        except Exception as exc:
            log.debug("Windows: close_window failed: %s", exc)
        return False

    def get_display_info(self) -> dict[str, Any]:
        try:
            import ctypes

            user32 = ctypes.windll.user32
            try:
                user32.SetProcessDpiAwarenessContext(-4)  # per-monitor aware v2
            except Exception:
                pass
            return {
                "virtual_screen": {
                    "left": user32.GetSystemMetrics(76),
                    "top": user32.GetSystemMetrics(77),
                    "width": user32.GetSystemMetrics(78),
                    "height": user32.GetSystemMetrics(79),
                },
                "primary": {
                    "width": user32.GetSystemMetrics(0),
                    "height": user32.GetSystemMetrics(1),
                },
                "dpi_aware": True,
            }
        except Exception:
            return {"monitors": [], "dpi_aware": False}

    def get_foreground_process(self) -> str | None:
        """Get the process name of the foreground window."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None

            # Get PID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

            if not pid.value:
                return None

            # Open process and get name
            process_query_information = 0x0400
            process_vm_read = 0x0010

            handle = kernel32.OpenProcess(
                process_query_information | process_vm_read,
                False,
                pid.value,
            )
            if not handle:
                return None

            try:
                # Try GetProcessImageFileName via psapi
                psapi = ctypes.windll.psapi
                buf = ctypes.create_unicode_buffer(260)
                psapi.GetProcessImageFileNameW(handle, buf, 260)
                path = buf.value
                if path:
                    # Extract filename from path (e.g. \Device\...\code.exe → code.exe)
                    return path.rsplit("\\", 1)[-1] if "\\" in path else path
            finally:
                kernel32.CloseHandle(handle)

        except Exception as exc:
            log.debug("Windows: get_foreground_process failed: %s", exc)
        return None

    def get_window_controls(self, title_or_id: str) -> list[dict[str, Any]]:
        """Get UI controls (stub — deferred to v2 with pywinauto)."""
        return []

    def _get_process_name_for_hwnd(self, hwnd: int) -> str | None:
        """Get process name for a window handle."""
        try:
            import ctypes
            from ctypes import wintypes

            pid = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                handle = ctypes.windll.kernel32.OpenProcess(0x0410, False, pid.value)
                if handle:
                    try:
                        buf = ctypes.create_unicode_buffer(260)
                        ctypes.windll.psapi.GetProcessImageFileNameW(handle, buf, 260)
                        path = buf.value
                        if path:
                            return path.rsplit("\\", 1)[-1]
                    finally:
                        ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            pass
        return None
