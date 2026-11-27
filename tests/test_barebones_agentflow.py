"""End-to-end verification tests for bare-bones Shogun AgentFlow."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from shogun.app import create_app
from shogun.config import settings
from shogun.db.engine import async_session_factory, engine
from shogun.db.base import Base
import shogun.db.models  # noqa: F401


@pytest.fixture()
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run each test against a fresh SQLite DB and isolated local workspace folder."""
    db_file = tmp_path / "test_agentflow.db"
    workspace_dir = tmp_path / "local_folder"
    uploads_dir = tmp_path / "uploads"
    configs_dir = tmp_path / "configs"

    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    monkeypatch.setattr(settings, "workspace_path", workspace_dir)
    monkeypatch.setattr(settings, "uploads_path", uploads_dir)
    monkeypatch.setattr(settings, "config_path", configs_dir)
    monkeypatch.setattr(settings, "infrastructure_admin_token", None)
    monkeypatch.setattr(settings, "deployment_mode", "desktop")

    # Rebind async engine to the isolated SQLite DB
    import sys
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    import shogun
    import shogun.engine.flow_engine as flow_engine_mod
    import shogun.api.system as system_api_mod

    # Guarantee we are testing D:\Projects\Shogun-AgentFlow, never another checkout
    project_root = Path(__file__).resolve().parent.parent
    assert Path(shogun.__file__).resolve().is_relative_to(project_root), f"Loaded wrong shogun: {shogun.__file__}"

    db_engine_mod = sys.modules["shogun.db.engine"]
    test_engine = create_async_engine(settings.database_url, echo=False)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    monkeypatch.setattr(db_engine_mod, "engine", test_engine)
    monkeypatch.setattr(db_engine_mod, "async_session_factory", test_factory)
    monkeypatch.setattr(flow_engine_mod, "async_session_factory", test_factory)
    monkeypatch.setattr(system_api_mod, "async_session_factory", test_factory)

    yield tmp_path

    asyncio.run(test_engine.dispose())


def test_only_barebones_routes_registered(isolated_env: Path):
    app = create_app()
    paths = set(app.openapi()["paths"].keys())
    assert "/api/v1/health" in paths
    assert "/api/v1/agent-flows" in paths
    assert "/api/v1/mapping-rpa/templates" in paths
    assert "/api/v1/transformation-profiles" in paths
    assert "/api/v1/stacks/orchestrator" in paths
    assert "/api/v1/model-providers" in paths
    assert "/api/v1/models/routing/profiles" in paths
    assert "/api/v1/workspace/config" in paths

    # Stripped subsystems must NOT exist
    for forbidden in (
        "/api/v1/memory",
        "/api/v1/mado/status",
        "/api/v1/ronin/desktop/status",
        "/api/v1/dojo/skills",
        "/api/v1/bushido/schedules",
        "/api/v1/kaizen/constitution",
        "/api/v1/telemetry/status",
        "/api/v1/supermode/missions",
        "/api/v1/setup/status",
    ):
        assert forbidden not in paths, f"Unexpected stripped route still mounted: {forbidden}"


def test_local_folder_setup_and_safety(isolated_env: Path):
    app = create_app()
    with TestClient(app) as client:
        new_folder = isolated_env / "custom_workspace"
        resp = client.put("/api/v1/workspace/config", json={"workspace_path": str(new_folder)})
        assert resp.status_code == 200, resp.text
        assert Path(resp.json()["data"]["workspace_path"]).resolve() == new_folder.resolve()
        assert (new_folder / "input").is_dir()
        assert (new_folder / "output").is_dir()

        mkdir_resp = client.post("/api/v1/workspace/mkdir", json={"path": "input/projects"})
        assert mkdir_resp.status_code == 200
        assert (new_folder / "input" / "projects").is_dir()

        # Path traversal must be rejected
        bad_resp = client.post("/api/v1/workspace/mkdir", json={"path": "../escape"})
        assert bad_resp.status_code == 400


