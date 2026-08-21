from __future__ import annotations

import io
import json
import zipfile

from shogun.api import system
from shogun.services import backup_service, release_metadata

RELEASE = {
    "product": "Shogun AFM",
    "version": "9.8.7",
    "build": 654,
    "release_id": "9.8.7+build.654",
    "release_date": "2026-08-21T12:00:00Z",
    "git_sha": "a" * 40,
    "distribution_status": "tracked_checkout_clean",
    "working_tree_modified": False,
}


def test_release_metadata_uses_matching_build_evidence_without_instance_identifiers(tmp_path, monkeypatch):
    (tmp_path / "version.json").write_text(
        json.dumps({
            "name": "Shogun AFM",
            "version": "9.8.7",
            "build": 654,
            "channel": "stable",
            "released": "2026-08-21T12:00:00Z",
            "changelog": "Traceable release",
            "security_changes": ["Hardened a boundary", 42, ""],
            "breaking_changes": ["Configuration review required"],
            "shogun_id": "must-not-leak",
        }),
        encoding="utf-8",
    )
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "release_metadata.json").write_text(
        json.dumps({"version": "9.8.7", "build": 654, "git_sha": "A" * 40}),
        encoding="utf-8",
    )
    monkeypatch.delenv("SHOGUN_GIT_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(release_metadata, "_git_tracked_modifications", lambda _root: None)

    metadata = release_metadata.get_release_metadata(tmp_path)

    assert metadata["release_id"] == "9.8.7+build.654"
    assert metadata["git_sha"] == "a" * 40
    assert metadata["security_changes"] == ["Hardened a boundary"]
    assert metadata["official_repository"] == "AlphaHorizon-AI/Shogun"
    assert metadata["distribution_status"] == "release_evidence_present"
    assert "shogun_id" not in metadata
    assert "instance" not in metadata


def test_release_metadata_rejects_stale_build_evidence_and_stale_checkout(tmp_path, monkeypatch):
    (tmp_path / "version.json").write_text(
        json.dumps({"version": "2.0.0", "build": 2}),
        encoding="utf-8",
    )
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "release_metadata.json").write_text(
        json.dumps({"version": "1.0.0", "build": 1, "git_sha": "b" * 40}),
        encoding="utf-8",
    )
    monkeypatch.delenv("SHOGUN_GIT_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(release_metadata, "_git_sha", lambda _root: None)
    monkeypatch.setattr(release_metadata, "_git_tracked_modifications", lambda _root: None)

    assert release_metadata.get_release_metadata(tmp_path)["git_sha"] is None


def test_updater_evidence_wins_over_stale_checkout_and_reaches_about_payload(tmp_path, monkeypatch):
    manifest = {
        "name": "Shogun AFM",
        "version": "3.2.1",
        "build": 321,
        "released": "2026-08-21T16:00:00Z",
    }
    (tmp_path / "version.json").write_text(json.dumps(manifest), encoding="utf-8")
    release_metadata.write_release_metadata_evidence(tmp_path, manifest, "d" * 40)
    monkeypatch.setenv("SHOGUN_GIT_SHA", "c" * 40)  # stale container/build identity
    monkeypatch.setattr(release_metadata, "_git_sha", lambda _root: "b" * 40)  # stale checkout HEAD
    monkeypatch.setattr(release_metadata, "_git_tracked_modifications", lambda _root: True)

    about_payload = release_metadata.get_release_metadata(tmp_path)

    assert about_payload["version"] == "3.2.1"
    assert about_payload["build"] == 321
    assert about_payload["git_sha"] == "d" * 40
    assert about_payload["working_tree_modified"] is None
    assert about_payload["distribution_status"] == "update_overlay_unverified"


def test_updater_with_unavailable_commit_never_reports_stale_environment_or_checkout(tmp_path, monkeypatch):
    manifest = {"name": "Shogun AFM", "version": "4.0.0", "build": 400}
    (tmp_path / "version.json").write_text(json.dumps(manifest), encoding="utf-8")
    release_metadata.write_release_metadata_evidence(tmp_path, manifest, None)
    monkeypatch.setenv("SHOGUN_GIT_SHA", "c" * 40)
    monkeypatch.setattr(release_metadata, "_git_sha", lambda _root: "b" * 40)
    monkeypatch.setattr(release_metadata, "_git_tracked_modifications", lambda _root: True)

    assert release_metadata.get_release_metadata(tmp_path)["git_sha"] is None


def test_modified_tracked_source_preserves_base_sha_and_marks_distribution(tmp_path, monkeypatch):
    (tmp_path / "version.json").write_text(
        json.dumps({"name": "Shogun AFM", "version": "5.0.0", "build": 500}),
        encoding="utf-8",
    )
    monkeypatch.delenv("SHOGUN_GIT_SHA", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setattr(release_metadata, "_git_sha", lambda _root: "e" * 40)
    monkeypatch.setattr(release_metadata, "_git_tracked_modifications", lambda _root: True)

    metadata = release_metadata.get_release_metadata(tmp_path)

    assert metadata["git_sha"] == "e" * 40
    assert metadata["git_sha_source"] == "git_checkout"
    assert metadata["working_tree_modified"] is True
    assert metadata["distribution_status"] == "locally_modified"


def test_database_export_manifest_uses_canonical_release_identity(monkeypatch):
    monkeypatch.setattr(system, "get_release_metadata", lambda: RELEASE)

    archive = system._build_zip({"agents": []}, include_db=False)

    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["shogun_version"] == "9.8.7"
    assert manifest["shogun_build"] == 654
    assert manifest["shogun_release_id"] == "9.8.7+build.654"
    assert manifest["shogun_git_sha"] == "a" * 40
    assert manifest["shogun_distribution_status"] == "tracked_checkout_clean"
    assert manifest["shogun_working_tree_modified"] is False


def test_installation_backup_manifest_uses_canonical_release_identity(tmp_path, monkeypatch):
    root = tmp_path / "shogun"
    backup_dir = root / "data" / "backups"
    backup_dir.mkdir(parents=True)
    (root / "version.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backup_service, "_get_project_root", lambda: root)
    monkeypatch.setattr(
        backup_service,
        "load_settings",
        lambda: {**backup_service.DEFAULT_SETTINGS, "backup_dir": str(backup_dir)},
    )
    monkeypatch.setattr(backup_service, "get_release_metadata", lambda: RELEASE)

    result = backup_service.create_backup("release-identity")

    assert result["success"] is True
    with zipfile.ZipFile(backup_dir / result["filename"]) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    assert manifest["shogun_version"] == "9.8.7"
    assert manifest["shogun_build"] == 654
    assert manifest["shogun_release_id"] == "9.8.7+build.654"
    assert manifest["shogun_git_sha"] == "a" * 40
    assert manifest["shogun_distribution_status"] == "tracked_checkout_clean"
    assert manifest["shogun_working_tree_modified"] is False
