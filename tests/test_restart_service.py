from __future__ import annotations

import asyncio

import pytest

from shogun.services import restart_service


@pytest.fixture(autouse=True)
def reset_restart_task(monkeypatch):
    monkeypatch.setattr(restart_service, "_restart_task", None)
    monkeypatch.setattr(restart_service, "_shutdown_task", None)


def test_launcher_restart_writes_supervision_marker(monkeypatch, tmp_path):
    marker = tmp_path / ".states" / "restart-requested"
    monkeypatch.setattr(restart_service, "_RESTART_MARKER", marker)
    monkeypatch.setattr(restart_service.settings, "deployment_mode", "desktop")
    monkeypatch.setenv("SHOGUN_LAUNCHER_MANAGED", "true")

    assert restart_service._prepare_restart_strategy() == "launcher"
    assert "requested_at=" in marker.read_text(encoding="utf-8")


def test_unsupervised_server_restart_is_rejected(monkeypatch):
    monkeypatch.setattr(restart_service.settings, "deployment_mode", "server")
    monkeypatch.delenv("SHOGUN_RESTART_SUPERVISED", raising=False)

    with pytest.raises(RuntimeError, match="restart supervisor"):
        restart_service._prepare_restart_strategy()


def test_browser_pid_marker_cannot_terminate_unrelated_process(monkeypatch, tmp_path):
    marker = tmp_path / "tenshu-browser.pid"
    marker.write_text("1234", encoding="ascii")
    monkeypatch.setattr(restart_service, "_BROWSER_PID_MARKER", marker)

    class UnrelatedProcess:
        def cmdline(self):
            return ["browser.exe", "https://example.com"]

    monkeypatch.setattr("psutil.Process", lambda _pid: UnrelatedProcess())
    monkeypatch.setattr("psutil.process_iter", lambda _attrs: [])

    restart_service._close_managed_browser()

    assert not marker.exists()


def test_launcher_shutdown_writes_exit_marker_and_clears_restart(monkeypatch, tmp_path):
    restart_marker = tmp_path / ".states" / "restart-requested"
    shutdown_marker = tmp_path / ".states" / "shutdown-requested"
    restart_marker.parent.mkdir(parents=True)
    restart_marker.write_text("stale", encoding="utf-8")
    monkeypatch.setattr(restart_service, "_RESTART_MARKER", restart_marker)
    monkeypatch.setattr(restart_service, "_SHUTDOWN_MARKER", shutdown_marker)
    monkeypatch.setattr(restart_service.settings, "deployment_mode", "desktop")
    monkeypatch.setenv("SHOGUN_LAUNCHER_MANAGED", "true")

    assert restart_service._prepare_shutdown_strategy() == "launcher"
    assert not restart_marker.exists()
    assert "requested_at=" in shutdown_marker.read_text(encoding="utf-8")


def test_managed_browser_discovery_uses_exact_dedicated_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(restart_service, "PROJECT_ROOT", tmp_path)
    expected_profile = tmp_path / "data" / "tenshu-browser-profile"

    class Process:
        def __init__(self, pid, command):
            self.pid = pid
            self._command = command

        def cmdline(self):
            return self._command

    managed = Process(11, ["msedge.exe", f"--user-data-dir={expected_profile}"])
    unrelated = Process(12, ["msedge.exe", "--user-data-dir=C:\\Users\\operator\\Default"])
    monkeypatch.setattr(restart_service, "_BROWSER_PID_MARKER", tmp_path / "missing.pid")
    monkeypatch.setattr("psutil.process_iter", lambda _attrs: [managed, unrelated])

    assert restart_service._managed_browser_roots() == [managed]


@pytest.mark.asyncio
async def test_restart_request_is_idempotent(monkeypatch):
    release = asyncio.Event()

    async def pending_shutdown(_delay_seconds: float) -> None:
        await release.wait()

    monkeypatch.setattr(restart_service, "_prepare_restart_strategy", lambda: "launcher")
    monkeypatch.setattr(restart_service, "_signal_graceful_shutdown", pending_shutdown)

    first = restart_service.request_restart(delay_seconds=0)
    second = restart_service.request_restart(delay_seconds=0)

    assert first["accepted"] is True
    assert first["browser_will_reopen"] is True
    assert second["already_requested"] is True
    release.set()
    await restart_service._restart_task


@pytest.mark.asyncio
async def test_shutdown_request_is_idempotent_and_never_reopens(monkeypatch):
    release = asyncio.Event()

    async def pending_shutdown(_delay_seconds: float) -> None:
        await release.wait()

    monkeypatch.setattr(restart_service, "_prepare_shutdown_strategy", lambda: "launcher")
    monkeypatch.setattr(restart_service, "_signal_graceful_stop", pending_shutdown)

    first = restart_service.request_shutdown(delay_seconds=0)
    second = restart_service.request_shutdown(delay_seconds=0)

    assert first["accepted"] is True
    assert first["browser_will_reopen"] is False
    assert second["already_requested"] is True
    release.set()
    await restart_service._shutdown_task


@pytest.mark.asyncio
async def test_updates_api_accepts_controlled_restart(monkeypatch):
    from shogun.api import updates

    monkeypatch.setattr(
        restart_service,
        "request_restart",
        lambda: {"accepted": True, "strategy": "launcher"},
    )

    response = await updates.restart_shogun("token_admin")

    assert response == {"accepted": True, "strategy": "launcher"}


@pytest.mark.asyncio
async def test_updates_api_accepts_controlled_shutdown(monkeypatch):
    from shogun.api import updates

    monkeypatch.setattr(
        restart_service,
        "request_shutdown",
        lambda: {"accepted": True, "strategy": "launcher", "browser_will_reopen": False},
    )

    response = await updates.shutdown_shogun("token_admin")

    assert response["accepted"] is True
    assert response["browser_will_reopen"] is False


def test_desktop_launcher_exits_after_controlled_shutdown():
    content = (restart_service.PROJECT_ROOT / "start.bat").read_text(encoding="utf-8")

    shutdown_check = content.index('if exist ".states\\shutdown-requested"')
    normal_pause = content.index(":: If the server exits, keep the window open")
    assert shutdown_check < normal_pause


def test_update_ui_waits_for_backend_restart_before_loading_new_bundle():
    content = (
        restart_service.PROJECT_ROOT / "frontend" / "src" / "pages" / "Updates.tsx"
    ).read_text(encoding="utf-8")

    assert "window.location.reload()" not in content
    assert "Restart Shogun before using the updated interface." in content