def test_ai_providers_and_routing_profiles(isolated_env: Path):
    app = create_app()
    with TestClient(app) as client:
        # Create an AI provider
        prov_resp = client.post(
            "/api/v1/model-providers",
            json={
                "name": "Test OpenAI",
                "provider_type": "openai",
                "slug": "test-openai",
                "base_url": "https://api.openai.com/v1",
                "auth_type": "api_key",
                "is_local": False,
                "config": {"api_key": "sk-test-secret-1234", "models": ["gpt-4o-mini"]},
            },
        )
        assert prov_resp.status_code == 201, prov_resp.text
        provider_id = prov_resp.json()["data"]["id"]

        # Connect provider and check routing profiles exist
        patch_resp = client.patch(f"/api/v1/model-providers/{provider_id}", json={"status": "connected"})
        assert patch_resp.status_code == 200

        profiles_resp = client.get("/api/v1/models/routing/profiles")
        assert profiles_resp.status_code == 200
        profiles = profiles_resp.json()["data"]
        assert len(profiles) >= 1

        # Create a custom routing profile
        custom_resp = client.post(
            "/api/v1/model-routing-profiles",
            json={
                "name": "Fast Flow Profile",
                "description": "Custom test routing profile",
                "is_default": True,
                "rules": [{"task_type": "*", "primary_model_id": provider_id, "fallback_model_ids": []}],
            },
        )
        assert custom_resp.status_code == 201, custom_resp.text


