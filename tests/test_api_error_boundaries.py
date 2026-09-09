"""Public OAuth and restore errors must not reflect diagnostics or executable HTML."""

from __future__ import annotations

import io
import json
import uuid
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from shogun.api import agents, backups, model_providers
from shogun.api.deps import get_db
from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.services import complete_backup_service, restart_service
from shogun.services.provider_oauth import ProviderOAuthError


class _OAuthPage(HTMLParser):
    def __init__(self, body: str):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.result = {}
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        self.elements.append(tag)
        attributes = dict(attrs)
        if attributes.get("id") == "oauth-result":
            self.result = attributes


@pytest.fixture
def api_boundary_app():
    app = FastAPI()
    app.include_router(model_providers.provider_router)
    app.include_router(backups.router)
    database = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[require_infrastructure_admin] = lambda: "test-admin"
    return app, database


async def _callback(app, **params):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/model-providers/oauth/callback", params={"state": "s" * 32, **params})


async def test_oauth_callback_does_not_reflect_provider_error(api_boundary_app, monkeypatch):
    app, database = api_boundary_app
    private_error = "</script><script>alert('callback-secret')</script><img src=x onerror=alert(1)>"
    recorded = []
    provider_id = uuid.uuid4()

    def reject(state, message):
        recorded.append((state, message))
        return provider_id, "https://shogun.example"

    monkeypatch.setattr(model_providers, "reject_provider_oauth", reject)
    response = await _callback(app, error=private_error)

    assert response.status_code == 200
    assert "callback-secret" not in response.text
    page = _OAuthPage(response.text)
    assert page.elements.count("script") == 1
    assert "img" not in page.elements
    payload = json.loads(page.result["data-payload"])
    assert payload["status"] == "error"
    assert payload["providerId"] == str(provider_id)
    assert page.result["data-target"] == "https://shogun.example"
    assert recorded == [("s" * 32, payload["message"])]
    database.commit.assert_not_awaited()


@pytest.mark.parametrize("failure_stage", ["reject", "exchange", "commit"])
async def test_oauth_callback_hides_exception_details(api_boundary_app, monkeypatch, failure_stage):
    app, database = api_boundary_app
    private_error = "credential=oauth-secret at /private/shogun/provider.json"
    provider = SimpleNamespace(id=uuid.uuid4())

    def reject(*_args):
        raise ProviderOAuthError(private_error)

    exchange = AsyncMock(return_value=(provider, "https://shogun.example"))
    if failure_stage == "exchange":
        exchange.side_effect = ProviderOAuthError(private_error)
    if failure_stage == "commit":
        database.commit.side_effect = RuntimeError(private_error)
    monkeypatch.setattr(model_providers, "reject_provider_oauth", reject)
    monkeypatch.setattr(model_providers, "complete_provider_oauth", exchange)
    response = await _callback(app, **({"error": "access_denied"} if failure_stage == "reject" else {"code": "code"}))

    assert response.status_code == 200
    assert "oauth-secret" not in response.text
    assert "/private/shogun" not in response.text
    assert json.loads(_OAuthPage(response.text).result["data-payload"])["status"] == "error"
    if failure_stage != "reject":
        database.rollback.assert_awaited_once()


async def test_oauth_success_encodes_page_data_and_commits_before_accepting(api_boundary_app, monkeypatch):
    app, database = api_boundary_app
    provider = SimpleNamespace(id=uuid.uuid4())
    # Even a malformed service result cannot become an HTML element or script.
    origin = "https://example.invalid/'></div><script>alert(1)</script>"
    monkeypatch.setattr(model_providers, "complete_provider_oauth", AsyncMock(return_value=(provider, origin)))
    accepted = []

    def accept(state):
        database.commit.assert_awaited_once()
        accepted.append(state)

    monkeypatch.setattr(model_providers, "accept_provider_oauth", accept)
    response = await _callback(app, code="authorization-code")

    page = _OAuthPage(response.text)
    assert page.elements.count("script") == 1
    assert page.result["data-target"] == origin
    assert json.loads(page.result["data-payload"])["status"] == "success"
    assert accepted == ["s" * 32]
    database.rollback.assert_not_awaited()


