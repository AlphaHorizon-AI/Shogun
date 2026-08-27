from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_desktop_installer_pins_archive_and_records_release_evidence():
    installer = _read("Shogun-Install.bat")

    assert "archive/refs/heads" not in installer
    assert "repos/%REPO%/commits/%BRANCH%" in installer
    assert "archive/%SOURCE_COMMIT%.zip" in installer
    assert "Shogun-%SOURCE_COMMIT%" in installer
    assert "if not defined SOURCE_COMMIT" in installer
    assert "shogun-install-'+[Guid]::NewGuid()" in installer
    assert 'SETUP_BACKUP=%TEMP_ROOT%\\setup.json' in installer
    assert "%TEMP%\\shogun_setup_backup.json" not in installer
    assert "call :cleanup" in installer
    assert 'if not exist "%SOURCE_DIR%\\version.json"' in installer
    assert "if errorlevel 8" in installer
    assert 'fc /b "%SOURCE_DIR%\\version.json" "%INSTALL_DIR%\\version.json"' in installer
    assert "write_release_metadata_evidence.py" in installer
    assert '--git-sha "%SOURCE_COMMIT%"' in installer


def test_shogun_installers_enforce_declared_python_and_node_engines():
    for relative_path in (
        "Shogun-Install.bat",
        "Shogun-Install.command",
        "install.bat",
        "install.sh",
    ):
        installer = _read(relative_path)
        assert "sys.version_info >= (3, 10)" in installer
        assert "major===22&&minor>=12" in installer
        assert "major<25" in installer


def test_mac_desktop_installer_pins_archive_and_uses_private_temporary_state():
    installer = _read("Shogun-Install.command")

    assert "archive/refs/heads" not in installer
    assert "commits/$BRANCH" in installer
    assert "archive/$SOURCE_COMMIT.zip" in installer
    assert "Shogun-$SOURCE_COMMIT" in installer
    assert 'TEMP_ROOT="$(mktemp -d ' in installer
    assert 'SETUP_BACKUP="$TEMP_ROOT/setup.json"' in installer
    assert "trap cleanup EXIT" in installer
    assert 'chmod 600 "$SETUP_BACKUP"' in installer
    assert "/tmp/shogun_setup_backup.json" not in installer
    assert 'cmp -s "$EXTRACTED/version.json" "$INSTALL_DIR/version.json"' in installer
    assert "write_release_metadata_evidence.py" in installer


def test_repair_updater_pins_public_and_private_archives_and_never_fails_on_evidence():
    installer = _read("Shogun-Repair-Update.bat")

    assert "archive/refs/heads" not in installer
    assert "zipball/%BRANCH%" not in installer
    assert "repos/%REPO%/commits/%BRANCH%" in installer
    assert "archive/'+$sha+'.zip" in installer
    assert "zipball/'+$sha" in installer
    assert "source-commit.txt" in installer
    assert "shogun-update-'+[Guid]::NewGuid()" in installer
    assert "%TEMP%\\shogun-inplace-update" not in installer
    assert 'fc /b "%SOURCE_DIR%\\version.json" "%INSTALL_DIR%\\version.json"' in installer
    assert "write_release_metadata_evidence.py" in installer
    assert "The update was applied, but release provenance could not be recorded" in installer


def test_server_installers_pin_source_and_persist_vcs_ref_for_compose():
    windows = _read("Shogun-Server-Install.bat")
    shell = _read("Shogun-Server-Install.sh")

    for installer in (windows, shell):
        assert "archive/refs/heads" not in installer
        assert "commits/" in installer
        assert "SOURCE_COMMIT" in installer
        assert "VCS_REF" in installer
        assert "python -m shogun.setup_link" in installer
        assert "?infrastructure_token=" not in installer
        assert "--show-setup-link" in installer
        assert "Share pseudonymous installation statistics?" in installer
        assert "Share anonymous installation statistics?" not in installer
        assert "change-me-to-an-independent-a2a-encryption-key" in installer
        assert "A2A_SECRET" in installer

    assert "archive/%SOURCE_COMMIT%.zip" in windows
    assert "Shogun-%SOURCE_COMMIT%" in windows
    assert "set \"VCS_REF=%SOURCE_COMMIT%\"" in windows
    assert "shogun-server-install-'+[Guid]::NewGuid()" in windows
    assert "%TEMP%\\shogun-server-install" not in windows
    assert 'set "ENV_BACKUP=%TEMP_ROOT%\\env.server.backup"' in windows
    assert 'del /f /q "%ENV_BACKUP%"' in windows
    assert ":ready\ncall :cleanup" in windows.replace("\r\n", "\n")
    assert ":failed\ncall :cleanup" in windows.replace("\r\n", "\n")
    assert "Remove-Item -LiteralPath $root -Recurse -Force" in windows
    assert "shogun-server-install-[0-9a-fA-F]{32}" in windows
    assert "Temporary installer data remains at" in windows
    assert 'rmdir /s /q "%TEMP_ROOT%"' not in windows
    assert "set_env_value VCS_REF" in shell
    assert "archive/$SOURCE_COMMIT.zip" in shell
    assert "Shogun-$SOURCE_COMMIT" in shell
    assert 'rm -f -- "$ENV_BACKUP"' in shell
    assert 'if [ -e "$ENV_BACKUP" ]' in shell
    assert 'ENV_BACKUP=""' in shell
    assert '[ -t 1 ] && [ -z "${CI:-}" ]' in shell
    assert "credential-bearing setup link was withheld" in shell
    assert "[Console]::IsOutputRedirected" in windows
    captured_redirect_probe = (
        'for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command '
        '"if([Environment]::UserInteractive'
    )
    assert captured_redirect_probe not in windows
    assert "if defined INTERACTIVE_OUTPUT start" in windows
    assert "credential-bearing setup link was withheld" in windows


