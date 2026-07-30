"""Regression coverage for the post-red-team security punch list."""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Response
from starlette.requests import Request


def test_gensui_defaults_to_loopback_and_hides_production_schema(monkeypatch):
    from gensui.app import create_app
    from gensui.config import GensuiSettings, gensui_settings

    assert GensuiSettings(_env_file=None).gensui_server_host == "127.0.0.1"
    monkeypatch.setattr(gensui_settings, "debug", False)
    paths = {
        path
        for route in create_app().routes
        if (path := getattr(route, "path", None)) is not None
    }
    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths


def test_gensui_secret_file_is_generated_with_strong_material(tmp_path: Path):
    from gensui.config import GensuiSettings

    secret_file = tmp_path / "secrets" / "jwt"
    config = GensuiSettings(
        _env_file=None,
        gensui_data_path=tmp_path,
        gensui_log_path=tmp_path / "logs",
        gensui_jwt_secret=None,
        gensui_jwt_secret_file=secret_file,
        gensui_admin_password="correct-horse-battery-staple",
    )
    config.ensure_directories()
    config.validate_security()
    assert secret_file.exists()
    assert len(config.jwt_secret) >= 64


def test_gensui_can_explicitly_allow_weak_password_on_loopback(tmp_path: Path):
    from gensui.config import GensuiSettings

    config = GensuiSettings(
        _env_file=None,
        gensui_server_host="127.0.0.1",
        gensui_jwt_secret="s" * 64,
        gensui_admin_password="changeme",
        gensui_allow_insecure_local_password=True,
    )

    config.validate_security()


def test_gensui_rejects_weak_password_bypass_on_remote_binding():
    from gensui.config import GensuiSettings

    config = GensuiSettings(
        _env_file=None,
        gensui_server_host="0.0.0.0",
        gensui_jwt_secret="s" * 64,
        gensui_admin_password="changeme",
        gensui_allow_insecure_local_password=True,
    )

    with pytest.raises(RuntimeError, match="loopback server host"):
        config.validate_security()


def test_gensui_tokens_are_typed_and_browser_cookies_are_httponly(monkeypatch):
    from gensui.api.auth import _issue_browser_session
    from gensui.config import gensui_settings
    from gensui.services.auth_service import AuthService

    monkeypatch.setattr(gensui_settings, "gensui_jwt_secret", "s" * 64)
    monkeypatch.setattr(gensui_settings, "gensui_access_token_minutes", 15)
    monkeypatch.setattr(gensui_settings, "gensui_refresh_token_days", 7)
    admin = SimpleNamespace(id="00000000-0000-0000-0000-000000000001", email="a@example.com", role="admin")
    response = Response()
    access = _issue_browser_session(response, admin)

    assert AuthService.decode_token(access, expected_type="access")["type"] == "access"
    cookies = response.headers.getlist("set-cookie")
    assert any("gensui_access_token=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert any("gensui_refresh_token=" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert any("gensui_csrf_token=" in cookie and "HttpOnly" not in cookie for cookie in cookies)


@pytest.mark.asyncio
async def test_gensui_cookie_mutations_require_csrf():
    from fastapi import HTTPException

    from gensui.api.deps import get_current_admin

    request = Request({
        "type": "http",
        "method": "POST",
        "path": "/api/gensui/policy",
        "headers": [(b"cookie", b"gensui_access_token=opaque")],
        "client": ("127.0.0.1", 1234),
    })
    with pytest.raises(HTTPException, match="CSRF") as exc_info:
        await get_current_admin(request, authorization=None, x_csrf_token=None, db=SimpleNamespace())
    assert exc_info.value.status_code == 403


def test_workspace_mutations_have_explicit_infrastructure_admin_guards():
    from shogun.api.a2a import workspace_router
    from shogun.api.infrastructure_auth import require_infrastructure_admin

    protected = {
        ("POST", "/workspaces"),
        ("PATCH", "/workspaces/{workspace_id}"),
        ("DELETE", "/workspaces/{workspace_id}"),
        ("PATCH", "/workspaces/{workspace_id}/peers/{peer_id}/status"),
        ("DELETE", "/workspaces/{workspace_id}/peers/{peer_id}"),
    }
    discovered = set()
    for route in workspace_router.routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        for method in route.methods or set():
            key = (method, route.path)
            if key in protected:
                assert require_infrastructure_admin in dependencies
                discovered.add(key)
    assert discovered == protected


def test_a2a_replay_cache_is_bounded_and_evicts_oldest(monkeypatch):
    import shogun.api.a2a as a2a

    a2a._seen_signatures.clear()
    monkeypatch.setattr(a2a, "_A2A_REPLAY_CACHE_LIMIT", 3)
    now = time.time()
    for index in range(4):
        a2a._remember_a2a_signature(f"sig-{index}", now + index)
    assert list(a2a._seen_signatures) == ["sig-1", "sig-2", "sig-3"]


def test_server_a2a_uses_explicit_https_public_url(monkeypatch):
    from shogun.api.a2a import _self_url
    from shogun.config import settings

    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "a2a_public_url", "https://shogun.example/base")
    assert _self_url("/api/v1/a2a/inbound") == "https://shogun.example/base/api/v1/a2a/inbound"
    monkeypatch.setattr(settings, "a2a_public_url", None)
    with pytest.raises(RuntimeError, match="A2A_PUBLIC_URL"):
        _self_url()


def test_a2a_peer_secret_uses_domain_separated_encryption(monkeypatch):
    from shogun.config import settings
    from shogun.services.a2a_crypto import protect_peer_secret, reveal_peer_secret

    monkeypatch.setattr(settings, "a2a_encryption_key", "a" * 64)
    protected = protect_peer_secret("peer-secret")
    assert protected.startswith("a2a:v1:")
    assert "peer-secret" not in protected
    assert reveal_peer_secret(protected) == "peer-secret"


def test_request_context_ignores_untrusted_forwarded_address(monkeypatch):
    from gensui.config import gensui_settings
    from gensui.services.request_context import begin_request, current_request_metadata, end_request

    monkeypatch.setattr(gensui_settings, "gensui_trusted_proxies", "")
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-forwarded-for", b"198.51.100.9")],
        "client": ("203.0.113.7", 1234),
    })
    token = begin_request(request)
    try:
        assert current_request_metadata()[0] == "203.0.113.7"
    finally:
        end_request(token)


def test_startup_notices_persist_only_sanitized_operator_text(tmp_path: Path, monkeypatch):
    import shogun.services.startup_notices as notices

    monkeypatch.setattr(notices, "_NOTICE_PATH", tmp_path / "notices.json")
    notices.record_startup_notice("migration_failed", "Run repair before restarting.", "error")
    stored = notices.list_startup_notices()
    assert stored[0]["code"] == "migration_failed"
    assert stored[0]["message"] == "Run repair before restarting."
    assert "traceback" not in stored[0]
