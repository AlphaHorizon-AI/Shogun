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
_BROWSER_PID_MARKER = PROJECT_ROOT / ".states" / "tenshu-browser.pid"
_restart_task: asyncio.Task[None] | None = None


def _truthy_environment(name: str) -> bool:
    return os.environ.get(name, "").casefold() in {"1", "true", "yes", "on"}


def _write_restart_marker() -> None:
    _RESTART_MARKER.parent.mkdir(parents=True, exist_ok=True)
    _RESTART_MARKER.write_text(
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


def _close_managed_browser() -> None:
    """Close only the dedicated Tenshu browser tree created by the launcher."""
    try:
        pid = int(_BROWSER_PID_MARKER.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return
    try:
        process = psutil.Process(pid)
        command = " ".join(process.cmdline()).casefold()
        expected_profile = str(PROJECT_ROOT / "data" / "tenshu-browser-profile").casefold()
        if expected_profile not in command:
            logger.warning("Ignored stale Tenshu browser PID marker for process %d", pid)
            return
        descendants = process.children(recursive=True)
        for child in reversed(descendants):
            child.terminate()
        process.terminate()
        psutil.wait_procs([*descendants, process], timeout=3)
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
        logger.debug("Managed Tenshu browser process was already closed", exc_info=True)
    finally:
        _BROWSER_PID_MARKER.unlink(missing_ok=True)


async def _signal_graceful_shutdown(delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    _close_managed_browser()
    logger.info("Signalling graceful Shogun shutdown for restart")
    if sys.platform == "win32":
        # Uvicorn installs a SIGINT handler; raising it in-process preserves
        # lifespan cleanup unlike TerminateProcess/SIGTERM on Windows.
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