def test_server_setup_bootstrap_is_fragment_only_and_frontend_consumes_it_before_react():
    helper = _read("shogun/setup_link.py")
    frontend_entry = _read("frontend/src/main.tsx")
    frontend_auth = _read("frontend/src/lib/infrastructureAuth.ts")
    gate = _read("frontend/src/App.tsx")

    assert "/setup#infrastructure_token=" in helper
    assert "/setup?infrastructure_token=" not in helper
    assert "consumeInfrastructureTokenFromLocation()" in frontend_entry
    assert frontend_entry.index("consumeInfrastructureTokenFromLocation()") < frontend_entry.index(
        "createRoot("
    )
    assert "window.history.replaceState" in frontend_auth
    assert frontend_auth.index("window.history.replaceState") < frontend_auth.index(
        "setInfrastructureAdminToken(token)"
    )
    assert ".catch(() => setStatus('ready'))" not in gate
    assert "setup_complete ?? true" not in gate
    assert "typeof complete !== 'boolean'" in gate
    assert "Primary Admin authorization required" in gate


def test_compose_and_container_build_preserve_source_revision():
    compose = _read("docker-compose.server.yml")
    dockerfile = _read("Dockerfile")
    workflow = _read(".github/workflows/security-hardening.yml")

    assert "VCS_REF: ${VCS_REF:-unknown}" in compose
    assert "SHOGUN_BUILD_ID" not in compose
    assert "SHOGUN_BUILD_ID" not in _read(".env.server.example")
    assert "ARG VCS_REF=unknown" in dockerfile
    assert 'org.opencontainers.image.revision="${VCS_REF}"' in dockerfile
    assert "SHOGUN_GIT_SHA=${VCS_REF}" in dockerfile
    assert "COPY LICENSE.md /build/LICENSE.md" in dockerfile
    assert 'docker build --build-arg VCS_REF="${GITHUB_SHA}"' in workflow


def test_release_evidence_helper_writes_only_non_sensitive_release_identity(tmp_path):
    root = tmp_path / "archive"
    service_dir = root / "shogun" / "services"
    service_dir.mkdir(parents=True)
    (root / "shogun" / "__init__.py").write_text("", encoding="utf-8")
    (service_dir / "__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(
        ROOT / "shogun" / "services" / "release_metadata.py",
        service_dir / "release_metadata.py",
    )
    (root / "version.json").write_text(
        json.dumps({
            "name": "Shogun AFM",
            "version": "9.1.2",
            "build": 912,
            "released": "2026-08-21T12:00:00Z",
            "instance_id": "must-not-leak",
        }),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "write_release_metadata_evidence.py"),
            "--root",
            str(root),
            "--git-sha",
            "a" * 40,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    evidence = json.loads((root / "configs" / "release_metadata.json").read_text())
    assert evidence["version"] == "9.1.2"
    assert evidence["build"] == 912
    assert evidence["git_sha"] == "a" * 40
    assert evidence["source_overlay"] is True
    assert "instance_id" not in evidence


@pytest.mark.skipif(
    os.name == "nt" or shutil.which("bash") is None,
    reason="a native bash runtime is not installed",
)
def test_server_shell_installer_has_valid_bash_syntax():
    for installer in ("Shogun-Install.command", "Shogun-Server-Install.sh"):
        subprocess.run(
            ["bash", "-n", str(ROOT / installer)],
            check=True,
            capture_output=True,
            text=True,
        )
