"""Pinned update preparation, code recovery and protected-state behavior."""

from __future__ import annotations

import asyncio
import io
import os
import stat
import threading
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from shogun.services import update_installer as installer


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def installation(tmp_path):
    root, source = tmp_path / "installed", tmp_path / "candidate"
    _write(root, "app.py", "old code")
    _write(root, "version.json", '{"version":"1.0","build":1}')
    _write(root, "data/state.txt", "existing conversation")
    _write(root, "vault/key.txt", "existing test key")
    _write(root, ".env", "existing test configuration")
    _write(root, ".env.server", "existing server credentials")
    _write(root, "configs/profile.json", "existing profile")
    _write(root, "logs/history.txt", "existing audit")
    _write(root, ".venv_wsl/keep.txt", "separate environment")
    _write(root, ".states/pending.txt", "pending task")
    _write(root, "frontend/node_modules/keep.txt", "existing frontend cache")
    _write(source, "app.py", "corrected code")
    _write(source, "version.json", '{"version":"2.0","build":2}')
    _write(source, "pyproject.toml", "[project]\nname='fixture'\n")
    _write(source, "shogun/edition.py", 'EDITION_NAME = "yellow-label"\n')
    _write(source, "shogun/security_maintenance.py", "# candidate policy checked in subprocess\n")
    _write(source, "frontend/package-lock.json", "{}")
    _write(source, "frontend/package.json", "{}")
    return root, source


