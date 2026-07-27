from __future__ import annotations

import asyncio

import pytest

from shogun.services import restart_service


@pytest.fixture(autouse=True)
def reset_restart_task(monkeypatch):
    monkeypatch.setattr(restart_service, "_restart_task", None)


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

    restart_service._close_managed_browser()

    assert not marker.exists()


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
async def test_updates_api_accepts_controlled_restart(monkeypatch):
    from shogun.api import updates

    monkeypatch.setattr(
        restart_service,
        "request_restart",
        lambda: {"accepted": True, "strategy": "launcher"},
    )

    response = await updates.restart_shogun("token_admin")

    assert response == {"accepted": True, "strategy": "launcher"}