async def _restore(app, restart_now=True):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(
            "/backups/total-restore",
            files={"file": ("backup.zip", io.BytesIO(b"test archive"), "application/zip")},
            data={"restart_now": str(restart_now).lower()},
        )


@pytest.mark.parametrize("error_type", [ValueError, OSError])
async def test_restore_staging_errors_hide_server_details(api_boundary_app, monkeypatch, error_type):
    app, _database = api_boundary_app

    def stage(*_args, **_kwargs):
        raise error_type("/private/shogun/vault/credential-secret could not be read")

    monkeypatch.setattr(complete_backup_service, "stage_total_restore", stage)
    response = await _restore(app)

    assert response.status_code == 400
    assert "credential-secret" not in response.text
    assert "/private/shogun" not in response.text
    assert "archive" in response.json()["detail"]


async def test_restore_remains_staged_when_restart_fails_without_exposing_error(api_boundary_app, monkeypatch):
    app, _database = api_boundary_app
    monkeypatch.setattr(complete_backup_service, "stage_total_restore", lambda *_args, **_kwargs: {"staged": True})

    def restart(**_kwargs):
        raise RuntimeError("restart-secret at /private/shogun/restart.py")

    monkeypatch.setattr(restart_service, "request_restart", restart)
    response = await _restore(app)

    assert response.status_code == 202
    assert response.json()["staged"] is True
    assert response.json()["restart"]["accepted"] is False
    assert "Restart Shogun manually" in response.json()["restart"]["message"]
    assert "restart-secret" not in response.text
    assert "/private/shogun" not in response.text


async def test_restore_preserves_successful_restart_response(api_boundary_app, monkeypatch):
    app, _database = api_boundary_app
    monkeypatch.setattr(complete_backup_service, "stage_total_restore", lambda *_args, **_kwargs: {"staged": True})
    monkeypatch.setattr(
        restart_service, "request_restart", lambda **_kwargs: {"accepted": True, "strategy": "launcher"},
    )

    response = await _restore(app)

    assert response.status_code == 202
    assert response.json() == {"staged": True, "restart": {"accepted": True, "strategy": "launcher"}}


@pytest.mark.parametrize("tool_name", ["desktop_click", "desktop_type", "desktop_screenshot"])
@pytest.mark.parametrize("status", ["error", "blocked"])
def test_ronin_action_errors_do_not_publish_tool_diagnostics(tool_name, status):
    result = {
        "status": status,
        "message": "credential=ronin-secret Traceback: /private/shogun/desktop.py",
        "error_type": "SensitiveInternalError",
    }

    event = agents._ronin_action_event(tool_name, {}, result)

    assert event["type"] == "ronin_action"
    assert event["action"] == "error"
    assert "permissions" in event["detail"]
    assert "ronin-secret" not in json.dumps(event)
    assert "/private/shogun" not in json.dumps(event)
    assert "SensitiveInternalError" not in json.dumps(event)


@pytest.mark.parametrize(
    "tool_name,arguments,action,detail",
    [
        ("desktop_click", {"x": 12, "y": 34}, "click", "Clicked at (12, 34)"),
        ("desktop_type", {"text": "hello"}, "type", "Typed: hello"),
        ("desktop_type", {"text": "x" * 100}, "type", "Typed: " + "x" * 80 + "..."),
    ],
)
def test_ronin_action_success_preserves_action_without_raw_diagnostics(tool_name, arguments, action, detail):
    result = {"status": "success", "message": "internal desktop implementation details"}

    event = agents._ronin_action_event(tool_name, arguments, result)

    assert event == {"type": "ronin_action", "action": action, "detail": detail}
