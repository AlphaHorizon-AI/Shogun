from __future__ import annotations

import zipfile

from shogun.services import backup_service


def _configure_backup_root(tmp_path, monkeypatch):
    root = tmp_path / "shogun"
    backup_dir = root / "data" / "backups"
    backup_dir.mkdir(parents=True)
    monkeypatch.setattr(backup_service, "_get_project_root", lambda: root)
    monkeypatch.setattr(
        backup_service,
        "load_settings",
        lambda: {**backup_service.DEFAULT_SETTINGS, "backup_dir": str(backup_dir)},
    )
    return root, backup_dir


def test_backup_label_cannot_escape_backup_directory(tmp_path, monkeypatch):
    _root, backup_dir = _configure_backup_root(tmp_path, monkeypatch)
    result = backup_service.create_backup("../../outside")

    assert result["success"] is True
    assert result["filename"].endswith("_outside.zip")
    assert (backup_dir / result["filename"]).is_file()
    assert not (tmp_path / "outside.zip").exists()


def test_delete_rejects_traversal(tmp_path, monkeypatch):
    _root, backup_dir = _configure_backup_root(tmp_path, monkeypatch)
    outside = tmp_path / "shogun_backup_20260727_120000.zip"
    outside.write_bytes(b"keep")

    assert backup_service.delete_backup("../../shogun_backup_20260727_120000.zip") is False
    assert outside.read_bytes() == b"keep"
    assert not any(backup_dir.iterdir())


def test_restore_rejects_zip_slip(tmp_path, monkeypatch):
    _root, backup_dir = _configure_backup_root(tmp_path, monkeypatch)
    archive = backup_dir / "shogun_backup_20260727_120000.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../../escaped.txt", "owned")

    result = backup_service.restore_backup(archive.name)

    assert result["success"] is False
    assert not (tmp_path / "escaped.txt").exists()
