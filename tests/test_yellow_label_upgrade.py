"""End-to-end verification that upgrading a full Yellow Label install produces
a clean bare-bones Shogun AgentFlow installation while preserving 100% of
workspace folder structure, files, AgentFlows, profiles, and credentials.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import uuid
from pathlib import Path

import pytest
import tomllib
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shogun.app import create_app
from shogun.config import settings
from shogun.db.base import Base
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.db.models.model_provider import ModelProvider
from shogun.services.provider_credentials import decrypt_password, encrypt_password, provider_api_key
from shogun.services.update_installer import (
    prune_legacy_from_manifest,
    validate_update_source,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_release_passes_yellow_label_updater_contract():
    """Existing Yellow Label installers validate these exact files and fields."""
    manifest = validate_update_source(PROJECT_ROOT)
    assert manifest["build"] > 274
    assert manifest["version"] != "1.47.123"

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = pyproject.get("project", {}).get("optional-dependencies", {})
    assert "office" in extras, "Existing Yellow Label updater runs `pip install {source}[office]`"

    manifest_file = PROJECT_ROOT / "shogun" / "resources" / "barebones_manifest.json"
    assert manifest_file.is_file()
    managed = json.loads(manifest_file.read_text(encoding="utf-8"))["managed_files"]
    assert "shogun/app.py" in managed
    assert "frontend/dist/index.html" in managed


def test_in_place_upgrade_prunes_legacy_code_and_preserves_files_and_flows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Simulate upgrading a full Yellow Label install in-place to Bare-Bones AgentFlow."""
    yellow_install = tmp_path / "Shogun-YellowLabel"
    yellow_install.mkdir()

    # 1. Legacy full-Yellow-Label code files that must be pruned
    legacy_files = {
        "version.json": json.dumps({"version": "1.47.119", "name": "Shogun AFM", "build": 270}),
        "shogun/api/kaizen.py": "# legacy kaizen router\n",
        "shogun/api/dojo.py": "# legacy dojo router\n",
        "shogun/ronin/core/ronin_controller.py": "# legacy ronin controller\n",
        "frontend/src/pages/Dojo.tsx": "export const Dojo = () => null;\n",
        "frontend/src/pages/Supermode.tsx": "export const Supermode = () => null;\n",
        "frontend/dist/assets/stale-legacy-chunk.js": "console.log('old');\n",
    }
    for rel, content in legacy_files.items():
        p = yellow_install / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    # 2. User persistent files & nested folder structure that MUST survive untouched
    preserved_files = {
        "data/workspace/Input/KS-LBP/Planning_v16/template.xlsx": b"FAKE-XLSX-BYTES-V16",
        "data/workspace/Input/KS-LBP/disponent_39.pdf": b"%PDF-1.7-SAMPLE",
        "data/workspace/Output/2026/monthly_report.md": b"# Monthly Report\nPreserved!",
        "data/workspace/CustomClientFolder/deep/nested/notes.txt": b"keep nested folder structure",
        "data/uploads/instructions.txt": b"custom uploaded prompt",
        "configs/office_config.json": b'{"enabled": true}\n',
        "configs/workspace.json": json.dumps({"workspace_path": str(yellow_install / "data" / "workspace")}).encode(),
        "vault/oauth.token": b"secret-oauth-bytes",
        ".env": b"API_HOST=127.0.0.1\nAPI_PORT=8000\nVAULT_ENCRYPTION_KEY=custom-customer-vault-key-1234567890\n",
    }
    for rel, raw in preserved_files.items():
        p = yellow_install / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)

    # 3. Seed realistic existing Yellow Label SQLite DB with an AgentFlow + encrypted AI Provider
    db_file = yellow_install / "data" / "shogun.db"
    db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"
    custom_vault_key = "custom-customer-vault-key-1234567890"
    monkeypatch.setattr(settings, "vault_encryption_key", custom_vault_key)

    flow_id = uuid.uuid4()
    n1_id, n2_id, n3_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    provider_id = uuid.uuid4()
    encrypted_secret = "enc:" + encrypt_password("sk-customer-live-secret-key")

    async def _seed_yellow_db() -> None:
        seed_engine = create_async_engine(db_url, echo=False)
        async with seed_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        seed_factory = async_sessionmaker(seed_engine, class_=AsyncSession, expire_on_commit=False)
        async with seed_factory() as session:
            session.add(
                AgentFlow(
                    id=flow_id,
                    name="KS-LBP Customer Production Flow",
                    description="Preserved across Yellow Label upgrade",
                    status="active",
                    trigger_type="manual",
                )
            )
            session.add_all(
                [
                    AgentFlowNode(
                        id=n1_id,
                        flow_id=flow_id,
                        node_type="input",
                        label="Start",
                        position_x=0,
                        position_y=0,
                        config={},
                    ),
                    AgentFlowNode(
                        id=n2_id,
                        flow_id=flow_id,
                        node_type="office",
                        label="Read Excel Template",
                        position_x=200,
                        position_y=0,
                        config={"action": "excel_read", "path": "Input/KS-LBP/Planning_v16/template.xlsx"},
                    ),
                    AgentFlowNode(
                        id=n3_id,
                        flow_id=flow_id,
                        node_type="output",
                        label="Final Output",
                        position_x=400,
                        position_y=0,
                        config={"output_type": "artifact"},
                    ),
                ]
            )
            session.add_all(
                [
                    AgentFlowEdge(flow_id=flow_id, source_node_id=n1_id, target_node_id=n2_id),
                    AgentFlowEdge(flow_id=flow_id, source_node_id=n2_id, target_node_id=n3_id),
                ]
            )
            session.add(
                ModelProvider(
                    id=provider_id,
                    name="Customer OpenRouter",
                    slug="customer-openrouter",
                    provider_type="openrouter",
                    base_url="https://openrouter.ai/api/v1",
                    auth_type="api_key",
                    status="connected",
                    config={"api_key": encrypted_secret, "models": ["openai/gpt-4o"]},
                )
            )
            await session.commit()
        await seed_engine.dispose()

    asyncio.run(_seed_yellow_db())

    # 4. Run the in-place upgrade script (skipping pip install inside tmp_path)
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from upgrade_yellow_label import upgrade_installation

    result = upgrade_installation(yellow_install, source_root=PROJECT_ROOT, install_deps=False)
    assert result["build"] > 270
    assert (yellow_install / result["backup"]).is_dir()

    # 5. Confirm obsolete full-Yellow-Label code was pruned and backed up
    for legacy_rel in (
        "shogun/api/kaizen.py",
        "shogun/api/dojo.py",
        "shogun/ronin/core/ronin_controller.py",
        "frontend/src/pages/Dojo.tsx",
        "frontend/src/pages/Supermode.tsx",
        "frontend/dist/assets/stale-legacy-chunk.js",
    ):
        assert not (yellow_install / legacy_rel).exists(), f"Legacy file should be pruned: {legacy_rel}"
        assert (yellow_install / result["backup"] / legacy_rel).is_file()

    # Confirm bare-bones code & release metadata were promoted
    assert (yellow_install / "shogun" / "app.py").is_file()
    assert (yellow_install / "frontend" / "dist" / "index.html").is_file()
    assert (yellow_install / "configs" / "release_metadata.json").is_file()

    # 6. Confirm ALL user workspace folders, files, configs, vault, and .env survived byte-for-byte
    for rel, expected_bytes in preserved_files.items():
        actual = yellow_install / rel
        assert actual.is_file(), f"User file lost during upgrade: {rel}"
        assert actual.read_bytes() == expected_bytes, f"User file modified during upgrade: {rel}"

    # 7. Boot bare-bones FastAPI app against the upgraded install's DB & workspace and verify live reads
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(settings, "workspace_path", yellow_install / "data" / "workspace")
    monkeypatch.setattr(settings, "uploads_path", yellow_install / "data" / "uploads")
    monkeypatch.setattr(settings, "config_path", yellow_install / "configs")
    monkeypatch.setattr(settings, "deployment_mode", "desktop")

    db_engine_mod = sys.modules["shogun.db.engine"]
    test_engine = create_async_engine(db_url, echo=False)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(db_engine_mod, "engine", test_engine)
    monkeypatch.setattr(db_engine_mod, "async_session_factory", test_factory)

    try:
        app = create_app()
        with TestClient(app) as client:
            flows_resp = client.get("/api/v1/agent-flows")
            assert flows_resp.status_code == 200
            names = [item["name"] for item in flows_resp.json()["data"]]
            assert "KS-LBP Customer Production Flow" in names

            detail_resp = client.get(f"/api/v1/agent-flows/{flow_id}")
            assert detail_resp.status_code == 200
            detail = detail_resp.json()["data"]
            assert len(detail["nodes"]) == 3
            assert len(detail["edges"]) == 2

            tree_resp = client.get("/api/v1/workspace/tree")
            assert tree_resp.status_code == 200
            tree_str = json.dumps(tree_resp.json())
            assert "KS-LBP" in tree_str
            assert "CustomClientFolder" in tree_str

            prov_resp = client.get("/api/v1/model-providers")
            assert prov_resp.status_code == 200
            assert any(p["name"] == "Customer OpenRouter" for p in prov_resp.json()["data"])

        # Verify encrypted API key still decrypts identically with the preserved VAULT_ENCRYPTION_KEY
        assert decrypt_password(encrypted_secret.removeprefix("enc:")) == "sk-customer-live-secret-key"
        assert provider_api_key({"api_key": encrypted_secret}) == "sk-customer-live-secret-key"
    finally:
        asyncio.run(test_engine.dispose())