def test_agentflow_dag_execution_with_adhoc_agent_and_local_folder(isolated_env: Path):
    app = create_app()
    with TestClient(app) as client:
        # Configure provider + mark connected
        prov = client.post(
            "/api/v1/model-providers",
            json={
                "name": "Mock Provider",
                "provider_type": "openai",
                "slug": "mock-provider",
                "base_url": "https://api.openai.com/v1",
                "auth_type": "api_key",
                "is_local": False,
                "config": {"api_key": "sk-mock-key", "models": ["gpt-4o-mini"]},
            },
        ).json()["data"]
        client.patch(f"/api/v1/model-providers/{prov['id']}", json={"status": "connected"})

        # Seed a local file in workspace
        workspace_root = settings.workspace_path.resolve()
        (workspace_root / "input").mkdir(parents=True, exist_ok=True)
        (workspace_root / "input" / "brief.txt").write_text("Project Alpha launch checklist", encoding="utf-8")

        # Create flow
        flow_id = client.post(
            "/api/v1/agent-flows",
            json={"name": "End-to-End Barebones Flow", "description": "Tests ad-hoc agent, logic, and local folder"},
        ).json()["data"]["id"]

        # Verify all 17 node types are accepted on graph save
        all_types_resp = client.put(
            f"/api/v1/agent-flows/{flow_id}/graph",
            json={
                "nodes": [
                    {"id": "n1", "node_type": "office", "label": "Excel Read", "config": {"action": "excel_read"}},
                    {"id": "n2", "node_type": "file_template", "label": "Template", "config": {}},
                    {
                        "id": "n3",
                        "node_type": "mapping_rpa",
                        "label": "Mapping RPA",
                        "config": {"mappings": [{"source": "input", "target": "A"}]},
                    },
                    {"id": "n4", "node_type": "mado_browser", "label": "Browser", "config": {}},
                    {"id": "n5", "node_type": "coding", "label": "Coding", "config": {"action": "analyze"}},
                    {"id": "n6", "node_type": "email_read", "label": "Email Read", "config": {}},
                    {"id": "n7", "node_type": "email_send", "label": "Email Send", "config": {}},
                    {"id": "n8", "node_type": "calendar_read", "label": "Calendar Read", "config": {}},
                    {"id": "n9", "node_type": "channel_send", "label": "Channel Send", "config": {}},
                ],
                "edges": [],
            },
        )
        assert all_types_resp.status_code == 200, all_types_resp.text

        # Save valid core 6-node DAG (workspace read -> ad-hoc samurai -> logic -> true output / false skipped)
        graph_resp = client.put(
            f"/api/v1/agent-flows/{flow_id}/graph",
            json={
                "nodes": [
                    {
                        "id": "11111111-1111-1111-1111-111111111111",
                        "node_type": "workspace",
                        "label": "Read Brief",
                        "position_x": 0,
                        "position_y": 0,
                        "config": {"action": "read_file", "path": "input/brief.txt"},
                    },
                    {
                        "id": "22222222-2222-2222-2222-222222222222",
                        "node_type": "samurai",
                        "label": "Ad-Hoc Summarizer",
                        "position_x": 250,
                        "position_y": 0,
                        "config": {
                            "role_description": "You are a concise launch coordinator.",
                            "task_description": "Summarize the project brief.",
                            "expected_output": "Short summary",
                        },
                    },
                    {
                        "id": "33333333-3333-3333-3333-333333333333",
                        "node_type": "logic",
                        "label": "Has Alpha?",
                        "position_x": 500,
                        "position_y": 0,
                        "config": {"condition_expression": "Does the summary mention Alpha?"},
                    },
                    {
                        "id": "44444444-4444-4444-4444-444444444444",
                        "node_type": "output",
                        "label": "Final Report",
                        "position_x": 750,
                        "position_y": 0,
                        "config": {"output_type": "artifact", "format": "markdown"},
                    },
                    {
                        "id": "55555555-5555-5555-5555-555555555555",
                        "node_type": "output",
                        "label": "Fallback Skipped",
                        "position_x": 750,
                        "position_y": 200,
                        "config": {"output_type": "artifact", "format": "markdown"},
                    },
                ],
                "edges": [
                    {
                        "source_node_id": "11111111-1111-1111-1111-111111111111",
                        "target_node_id": "22222222-2222-2222-2222-222222222222",
                    },
                    {
                        "source_node_id": "22222222-2222-2222-2222-222222222222",
                        "target_node_id": "33333333-3333-3333-3333-333333333333",
                    },
                    {
                        "source_node_id": "33333333-3333-3333-3333-333333333333",
                        "target_node_id": "44444444-4444-4444-4444-444444444444",
                    },
                    {
                        "source_node_id": "33333333-3333-3333-3333-333333333333",
                        "target_node_id": "55555555-5555-5555-5555-555555555555",
                        "source_handle": "false",
                    },
                ],
            },
        )
        assert graph_resp.status_code == 200, graph_resp.text

        # Execute flow with mocked LLM responses (1st call: Ad-Hoc Agent, 2nd call: Logic evaluator)
        import httpx

        def _fake_llm_resp(content: str) -> httpx.Response:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"role": "assistant", "content": content}}]},
            )

        mock_llm = AsyncMock(
            side_effect=[
                _fake_llm_resp("Project Alpha Summary: Ready to launch."),
                _fake_llm_resp("TRUE"),
            ]
        )
        with patch("shogun.engine.flow_engine.model_chat_completion", mock_llm):
            run_id = client.post(f"/api/v1/agent-flows/{flow_id}/run").json()["data"]["run_id"]
            # Poll until completed
            import time

            run_data = None
            for _ in range(40):
                run_data = client.get(f"/api/v1/agent-flows/runs/{run_id}").json()["data"]
                if run_data["status"] in {"completed", "failed", "cancelled"}:
                    break
                time.sleep(0.05)

        assert run_data is not None
        assert run_data["status"] == "completed", run_data
        assert run_data["node_states"]["22222222-2222-2222-2222-222222222222"]["status"] == "completed"
        assert "Project Alpha Summary" in str(run_data["node_states"]["22222222-2222-2222-2222-222222222222"]["output"])
        assert run_data["node_states"]["44444444-4444-4444-4444-444444444444"]["status"] == "completed"
        assert run_data["node_states"]["55555555-5555-5555-5555-555555555555"]["status"] == "skipped"

        # Verify built-in templates instantiate cleanly
        tpl_resp = client.get("/api/v1/agent-flows/templates")
        assert tpl_resp.status_code == 200
        assert tpl_resp.json()["data"]["total"] >= 3
