"""Controlled Shogun restart orchestration.

The API process must exit gracefully so the application lifespan can close
managed browsers, schedulers, pollers, database engines, and Office workers.
The desktop launcher or deployment supervisor is responsible for starting the
replacement process after the listener has stopped.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone

import psutil

from shogun.config import PROJECT_ROOT, settings

logger = logging.getLogger("shogun.restart")

_RESTART_MARKER = PROJECT_ROOT / ".states" / "restart-requested"
_SHUTDOWN_MARKER = PROJECT_ROOT / ".states" / "shutdown-requested"
_BROWSER_PID_MARKER = PROJECT_ROOT / ".states" / "tenshu-browser.pid"
_restart_task: asyncio.Task[None] | None = None
_shutdown_task: asyncio.Task[None] | None = None


def _truthy_environment(name: str) -> bool:
    return os.environ.get(name, "").casefold() in {"1", "true", "yes", "on"}


def _write_restart_marker() -> None:
    _RESTART_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _RESTART_MARKER.write_text(
        f"pid={os.getpid()}\nrequested_at={datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )


def _write_shutdown_marker() -> None:
    _SHUTDOWN_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _SHUTDOWN_MARKER.write_text(
        f"pid={os.getpid()}\nrequested_at={datetime.now(timezone.utc).isoformat()}\n",
        encoding="utf-8",
    )


def _launch_desktop_helper() -> None:
    """Start a detached waiter for direct, non-launcher desktop sessions."""
    command = [
        sys.executable,
        "-m",
        "shogun.services.restart_helper",
        "--parent-pid",
        str(os.getpid()),
        "--project-root",
        str(PROJECT_ROOT),
    ]
    environment = os.environ.copy()
    environment.pop("SHOGUN_LAUNCHER_MANAGED", None)
    kwargs: dict = {
        "cwd": str(PROJECT_ROOT),
        "env": environment,
        "close_fds": True,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _prepare_restart_strategy() -> str:
    if settings.deployment_mode == "server":
        if not _truthy_environment("SHOGUN_RESTART_SUPERVISED"):
            raise RuntimeError(
                "This server is not configured with a restart supervisor. "
                "Restart it through the deployment platform."
            )
        return "supervisor"

    if _truthy_environment("SHOGUN_LAUNCHER_MANAGED"):
        _write_restart_marker()
        return "launcher"

    _launch_desktop_helper()
    return "helper"


def _prepare_shutdown_strategy() -> str:
    """Tell the desktop launcher to exit after the API process stops."""
    _RESTART_MARKER.unlink(missing_ok=True)
    if settings.deployment_mode == "server":
        return "server"
    if _truthy_environment("SHOGUN_LAUNCHER_MANAGED"):
        _write_shutdown_marker()
        return "launcher"
    return "direct"


def _uses_tenshu_browser_profile(process: psutil.Process) -> bool:
    expected_profile = os.path.normcase(
        os.path.abspath(str(PROJECT_ROOT / "data" / "tenshu-browser-profile"))
    )
    try:
        command = process.cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    for argument in command:
        key, separator, value = argument.partition("=")
        if separator and key.casefold() == "--user-data-dir":
            actual_profile = os.path.normcase(os.path.abspath(value.strip('"')))
            return actual_profile == expected_profile
    return False


def _managed_browser_roots() -> list[psutil.Process]:
    processes: dict[int, psutil.Process] = {}
    try:
        marker_pid = int(_BROWSER_PID_MARKER.read_text(encoding="ascii").strip())
        marker_process = psutil.Process(marker_pid)
        if _uses_tenshu_browser_profile(marker_process):
            processes[marker_pid] = marker_process
        else:
            logger.warning("Ignored stale Tenshu browser PID marker for process %d", marker_pid)
    except (OSError, ValueError, psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    # Chromium can hand an app window to an existing process and immediately
    # exit the PID returned by Popen. The unique profile argument remains a
    # safe ownership marker, so recover the managed root without matching any
    # of the operator's normal browser sessions.
    for process in psutil.process_iter(["pid", "cmdline"]):
        if _uses_tenshu_browser_profile(process):
            processes[process.pid] = process
    return list(processes.values())


def _request_windows_browser_close(processes: list[psutil.Process]) -> int:
    """Post WM_CLOSE only to windows owned by the managed browser tree."""
    if sys.platform != "win32" or not processes:
        return 0
    import ctypes

    target_pids = {process.pid for process in processes}
    closed = 0
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def close_window(window, _parameter) -> bool:
        nonlocal closed
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(window, ctypes.byref(process_id))
        if process_id.value in target_pids and user32.IsWindow(window):
            if user32.PostMessageW(window, 0x0010, 0, 0):  # WM_CLOSE
                closed += 1
        return True

    user32.EnumWindows(callback_type(close_window), 0)
    return closed


def _close_managed_browser() -> int:
    """Close only browser processes using Shogun's dedicated Tenshu profile."""
    roots = _managed_browser_roots()
    targets: dict[int, psutil.Process] = {}
    for process in roots:
        try:
            targets.update({child.pid: child for child in process.children(recursive=True)})
            targets[process.pid] = process
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    try:
        alive = list(targets.values())
        if _request_windows_browser_close(alive):
            _gone, alive = psutil.wait_procs(alive, timeout=4)
        for process in reversed(alive):
            try:
                process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if alive:
            _gone, alive = psutil.wait_procs(alive, timeout=3)
            for process in alive:
                try:
                    process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if alive:
                psutil.wait_procs(alive, timeout=2)
    finally:
        _BROWSER_PID_MARKER.unlink(missing_ok=True)
    if targets:
        logger.info("Closed %d managed Tenshu browser processes", len(targets))
    return len(targets)


