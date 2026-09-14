"""Regression tests for the non-configurable Yellow Label edition boundary."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shogun.api import setup as setup_api
from shogun.api.setup import SetupCompletePayload
from shogun.app import create_app
from shogun.db.models.agent_flow import AgentFlow
from shogun.db.models.nexus import NexusTaskModel
from shogun.db.models.operator import Operator
from shogun.db.models.teams import TeamsConfig
from shogun.edition import EDITION_NAME, REMOVED_FEATURES, REMOVED_NATIVE_TOOLS
from shogun.services.native_skills import NATIVE_TOOLS
from shogun.services.notification_service import send_channel_message

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_REMOVED_FEATURES = {
    "flow_stack",
    "team_mode",
    "microsoft_teams",
    "logs_ui",
    "nexus",
    "gensui",
    "gensui_skill_repository",
    "gensui_skill_publication",
    "gensui_skill_distribution",
    "gensui_competence_registry",
    "enterprise_skill_sync",
}

REMOVED_ROUTE_PREFIXES = {
    "/api/v1/team",
    "/api/v1/logs",
    "/api/v1/a2a",
    "/api/v1/workspaces",
    "/api/v1/stacks/orchestrator",
    "/api/v1/gensui",
    "/api/v1/katana/teams",
    "/api/v1/katana/command",
    "/api/v1/nexus",
    "/api/v1/agent-flows/flow-stack",
    "/api/v1/models/usage/by-stack",
}

DENY_ONLY_GENSUI_ROUTES = frozenset(
    {
        ("POST", "/api/v1/gensui/skills/publish"),
        ("GET", "/api/v1/gensui/skills/manifest"),
        ("POST", "/api/v1/gensui/skills/{skill_id}/approve"),
        ("POST", "/api/v1/gensui/skills/{skill_id}/distribute"),
        ("GET", "/api/v1/gensui/competence"),
    }
)


def test_yellow_label_capability_boundary_is_fixed() -> None:
    assert EDITION_NAME == "yellow-label"
    assert set(REMOVED_FEATURES) == EXPECTED_REMOVED_FEATURES


def test_macos_release_uses_yellow_label_source_and_boundary_tests() -> None:
    installer = (PROJECT_ROOT / "Shogun-Install.command").read_text(encoding="utf-8")
    workflow = (PROJECT_ROOT / ".github/workflows/macos-compatibility.yml").read_text(encoding="utf-8")
    assert 'REPO="AlphaHorizon-AI/Shogun"' in installer
    assert 'SHOGUN_MACOS_EDITION: "yellow-label"' in workflow
    assert "tests/test_yellow_label_edition.py" in workflow


def test_removed_features_are_not_registered_as_public_routes() -> None:
    app = create_app()
    found_deny_stubs: set[tuple[str, str]] = set()

    for route in app.routes:
        path = getattr(route, "path", None)
        if path is None:
            continue
        methods = getattr(route, "methods", set()) or set()

        for prefix in REMOVED_ROUTE_PREFIXES:
            if path.startswith(prefix):
                for method in methods:
                    if (method, path) in DENY_ONLY_GENSUI_ROUTES:
                        found_deny_stubs.add((method, path))
                    else:
                        pytest.fail(f"Unauthorized enterprise route registered: {method} {path}")

        assert "/attach-to-stack/" not in path

    # Exactly the five deny-only Gensui stub routes must be present
    assert found_deny_stubs == DENY_ONLY_GENSUI_ROUTES


def test_gensui_deny_stubs_always_return_403_even_with_flags_enabled(monkeypatch) -> None:
    """The 5 Gensui stub routes must always deny with 403 CAPABILITY_UNAVAILABLE."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    dummy_skill_id = uuid.uuid4()

    endpoints = [
        ("POST", "/api/v1/gensui/skills/publish"),
        ("GET", "/api/v1/gensui/skills/manifest"),
        ("POST", f"/api/v1/gensui/skills/{dummy_skill_id}/approve"),
        ("POST", f"/api/v1/gensui/skills/{dummy_skill_id}/distribute"),
        ("GET", "/api/v1/gensui/competence"),
    ]

    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code}"
        assert resp.json().get("detail", {}).get("error") == "CAPABILITY_UNAVAILABLE"

    # Even if someone attempts to mock or enable all capabilities, denial is unconditional
    from shogun.services.capability_service import CapabilityService

    monkeypatch.setattr(CapabilityService, "enabled", lambda self, cap: True)

    for method, path in endpoints:
        resp = client.request(method, path)
        assert resp.status_code == 403, f"{method} {path} returned {resp.status_code} after flags enabled"
        assert resp.json().get("detail", {}).get("error") == "CAPABILITY_UNAVAILABLE"

    # The route inventory test above rejects all other enterprise handlers.
    # Unknown URLs may reach the existing HTML fallback for the frontend.
    client.close()


def test_flow_stack_native_tools_are_not_advertised() -> None:
    names = {tool["function"]["name"] for tool in NATIVE_TOOLS}
    assert names.isdisjoint(REMOVED_NATIVE_TOOLS)


def test_setup_rejects_team_mode() -> None:
    with pytest.raises(ValidationError, match="installation_mode"):
        SetupCompletePayload(
            installation_mode="team",
            security_incident_acknowledged=True,
            license_terms_accepted=True,
        )


@pytest.mark.asyncio
async def test_legacy_team_configuration_is_hidden_without_being_rewritten(monkeypatch) -> None:
    legacy_setup = {
        "setup_complete": True,
        "installation_mode": "team",
        "team_members": [{"id": "retained-for-white-label"}],
    }
    monkeypatch.setattr(setup_api, "_read_setup", lambda: legacy_setup)
    monkeypatch.setattr(
        setup_api,
        "_write_setup",
        lambda _data: pytest.fail("status lookup must not rewrite legacy data"),
    )

    response = await setup_api.get_setup_status()

    assert response.data["installation_mode"] == "single"
    assert response.data["team_members"] == []
    assert legacy_setup["installation_mode"] == "team"
    assert legacy_setup["team_members"] == [{"id": "retained-for-white-label"}]


@pytest.mark.asyncio
async def test_microsoft_teams_delivery_is_disabled() -> None:
    result = await send_channel_message("hello", channel="teams")
    assert result == {
        "teams": {
            "ok": False,
            "error": "Microsoft Teams is not available in Yellow Label",
            "sent": 0,
        }
    }


def test_premium_persistence_models_remain_for_future_white_label_upgrade() -> None:
    assert AgentFlow.__table__.c.flow_type is not None
    assert Operator.__table__.c.preferences is not None
    assert TeamsConfig.__table__.name == "katana_teams_config"
    assert NexusTaskModel.__table__.name == "nexus_tasks"


def test_gensui_is_absent_from_yellow_label_installation_surfaces() -> None:
    for relative_path in (
        ".env.example",
        ".env.server.example",
        "docker-compose.server.yml",
    ):
        content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "gensui" not in content.lower(), relative_path

    dockerignore_lines = {
        line.strip()
        for line in (PROJECT_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "gensui" in dockerignore_lines
    assert not any(line.startswith("!gensui") for line in dockerignore_lines)

    for relative_path in (
        "Gensui-Docker-Install.bat",
        "Gensui-Docker-Install.sh",
        "Gensui-Install.bat",
        "Gensui-Install.command",
        "gensui/Dockerfile",
        "gensui/docker-compose.yml",
        "gensui/install.bat",
        "gensui/install.sh",
    ):
        assert not (PROJECT_ROOT / relative_path).exists(), relative_path
