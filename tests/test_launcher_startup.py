"""Regression coverage for standalone launcher startup behavior."""

import socket
import sys
from pathlib import Path

import pytest

from shogun import __main__ as launcher
from shogun.__main__ import _port_in_use


def test_port_in_use_detects_existing_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        assert _port_in_use("127.0.0.1", port) is True


def test_port_in_use_accepts_available_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    assert _port_in_use("127.0.0.1", port) is False


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX address reuse after an active close")
def test_port_in_use_accepts_restarting_after_a_connection() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
            connection, _address = listener.accept()
            connection.close()
            assert client.recv(1) == b""

    assert _port_in_use("127.0.0.1", port) is False


@pytest.mark.parametrize("active_name", [".venv", "venv"])
def test_launcher_keeps_active_project_venv_when_both_exist(tmp_path, monkeypatch, active_name):
    monkeypatch.setattr(launcher, "__file__", str(tmp_path / "shogun/__main__.py"))
    interpreter = Path("Scripts/python.exe") if sys.platform == "win32" else Path("bin/python")
    for name in (".venv", "venv"):
        candidate = tmp_path / name / interpreter
        candidate.parent.mkdir(parents=True)
        candidate.touch()
    monkeypatch.setattr(sys, "prefix", str(tmp_path / active_name))
    monkeypatch.setattr(launcher.os, "execve", lambda *_: pytest.fail("already inside the project venv"))
    launcher._reexec_in_project_venv()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX venv executable symlink")
def test_global_python_reexecs_even_when_venv_python_is_a_symlink(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "__file__", str(tmp_path / "shogun/__main__.py"))
    candidate = tmp_path / "venv/bin/python"
    candidate.parent.mkdir(parents=True)
    candidate.symlink_to(sys.executable)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "system-python"))
    calls = []
    monkeypatch.setattr(launcher.os, "execve", lambda *args: calls.append(args))
    launcher._reexec_in_project_venv()
    assert len(calls) == 1
    assert calls[0][0] == str(candidate)
    assert calls[0][1][:3] == [str(candidate), "-m", "shogun"]