async def _signal_graceful_shutdown(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    await asyncio.to_thread(_close_managed_browser)
    logger.info("Signalling graceful Shogun shutdown for restart")
    if sys.platform == "win32":
        # Uvicorn installs a SIGINT handler; raising it in-process preserves
        # lifespan cleanup unlike TerminateProcess/SIGTERM on Windows.
        signal.raise_signal(signal.SIGINT)
    else:
        os.kill(os.getpid(), signal.SIGTERM)


async def _signal_graceful_stop(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    await asyncio.to_thread(_close_managed_browser)
    logger.info("Signalling graceful Shogun shutdown")
    if sys.platform == "win32":
        signal.raise_signal(signal.SIGINT)
    else:
        os.kill(os.getpid(), signal.SIGTERM)


def request_restart(*, delay_seconds: float = 1.25) -> dict:
    """Prepare a replacement process and schedule graceful server shutdown."""
    global _restart_task
    if _restart_task is not None and not _restart_task.done():
        return {
            "accepted": True,
            "already_requested": True,
            "message": "A Shogun restart is already in progress.",
        }
    if _shutdown_task is not None and not _shutdown_task.done():
        raise RuntimeError("A Shogun shutdown is already in progress.")

    strategy = _prepare_restart_strategy()
    loop = asyncio.get_running_loop()
    _restart_task = loop.create_task(
        _signal_graceful_shutdown(delay_seconds),
        name="shogun-controlled-restart",
    )
    return {
        "accepted": True,
        "already_requested": False,
        "strategy": strategy,
        "close_browser": True,
        "browser_will_reopen": strategy in {"launcher", "helper"},
        "message": "Shogun is shutting down cleanly and will restart.",
    }


def request_shutdown(*, delay_seconds: float = 1.25) -> dict:
    """Schedule a graceful stop without starting a replacement process."""
    global _shutdown_task
    if _shutdown_task is not None and not _shutdown_task.done():
        return {
            "accepted": True,
            "already_requested": True,
            "message": "A Shogun shutdown is already in progress.",
        }
    if _restart_task is not None and not _restart_task.done():
        raise RuntimeError("A Shogun restart is already in progress.")

    strategy = _prepare_shutdown_strategy()
    loop = asyncio.get_running_loop()
    _shutdown_task = loop.create_task(
        _signal_graceful_stop(delay_seconds),
        name="shogun-controlled-shutdown",
    )
    return {
        "accepted": True,
        "already_requested": False,
        "strategy": strategy,
        "close_browser": True,
        "browser_will_reopen": False,
        "message": "Tenshu is closing managed processes and shutting down cleanly.",
    }
