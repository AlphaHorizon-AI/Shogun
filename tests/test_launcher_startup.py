"""Regression coverage for standalone launcher startup behavior."""

import socket

import shogun.__main__ as shogun_main
from shogun.__main__ import _port_in_use


def test_server_mode_does_not_touch_dotenv(monkeypatch) -> None:
    """Immutable server containers must use their injected environment."""
    monkeypatch.setenv("DEPLOYMENT_MODE", "server")

    def fail_if_called(*_args, **_kwargs) -> None:
        raise AssertionError("server mode attempted to rewrite .env")

    monkeypatch.setattr(shogun_main, "_secure_env_file", fail_if_called)

    shogun_main._ensure_env_file()


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
