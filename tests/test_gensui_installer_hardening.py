"""Regression tests for the standalone and in-repository Gensui installers."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_SOURCE_SHA = "0774ce5998400963541a19b78e81e97dfea0ad4e"
WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt",
    reason="requires the native Windows command processor",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _write_batch(path: Path, body: str) -> None:
    path.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))


def _prepare_windows_installer(tmp_path: Path) -> tuple[Path, Path]:
    installer_dir = tmp_path / "gensui"
    installer_dir.mkdir()
    shutil.copyfile(ROOT / "gensui" / "install.bat", installer_dir / "install.bat")

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    _write_batch(
        stubs / "python.bat",
        """@echo off
if "%~1"=="--version" (
  echo Python 3.13.0
  exit /b 0
)
if "%~1"=="-c" (
  if defined GENSUI_NODE_VERSION exit /b %FAKE_NODE_GATE%
  exit /b %FAKE_PYTHON_GATE%
)
exit /b 0
""",
    )
    _write_batch(
        stubs / "node.bat",
        """@echo off
if "%~1"=="--version" echo %FAKE_NODE_VERSION%
exit /b 0
""",
    )
    _write_batch(stubs / "pip.bat", "@echo off\nexit /b 0\n")
    _write_batch(
        stubs / "npm.bat",
        """@echo off
if /i "%~1"=="install" exit /b %FAKE_NPM_INSTALL_EXIT%
if /i "%~1"=="run" exit /b %FAKE_NPM_BUILD_EXIT%
exit /b 0
""",
    )
    return installer_dir, stubs


def _run_windows_installer(
    installer_dir: Path,
    stubs: Path,
    **overrides: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": str(stubs) + os.pathsep + env["PATH"],
            "FAKE_PYTHON_GATE": "0",
            "FAKE_NODE_GATE": "0",
            "FAKE_NODE_VERSION": "v22.12.0",
            "FAKE_NPM_INSTALL_EXIT": "0",
            "FAKE_NPM_BUILD_EXIT": "0",
        }
    )
    env.update(overrides)
    return subprocess.run(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "install.bat"],
        cwd=installer_dir,
        env=env,
        input="\n",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
        check=False,
    )


def test_standalone_downloader_uses_an_authorized_immutable_revision() -> None:
    installer = _read("Gensui-Install.bat")
    source_match = re.search(r'^set "SOURCE_SHA=([0-9a-f]{40})"$', installer, re.MULTILINE)

    assert source_match
    assert source_match.group(1) == AUTHORIZED_SOURCE_SHA
    assert "/archive/%SOURCE_SHA%.zip" in installer
    assert "/archive/refs/heads/" not in installer
    assert 'set "BRANCH=' not in installer
    assert "Shogun-%SOURCE_SHA%" in installer


def test_standalone_downloader_uses_private_temp_and_fail_safe_cleanup() -> None:
    installer = _read("Gensui-Install.bat")
    main_body = installer.split(":restore_backup", maxsplit=1)[0]

    assert "[guid]::NewGuid().ToString('N')" in installer
    assert 'set "GENSUI_TEMP_ROOT=%TEMP%\\gensui-install-!TEMP_ID!"' in installer
    assert "SetAccessRuleProtection($true,$false)" in installer
    assert 'set "BACKUP_FILE=!GENSUI_TEMP_ROOT!\\existing.env"' in installer
    assert "%TEMP%\\gensui_setup_backup" not in installer
    assert ":restore_backup" in installer
    assert ":purge_temp" in installer
    assert ":cleanup" in installer
    assert "Remove-Item -LiteralPath $env:GENSUI_TEMP_ROOT -Recurse -Force" in installer
    assert "exit /b 1" not in main_body
    assert "endlocal & exit /b %EXIT_CODE%" in installer
    assert installer.index("call :restore_backup") < installer.index("call :purge_temp")


def test_all_gensui_installers_enforce_supported_runtime_ranges() -> None:
    for relative in ("Gensui-Install.bat", "gensui/install.bat", "gensui/install.sh"):
        installer = _read(relative)
        assert "sys.version_info >= (3, 10)" in installer
        assert "(22, 12) <= p < (25, 0)" in installer


def test_inner_installers_fail_closed_and_protect_generated_secrets() -> None:
    windows = _read("gensui/install.bat")
    unix = _read("gensui/install.sh")

    assert re.search(r"call npm install[^\n]+\n\s+if errorlevel 1", windows)
    assert re.search(r"call npm run build[^\n]+\n\s+if errorlevel 1", windows)
    assert "System.Security.AccessControl.FileSecurity" in windows
    assert 'if defined ENV_CREATED del /f /q ".env"' in windows
    assert "endlocal & exit /b %EXIT_CODE%" in windows

    assert "umask 077" in unix
    assert 'mktemp -d "${TMPDIR:-/tmp}/gensui-install.XXXXXX"' in unix
    assert "trap cleanup_installer EXIT" in unix
    assert 'rm -rf -- "${GENSUI_TEMP_DIR:?}"' in unix
    assert 'ENV_TEMP="$GENSUI_TEMP_DIR/.env"' in unix
    assert 'install -m 600 "$ENV_TEMP" .env' in unix
    assert 'rm -f -- "$ENV_TEMP"' in unix
    assert "if ! npm install --silent" in unix
    assert "if ! npm run build --silent" in unix


@WINDOWS_ONLY
def test_windows_installer_rejects_unsupported_python(tmp_path: Path) -> None:
    installer_dir, stubs = _prepare_windows_installer(tmp_path)
    result = _run_windows_installer(
        installer_dir,
        stubs,
        FAKE_PYTHON_GATE="1",
    )

    assert result.returncode != 0
    assert "requires Python 3.10 or newer" in result.stdout


@WINDOWS_ONLY
def test_windows_installer_rejects_unsupported_node(tmp_path: Path) -> None:
    installer_dir, stubs = _prepare_windows_installer(tmp_path)
    result = _run_windows_installer(
        installer_dir,
        stubs,
        FAKE_NODE_GATE="1",
        FAKE_NODE_VERSION="v25.0.0",
    )

    assert result.returncode != 0
    assert "requires 22.12 or newer, but below 25" in result.stdout


@pytest.mark.parametrize(
    ("install_exit", "build_exit", "expected_error"),
    [
        ("9", "0", "Failed to install Gensui frontend dependencies"),
        ("0", "9", "Failed to build the Gensui Admin UI"),
    ],
)
@WINDOWS_ONLY
def test_windows_installer_propagates_npm_failures(
    tmp_path: Path,
    install_exit: str,
    build_exit: str,
    expected_error: str,
) -> None:
    installer_dir, stubs = _prepare_windows_installer(tmp_path)
    activate = installer_dir / ".venv" / "Scripts" / "activate.bat"
    activate.parent.mkdir(parents=True)
    _write_batch(activate, "@echo off\nexit /b 0\n")
    frontend = installer_dir / "frontend"
    frontend.mkdir()
    (frontend / "package.json").write_text("{}", encoding="utf-8")

    result = _run_windows_installer(
        installer_dir,
        stubs,
        FAKE_NPM_INSTALL_EXIT=install_exit,
        FAKE_NPM_BUILD_EXIT=build_exit,
    )

    assert result.returncode != 0
    assert expected_error in result.stdout
