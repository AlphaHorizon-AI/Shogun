"""Regression coverage for standalone launcher startup behavior."""

import socket

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
