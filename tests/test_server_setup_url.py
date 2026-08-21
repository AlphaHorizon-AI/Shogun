from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from shogun.setup_link import build_server_setup_url

ROOT = Path(__file__).resolve().parents[1]


def test_setup_link_keeps_encoded_token_in_fragment_only():
    token = "a" * 32 + "+/?#&="

    setup_url = build_server_setup_url(token, "https://admin.example.test:8443")
    parsed = urlsplit(setup_url)

    assert parsed.scheme == "https"
    assert parsed.netloc == "admin.example.test:8443"
    assert parsed.path == "/setup"
    assert parsed.query == ""
    assert parse_qs(parsed.fragment) == {"infrastructure_token": [token]}
    assert token not in setup_url
    assert "?infrastructure_token=" not in setup_url


@pytest.mark.parametrize(
    "origin",
    (
        "ftp://127.0.0.1:8000",
        "http://operator:secret@127.0.0.1:8000",
        "http://127.0.0.1:8000/nested",
        "http://127.0.0.1:8000?token=leak",
        "http://127.0.0.1:8000#old-fragment",
        "http://127.0.0.1:99999",
    ),
)
def test_setup_link_rejects_non_origin_input(origin: str):
    with pytest.raises(ValueError, match="setup origin"):
        build_server_setup_url("a" * 32, origin)


@pytest.mark.parametrize(
    "token",
    ("", "too-short", "change-me-token" + "x" * 32, "a" * 32 + "\nsecret", "a" * 32 + "🔑"),
)
def test_setup_link_rejects_missing_or_bootstrap_token_without_echoing_it(token: str):
    with pytest.raises(ValueError, match="configured infrastructure administrator token") as error:
        build_server_setup_url(token)

    if token:
        assert token not in str(error.value)


def test_setup_link_cli_reads_token_from_environment_not_command_line():
    token = "b" * 48
    environment = os.environ.copy()
    environment["SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN"] = token

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "shogun.setup_link",
            "--origin",
            "http://127.0.0.1:8123",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stderr == ""
    assert completed.stdout.strip() == (
        f"http://127.0.0.1:8123/setup#infrastructure_token={token}"
    )
