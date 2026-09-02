"""Regression coverage for the post-red-team security punch list."""

from __future__ import annotations

import time
from pathlib import Path

import pytest


def test_shogun_workspace_always_has_input_and_output_folders(tmp_path: Path, monkeypatch):
    from shogun.config import settings

    workspace = tmp_path / "workspace"
    monkeypatch.setattr(settings, "workspace_path", workspace)

    settings.ensure_directories()

    assert (workspace / "input").is_dir()
    assert (workspace / "output").is_dir()


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


def test_startup_notices_persist_only_sanitized_operator_text(tmp_path: Path, monkeypatch):
    import shogun.services.startup_notices as notices

    monkeypatch.setattr(notices, "_NOTICE_PATH", tmp_path / "notices.json")
    notices.record_startup_notice("migration_failed", "Run repair before restarting.", "error")
    stored = notices.list_startup_notices()
    assert stored[0]["code"] == "migration_failed"
    assert stored[0]["message"] == "Run repair before restarting."
    assert "traceback" not in stored[0]