def test_post_update_manifest_pruning_for_old_in_app_updater(tmp_path: Path):
    """Simulate an older Yellow Label in-app updater overlaying files without pruning."""
    install_dir = tmp_path / "old-in-app-updated"
    install_dir.mkdir()

    # Copy bare-bones manifest + a couple of managed files as the old updater would
    manifest_src = PROJECT_ROOT / "shogun" / "resources" / "barebones_manifest.json"
    manifest_dst = install_dir / "shogun" / "resources" / "barebones_manifest.json"
    manifest_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_src, manifest_dst)
    (install_dir / "shogun" / "app.py").write_text("# barebones\n", encoding="utf-8")

    # Leftover obsolete full-Yellow-Label files + preserved user workspace file
    (install_dir / "shogun" / "api").mkdir(parents=True, exist_ok=True)
    (install_dir / "shogun" / "api" / "bushido.py").write_text("# obsolete\n", encoding="utf-8")
    (install_dir / "frontend" / "src" / "pages").mkdir(parents=True, exist_ok=True)
    (install_dir / "frontend" / "src" / "pages" / "Kaizen.tsx").write_text("// obsolete\n", encoding="utf-8")
    (install_dir / "data" / "workspace" / "Input").mkdir(parents=True, exist_ok=True)
    (install_dir / "data" / "workspace" / "Input" / "keep.txt").write_text("user data", encoding="utf-8")

    # First boot prunes the 2 obsolete legacy files and keeps user data intact
    pruned_count = prune_legacy_from_manifest(install_dir)
    assert pruned_count == 2
    assert not (install_dir / "shogun" / "api" / "bushido.py").exists()
    assert not (install_dir / "frontend" / "src" / "pages" / "Kaizen.tsx").exists()
    assert (install_dir / "shogun" / "app.py").is_file()
    assert (install_dir / "data" / "workspace" / "Input" / "keep.txt").read_text(encoding="utf-8") == "user data"

    # Second boot is a fast 0-file no-op
    assert prune_legacy_from_manifest(install_dir) == 0

    # Git checkouts must NEVER be auto-pruned
    (install_dir / ".git").mkdir()
    (install_dir / "shogun" / "api").mkdir(parents=True, exist_ok=True)
    (install_dir / "shogun" / "api" / "extra_dev_file.py").write_text("# dev\n", encoding="utf-8")
    assert prune_legacy_from_manifest(install_dir) == 0
    assert (install_dir / "shogun" / "api" / "extra_dev_file.py").is_file()
