from __future__ import annotations

import asyncio

import pytest

from shogun.api import benchmark
from shogun.services.ide_service import IDEService


class FakeProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.terminated = False
        self.killed = False

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    async def wait(self) -> int:
        return int(self.returncode or 0)


class FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    async def close(self, *, code: int, reason: str) -> None:
        assert code == 4001
        assert reason
        self.closed = True


@pytest.mark.asyncio
async def test_ide_shutdown_stops_owned_processes_and_connections() -> None:
    service = IDEService()
    process = FakeProcess()
    socket = FakeSocket()
    pending = asyncio.get_running_loop().create_future()
    service.active_processes["task"] = process
    service.connections["editor"] = socket
    service.pending["request"] = pending

    assert await service.shutdown_runtime() == 1
    assert process.terminated is True
    assert process.killed is False
    assert socket.closed is True
    assert pending.cancelled()
    assert not service.active_processes
    assert not service.connections


@pytest.mark.asyncio
async def test_benchmark_shutdown_stops_owned_processes(monkeypatch) -> None:
    process = FakeProcess()
    monkeypatch.setattr(benchmark, "_processes", {"run": process})

    assert await benchmark.shutdown_benchmark_runs() == 1
    assert process.terminated is True
    assert process.killed is False
    assert not benchmark._processes
