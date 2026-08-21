from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import Request, Response

from shogun.api.control_plane_auth import enforce_control_plane_access
from shogun.api.infrastructure_auth import INFRASTRUCTURE_TOKEN_HEADER
from shogun.config import settings
from shogun.environment_bootstrap import (
    build_desktop_browser_url,
    ensure_desktop_environment,
)
from shogun.telemetry.models import EventType
from shogun.telemetry.payload import build_event

ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = {
    "SECRET_KEY",
    "VAULT_ENCRYPTION_KEY",
    "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN",
    "A2A_ENCRYPTION_KEY",
}


def _values(path: Path) -> dict[str, str]:
    return {
        key: value
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.lstrip().startswith("#") and "=" in line
        for key, value in (line.split("=", 1),)
    }


def _request(token: str = "") -> Request:
    headers = []
    if token:
        headers.append((INFRASTRUCTURE_TOKEN_HEADER.lower().encode(), token.encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/setup/status",
            "raw_path": b"/api/v1/setup/status",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 51234),
            "server": ("127.0.0.1", 8000),
        }
    )


def test_clean_desktop_bootstrap_generates_independent_strong_secrets(tmp_path: Path):
    (tmp_path / ".env.example").write_text(
        "API_HOST=0.0.0.0\n"
        "SECRET_KEY=change-me\n"
        "VAULT_ENCRYPTION_KEY=\n"
        "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=too-short\n",
        encoding="utf-8",
    )

    env_path, created = ensure_desktop_environment(tmp_path)
    values = _values(env_path)

    assert created is True
    assert values["API_HOST"] == "127.0.0.1"
    assert SECRET_KEYS <= values.keys()
    secrets = [values[key] for key in SECRET_KEYS]
    assert all(len(value) >= 64 for value in secrets)
    assert len(set(secrets)) == len(secrets)
    assert "change-me" not in env_path.read_text(encoding="utf-8").casefold()
    if os.name != "nt":
        assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


def test_desktop_bootstrap_preserves_an_existing_strong_token(tmp_path: Path):
    token = "existing-private-token-" + "x" * 48
    (tmp_path / ".env").write_text(
        f"SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN={token}\n",
        encoding="utf-8",
    )

    env_path, created = ensure_desktop_environment(tmp_path)

    assert created is False
    assert _values(env_path)["SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN"] == token


def test_desktop_bootstrap_cli_never_prints_the_generated_token(tmp_path: Path):
    (tmp_path / ".env.example").write_text(
        "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=change-me\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "shogun.environment_bootstrap",
            "--root",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    token = _values(tmp_path / ".env")["SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN"]

    assert completed.stderr == ""
    assert completed.stdout.strip() == "Shogun desktop environment is ready."
    assert token not in completed.stdout


def test_desktop_browser_url_confines_encoded_token_to_fragment():
    token = "z" * 40 + "+/?#&="
    result = build_desktop_browser_url("http://localhost:8000/setup", token)
    parsed = urlsplit(result)

    assert parsed.path == "/setup"
    assert parsed.query == ""
    assert parse_qs(parsed.fragment) == {"infrastructure_token": [token]}
    assert token not in result
    assert "?infrastructure_token=" not in result


@pytest.mark.parametrize(
    "url",
    (
        "https://external.example/setup",
        "http://0.0.0.0:8000/setup",
        "http://user@localhost:8000/setup",
        "http://localhost:99999/setup",
    ),
)
def test_desktop_browser_url_rejects_non_loopback_or_ambiguous_origins(url: str):
    with pytest.raises(ValueError):
        build_desktop_browser_url(url, "z" * 40)


@pytest.mark.parametrize(
    "url",
    (
        "http://localhost:8000/setup",
        "http://127.0.0.1:8000/setup",
        "http://[::1]:8000/setup",
    ),
)
def test_desktop_browser_url_accepts_only_loopback_origins(url: str):
    parsed = urlsplit(build_desktop_browser_url(url, "z" * 40))
    assert parsed.hostname in {"localhost", "127.0.0.1", "::1"}


@pytest.mark.asyncio
async def test_generated_token_authorizes_real_desktop_control_plane_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    env_path, _created = ensure_desktop_environment(tmp_path)
    token = _values(env_path)["SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN"]
    monkeypatch.setattr(settings, "deployment_mode", "desktop")
    monkeypatch.setattr(settings, "infrastructure_admin_token", token)

    async def accepted(_request: Request) -> Response:
        return Response(status_code=204)

    missing = await enforce_control_plane_access(_request(), accepted)
    authorized = await enforce_control_plane_access(_request(token), accepted)

    assert missing.status_code == 401
    assert authorized.status_code == 204


def test_infrastructure_token_is_excluded_from_installation_telemetry(
    monkeypatch: pytest.MonkeyPatch,
):
    token = "telemetry-must-not-contain-" + "s" * 48
    monkeypatch.setattr(settings, "infrastructure_admin_token", token)

    payload = build_event(EventType.INSTALL_COMPLETED).model_dump(
        mode="json",
        exclude_none=True,
    )

    assert token not in json.dumps(payload)
    assert "infrastructure_admin_token" not in payload


def test_desktop_installers_bootstrap_privately_and_launch_via_python():
    windows_outer = (ROOT / "Shogun-Install.bat").read_text(encoding="utf-8")
    unix_outer = (ROOT / "Shogun-Install.command").read_text(encoding="utf-8")
    windows = (ROOT / "install.bat").read_text(encoding="utf-8")
    unix = (ROOT / "install.sh").read_text(encoding="utf-8")
    windows_start = (ROOT / "start.bat").read_text(encoding="utf-8")
    unix_start = (ROOT / "start.sh").read_text(encoding="utf-8")
    bootstrap = (ROOT / "shogun" / "environment_bootstrap.py").read_text(
        encoding="utf-8"
    )

    assert "call install.bat" in windows_outer
    assert "bash install.sh" in unix_outer
    assert "python -m shogun.environment_bootstrap" in windows
    assert "$PYTHON_CMD -m shogun.environment_bootstrap" in unix
    assert windows.index("python -m shogun.environment_bootstrap") < windows.index(
        "python -m shogun.telemetry.cli"
    )
    assert unix.index("shogun.environment_bootstrap") < unix.index(
        "shogun.telemetry.cli"
    )
    assert '--root "%CD%" >nul 2>&1' in windows
    assert '--root "$(pwd)" >/dev/null' in unix
    assert "umask 077" in unix
    assert "chmod 600 .env" in unix
    for sid in ("S-1-5-18", "S-1-5-32-544"):
        assert sid in bootstrap
    assert "WindowsIdentity]::GetCurrent().User.Value" in bootstrap

    for launcher in (windows, unix, windows_start, unix_start):
        assert "SHOGUN_BROWSER_URL=http://localhost:8000" in launcher
        assert "python -m shogun" in launcher or "$PYTHON_CMD -m shogun" in launcher
    assert 'start "" "http://localhost:8000"' not in windows_start
    assert 'open "http://localhost:8000' not in unix
    assert 'xdg-open "http://localhost:8000' not in unix
    assert 'open "http://localhost:8000' not in unix_start
    assert 'xdg-open "http://localhost:8000' not in unix_start