def _state(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize(
    "stage",
    [
        "Frontend dependency installation",
        "Frontend build",
        "Python dependency installation",
        "Python dependency validation",
        "Security prerequisite validation",
    ],
)
def test_preparation_failure_preserves_all_application_and_user_files(installation, monkeypatch, stage):
    root, source = installation
    original = _state(root)
    monkeypatch.setattr(installer.shutil, "which", lambda *_, **__: "npm")
    stages = []

    def run(command, **kwargs):
        stages.append(kwargs["stage"])
        if kwargs["stage"] == stage:
            raise installer.UpdateInstallError("preparation failed")

    monkeypatch.setattr(installer, "_run_preparation", run)
    with pytest.raises(installer.UpdateInstallError, match="preparation failed"):
        installer.prepare_and_install_update(source, root, {"PATH": "corrected-node"}, "a" * 40)
    assert _state(root) == original
    assert stages[-1] == stage


def test_success_preserves_state_and_retains_original_code(installation, monkeypatch):
    root, source = installation
    original = _state(root)
    for relative in original:
        if relative not in {"app.py", "version.json"}:
            _write(source, relative, "must never replace persistent state")
    monkeypatch.setattr(installer.shutil, "which", lambda *_, **__: "npm")
    commands = []
    monkeypatch.setattr(installer, "_run_preparation", lambda command, **kwargs: commands.append(command))
    manifest, count, backup = installer.prepare_and_install_update(source, root, {"PATH": "safe"}, "a" * 40)
    assert manifest["version"] == "2.0" and count > 0
    assert (root / "app.py").read_text() == "corrected code"
    assert (root / backup / "app.py").read_text() == "old code"
    assert not (root / backup / "data").exists()
    for relative, content in original.items():
        if relative not in {"app.py", "version.json"}:
            assert (root / relative).read_bytes() == content
    assert "ci" in commands[0] and "--strict-ssl=true" in commands[0]
    assert "--engine-strict" in commands[0]
    assert any("certifi>=2026.10.19" in command for command in commands)


def test_mid_promotion_failure_restores_existing_code_and_removes_new_files(installation, monkeypatch):
    root, source = installation
    _write(source, "a-new-file.txt", "new file")
    original = _state(root)
    replace = os.replace
    failed = False

    def fail_once(staged, destination):
        nonlocal failed
        if Path(destination).name == "version.json" and not failed:
            failed = True
            raise OSError("simulated locked destination")
        return replace(staged, destination)

    monkeypatch.setattr(installer.os, "replace", fail_once)
    backup = root / ".states/code-backup"
    with pytest.raises(installer.UpdateInstallError, match="original application files were restored"):
        installer.promote_application_files(source, root, backup)
    current = {name: content for name, content in _state(root).items() if not name.startswith(".states/code-backup/")}
    assert current == original
    assert not list(root.rglob(".shogun-update-*"))


def test_update_lock_excludes_other_workers_and_cleans_up_after_failure(tmp_path):
    with pytest.raises(ValueError):
        with installer.installation_update_lock(tmp_path):
            with pytest.raises(installer.UpdateInstallError, match="Another update"):
                with installer.installation_update_lock(tmp_path):
                    pytest.fail("overlapping updater entered")
            assert (tmp_path / ".states/update-install.lock").is_file()
            raise ValueError("unexpected preparation error")
    assert not (tmp_path / ".states/update-install.lock").exists()


def test_dirty_checkout_stops_before_update_and_does_not_disclose_paths(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        installer.subprocess, "run", lambda *_, **__: SimpleNamespace(returncode=0, stdout=" M private.py\n")
    )
    with pytest.raises(installer.UpdateInstallError, match="Local application changes") as error:
        installer.require_clean_application_checkout(tmp_path)
    assert "private.py" not in str(error.value)


@pytest.mark.parametrize("edition", ["white-label", "legacy-unknown"])
def test_incompatible_edition_is_rejected_before_build_or_dependency_changes(installation, edition):
    _, source = installation
    _write(source, "shogun/edition.py", f'EDITION_NAME = "{edition}"\n')
    with pytest.raises(installer.UpdateInstallError, match="not Yellow Label"):
        installer.validate_update_source(source)


@pytest.mark.parametrize("filename", ["../escape", "root/../../escape", "C:/escape", "root\\..\\escape"])
def test_unsafe_archive_paths_are_rejected_before_extraction(tmp_path, filename):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        member = zipfile.ZipInfo("placeholder")
        member.filename = filename
        bundle.writestr(member, "untrusted content")
    destination = tmp_path / "extracted"
    with pytest.raises(installer.UpdateInstallError, match="Unsafe path"):
        installer.extract_update_archive(archive, destination)
    assert not destination.exists()


def test_archive_symlinks_are_rejected(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        link = zipfile.ZipInfo("root/link")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(link, "../outside")
    with pytest.raises(installer.UpdateInstallError, match="Unsafe path"):
        installer.extract_update_archive(archive, tmp_path / "extracted")


def test_preparation_errors_are_safe_and_never_return_success(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(
        installer.subprocess,
        "run",
        lambda *_, **__: SimpleNamespace(
            returncode=1,
            stdout="private-index-token",
            stderr="private-index-token",
        ),
    )
    with pytest.raises(installer.UpdateInstallError, match="Application files were not changed") as error:
        installer._run_preparation(["pip"], cwd=tmp_path, environment={}, stage="Python dependency installation")
    assert "private-index-token" not in str(error.value) + caplog.text


@pytest.mark.asyncio
async def test_api_returns_failure_on_dependency_error_and_releases_lock(installation, monkeypatch):
    import httpx
    from fastapi import HTTPException

    from shogun.api import updates

    root, source = installation
    original = _state(root)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.writestr("source/" + path.relative_to(source).as_posix(), path.read_bytes())

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, url, **_):
            if "/commits/" in url:
                return SimpleNamespace(status_code=200, json=lambda: {"sha": "a" * 40})
            return SimpleNamespace(status_code=200, content=data.getvalue())

    monkeypatch.setattr(updates, "__file__", str(root / "shogun/api/updates.py"))
    monkeypatch.setattr(updates, "check_python_security", lambda: None)
    monkeypatch.setattr(updates, "node_environment", lambda: {"PATH": "safe"})
    monkeypatch.setattr(updates, "get_update_token", lambda: "")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: Client())

    def fail(*_):
        raise installer.UpdateInstallError("Python dependency installation failed. Application files were not changed.")

    monkeypatch.setattr(updates, "prepare_and_install_update", fail)
    with pytest.raises(HTTPException) as error:
        await updates.apply_update("test-admin")
    assert error.value.status_code == 409
    assert "Python dependency installation failed" in error.value.detail
    assert _state(root) == original


@pytest.mark.asyncio
async def test_cancelled_http_waiter_cannot_release_worker_lock_or_remove_build_source(tmp_path, monkeypatch):
    from shogun.api import updates

    entered, release = threading.Event(), threading.Event()
    sources = []
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as bundle:
        bundle.writestr("source/placeholder", "fixture")

    def prepare(source, *_):
        sources.append(source)
        entered.set()
        assert release.wait(timeout=5)
        raise installer.UpdateInstallError("synthetic cancelled preparation")

    monkeypatch.setattr(updates, "prepare_and_install_update", prepare)
    task = asyncio.create_task(
        asyncio.to_thread(
            updates._install_downloaded_update,
            data.getvalue(),
            tmp_path,
            {"PATH": "safe"},
            "a" * 40,
        )
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert (tmp_path / ".states/update-install.lock").exists()
        assert sources[0].is_dir()
    finally:
        release.set()
    for _ in range(200):
        if not (tmp_path / ".states/update-install.lock").exists():
            break
        await asyncio.sleep(0.01)
    assert not (tmp_path / ".states/update-install.lock").exists()
    assert not sources[0].exists()
