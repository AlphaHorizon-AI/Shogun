"""Detached waiter used when Shogun was started without its launcher."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import psutil


def _wait_for_parent(parent_pid: int, timeout_seconds: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while psutil.pid_exists(parent_pid) and time.monotonic() < deadline:
        time.sleep(0.25)
    return not psutil.pid_exists(parent_pid)


def _start_launcher(project_root: Path) -> None:
    if sys.platform == "win32":
        launcher = project_root / "start.bat"
        subprocess.Popen(
            ["cmd.exe", "/c", str(launcher)],
            cwd=str(project_root),
            creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        return

    launcher = project_root / "start.sh"
    subprocess.Popen(
        ["bash", str(launcher)],
        cwd=str(project_root),
        start_new_session=True,
        close_fds=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    arguments = parser.parse_args()
    if _wait_for_parent(arguments.parent_pid):
        _start_launcher(arguments.project_root.resolve())


if __name__ == "__main__":
    main()
