from __future__ import annotations

import json

import pytest

from shogun.config import settings
from shogun.services import update_checker


def test_update_token_is_encrypted_at_rest(tmp_path, monkeypatch):
    credential_path = tmp_path / "update_credentials.json"
    monkeypatch.setattr(update_checker, "_credential_file", lambda: credential_path)
    monkeypatch.setattr(settings, "github_token", None)

    update_checker.save_update_token("github-secret-token")

    stored = credential_path.read_text(encoding="utf-8")
    assert "github-secret-token" not in stored
    assert update_checker.get_update_token() == "github-secret-token"
    assert json.loads(stored)["github_token"]


@pytest.mark.asyncio
async def test_check_uses_build_number_to_offer_in_place_update(monkeypatch):
    async def remote():
        return {
            "version": "1.6.0",
            "build": 36,
            "released": "2026-07-06T13:00:00Z",
            "changelog": "Updater repaired",
        }

    monkeypatch.setattr(
        update_checker,
        "_get_local_version",
        lambda: {"version": "1.5.5", "build": 35},
    )
    monkeypatch.setattr(update_checker, "_fetch_remote_version", remote)
    monkeypatch.setattr(update_checker, "update_token_configured", lambda: False)
    update_checker._cached_result = None
    update_checker._last_check = None

    result = await update_checker.check_for_updates(force=True)

    assert result["update_available"] is True
    assert result["remote_build"] == 36
    assert result["changelog"] == "Updater repaired"


@pytest.mark.asyncio
async def test_private_repository_error_requests_access_token(monkeypatch):
    class Response:
        status_code = 404

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(update_checker, "get_update_token", lambda: "")
    monkeypatch.setattr(update_checker.httpx, "AsyncClient", lambda **_kwargs: Client())

    assert await update_checker._fetch_remote_version() is None
    assert update_checker._last_fetch_error["auth_required"] is True


@pytest.mark.asyncio
async def test_structured_release_notes_are_bounded_and_malformed_values_are_ignored(monkeypatch):
    async def remote():
        return {
            "version": "1.6.0",
            "build": 36,
            "security_changes": ["  safe note  ", 42, "", "x" * 700],
            "breaking_changes": {"not": "a list"},
        }

    monkeypatch.setattr(
        update_checker,
        "_get_local_version",
        lambda: {"version": "1.5.5", "build": 35},
    )
    monkeypatch.setattr(update_checker, "_fetch_remote_version", remote)
    monkeypatch.setattr(update_checker, "update_token_configured", lambda: False)
    update_checker._cached_result = None
    update_checker._last_check = None

    result = await update_checker.check_for_updates(force=True)

    assert result["security_changes"] == ["safe note", "x" * 500]
    assert result["breaking_changes"] == []
