from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import BaseModel

from shogun.engine import vector_store
from shogun.services.complete_backup_service import (
    MANIFEST_NAME,
    apply_pending_total_restore,
    create_complete_backup,
    discover_storage_roots,
    stage_total_restore,
)


class FakeSettings(BaseModel):
    data_path: Path
    qdrant_path: Path
    config_path: Path
    log_path: Path
    vault_path: Path
    plugin_state_path: Path
    database_url: str


def _settings(root: Path) -> FakeSettings:
    return FakeSettings(
        data_path=root / "data",
        qdrant_path=root / "data" / "qdrant",
        config_path=root / "configs",
        log_path=root / "logs",
        vault_path=root / "vault",
        plugin_state_path=root / "data" / "future-plugin",
        database_url=f"sqlite+aiosqlite:///{(root / 'data' / 'shogun.db').as_posix()}",
    )


def _seed_state(root: Path) -> FakeSettings:
    settings = _settings(root)
    for directory in {
        settings.data_path,
        settings.qdrant_path,
        settings.config_path,
        settings.log_path,
        settings.vault_path,
        settings.plugin_state_path,
    }:
        directory.mkdir(parents=True, exist_ok=True)
    (settings.qdrant_path / "vectors.bin").write_bytes(b"qdrant-state")
    (settings.config_path / "toolgate.json").write_text('{"mode":"guarded"}', encoding="utf-8")
    (settings.config_path / "setup.json").write_text(
        json.dumps({"data_path": str(root / "data")}),
        encoding="utf-8",
    )
    (settings.log_path / "all.log").write_text("complete log history", encoding="utf-8")
    (settings.vault_path / "credential.bin").write_bytes(b"encrypted")
    (settings.plugin_state_path / "future.dat").write_bytes(b"automatically-discovered")
    (root / ".env").write_text(f"DATA_PATH={root / 'data'}\nSECRET_KEY=preserved\n", encoding="utf-8")
    (root / ".env.example").write_text("NOT_RUNTIME_STATE=true\n", encoding="utf-8")
    with closing(sqlite3.connect(settings.data_path / "shogun.db")) as database:
        database.execute("CREATE TABLE chats (message TEXT NOT NULL)")
        database.execute("INSERT INTO chats VALUES ('entire chat history')")
        database.commit()
    return settings


def test_discovery_collapses_nested_paths_and_keeps_future_storage(tmp_path: Path) -> None:
    settings = _seed_state(tmp_path)

    roots = discover_storage_roots(settings_object=settings, project_root=tmp_path)

    root_paths = {item.path for item in roots}
    assert settings.data_path in root_paths
    assert settings.qdrant_path not in root_paths
    assert settings.plugin_state_path not in root_paths
    assert any(item.setting_key == "__project_environment__" for item in roots)


def test_complete_backup_and_total_restore_recreate_all_discovered_state(tmp_path: Path) -> None:
    source_root = tmp_path / "old-pc" / "Shogun"
    target_root = tmp_path / "new-pc" / "Shogun"
    source_settings = _seed_state(source_root)
    target_settings = _seed_state(target_root)

    result = create_complete_backup(
        save_path=source_root / "complete_backups",
        label="migration",
        settings_object=source_settings,
        project_root=source_root,
    )
    assert result["success"] is True
    archive_path = Path(result["path"])
    with zipfile.ZipFile(archive_path) as archive:
        assert MANIFEST_NAME in archive.namelist()
        assert all("complete_backups" not in name for name in archive.namelist())
        assert all(".env.example" not in name for name in archive.namelist())

    (target_settings.data_path / "extra-after-backup.txt").write_text("must disappear", encoding="utf-8")
    (target_settings.log_path / "all.log").write_text("new pc log", encoding="utf-8")
    (target_root / ".env").write_text("SECRET_KEY=new-pc\n", encoding="utf-8")
    with archive_path.open("rb") as source:
        staged = stage_total_restore(source, filename=archive_path.name, project_root=target_root)
    assert staged["restart_required"] is True

    restored = apply_pending_total_restore(project_root=target_root, settings_object=target_settings)

    assert restored["applied"] is True
    assert not (target_settings.data_path / "extra-after-backup.txt").exists()
    assert (target_settings.qdrant_path / "vectors.bin").read_bytes() == b"qdrant-state"
    assert (target_settings.config_path / "toolgate.json").read_text(encoding="utf-8") == '{"mode":"guarded"}'
    setup_contents = (target_settings.config_path / "setup.json").read_text(encoding="utf-8")
    assert str(target_root).replace("\\", "\\\\") in setup_contents
    assert str(source_root).replace("\\", "\\\\") not in setup_contents
    assert (target_settings.log_path / "all.log").read_text(encoding="utf-8") == "complete log history"
    assert (target_settings.plugin_state_path / "future.dat").read_bytes() == b"automatically-discovered"
    assert "SECRET_KEY=preserved" in (target_root / ".env").read_text(encoding="utf-8")
    assert str(target_root) in (target_root / ".env").read_text(encoding="utf-8")
    assert str(source_root) not in (target_root / ".env").read_text(encoding="utf-8")
    with closing(sqlite3.connect(target_settings.data_path / "shogun.db")) as database:
        assert database.execute("SELECT message FROM chats").fetchone() == ("entire chat history",)
    assert Path(restored["safety_backup"]).is_file()


def test_total_restore_rejects_zip_slip_even_when_manifest_is_present(tmp_path: Path) -> None:
    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as archive:
        archive.writestr(
            MANIFEST_NAME,
            '{"format":"shogun-complete-backup","format_version":1,"roots":[],"files":[]}',
        )
        archive.writestr("../../escape.txt", "owned")
    malicious.seek(0)

    with pytest.raises(ValueError, match="unsafe path"):
        stage_total_restore(malicious, filename="malicious.zip", project_root=tmp_path)
    assert not (tmp_path.parent / "escape.txt").exists()


def test_complete_backup_guard_closes_and_blocks_embedded_qdrant(monkeypatch) -> None:
    store = vector_store.VectorStore()

    class FakeClient:
        closed = False

        def close(self) -> None:
            self.closed = True

    client = FakeClient()
    store._client = client
    monkeypatch.setattr(vector_store, "_store_instance", store)

    with vector_store.suspend_embedded_vector_store():
        assert client.closed is True
        assert store._client is None
        with pytest.raises(RuntimeError, match="paused"):
            _ = store.client

    assert vector_store._storage_suspended is False


def test_total_restore_rejects_forged_storage_root(tmp_path: Path) -> None:
    forged = io.BytesIO()
    manifest = {
        "format": "shogun-complete-backup",
        "format_version": 1,
        "roots": [{
            "id": "../../application",
            "setting_key": "__project_environment__",
            "kind": "selected_files",
        }],
        "files": [],
    }
    with zipfile.ZipFile(forged, "w") as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(manifest))
    forged.seek(0)

    with pytest.raises(ValueError, match="storage root ID"):
        stage_total_restore(forged, filename="forged.zip", project_root=tmp_path)
