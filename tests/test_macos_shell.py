"""Execute the desktop shell flows with isolated, deterministic tool substitutes.

These tests also run with macOS /bin/bash 3.2. They exercise shell control flow;
the native CI job separately installs real dependencies and starts the server.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH = os.environ.get("SHOGUN_TEST_BASH") or (
    str(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe")
    if os.name == "nt" else "/bin/bash"
)
pytestmark = pytest.mark.skipif(not Path(BASH).is_file(), reason="Bash is unavailable")


def _shell_path(path: Path) -> str:
    value = path.resolve().as_posix()
    return f"/{value[0].lower()}{value[2:]}" if os.name == "nt" else value


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    path.chmod(0o755)


@pytest.fixture
def shell_install(tmp_path):
    root = tmp_path / "Shogun with spaces $cash 'quote"
    binaries = tmp_path / "bin"
    for relative in ("install.sh", "start.sh", "uninstall.sh", "Shogun-Install.command",
                     "scripts/create_shortcut_mac.sh"):
        _write(root / relative, (ROOT / relative).read_text(encoding="utf-8"))
    _write(root / "pyproject.toml", "[project]\nname='fixture'\n")
    _write(root / "shogun/__main__.py", "")
    _write(root / "frontend/package-lock.json", "{}")
    _write(binaries / "uname", "#!/bin/bash\necho Darwin\n")
    _write(binaries / "sw_vers", '#!/bin/bash\necho "${TEST_MACOS_VERSION:-14.0}"\n')
    _write(binaries / "node", '#!/bin/bash\n[ "${FAIL_STAGE:-}" != node ]\n')
    _write(binaries / "npm", '''#!/bin/bash
echo "npm:$*" >> "$TEST_CALLS"
if [ "$1" = ci ] && [ "${FAIL_STAGE:-}" = npm-ci ]; then exit 31; fi
if [ "$1" = run ]; then
    if [ "${FAIL_STAGE:-}" = npm-build ]; then exit 32; fi
    mkdir -p dist
    echo '<html>fixture</html>' > dist/index.html
fi
''')
    _write(binaries / "python3.12", '''#!/bin/bash
echo "python:$*" >> "$TEST_CALLS"
case "$*" in
    *platform.machine*) [ "${FAIL_STAGE:-}" != architecture ]; exit $? ;;
    *sys.version_info*) exit 0 ;;
    '--version') echo 'Python 3.12.0'; exit 0 ;;
    '-m venv venv')
        mkdir -p venv/bin
        cp "$0" venv/bin/python
        chmod +x venv/bin/python
        echo ':' > venv/bin/activate
        exit 0 ;;
    '-m pip '*) [ "${FAIL_STAGE:-}" != pip ]; exit $? ;;
    '-m shogun.environment_bootstrap '*) echo fixture > .env; exit 0 ;;
    '-m shogun.telemetry.cli '*) exit 0 ;;
    '-m playwright '*) [ "${FAIL_STAGE:-}" != browser ]; exit $? ;;
    *asyncio.run*) [ "${FAIL_STAGE:-}" != database ]; exit $? ;;
    '-m shogun')
        echo "launch:$PWD:${SHOGUN_BROWSER_URL:-}:${SHOGUN_LAUNCHER_MANAGED:-}" >> "$TEST_CALLS"
        if [ "${TEST_RESTART:-}" = yes ] && [ ! -f restarted ]; then
            mkdir -p .states
            touch .states/restart-requested restarted
        fi
        exit 0 ;;
esac
''')
    _write(binaries / "curl", '#!/bin/bash\necho network-called >> "$TEST_CALLS"\nexit 33\n')
    # Record removal targets without actually deleting anything in shell tests.
    _write(binaries / "rm", '#!/bin/bash\nprintf "rm:%s\\n" "$@" >> "$TEST_CALLS"\n')
    return root, binaries, tmp_path


def _run(fixture, script="install.sh", *args, stdin="", **overrides):
    root, binaries, temporary = fixture
    environment = os.environ.copy()
    environment.pop("PYTHON_CMD", None)
    environment.pop("BASH_ENV", None)
    environment.update({
        "HOME": _shell_path(temporary / "home"),
        "TMPDIR": _shell_path(temporary),
        "TEST_CALLS": _shell_path(temporary / "calls.log"),
        "SHOGUN_TELEMETRY": "off",
        **overrides,
    })
    (temporary / "home").mkdir(exist_ok=True)
    result = subprocess.run(
        [BASH, "-c", 'export PATH="$1:/usr/bin:/bin"; shift; exec /bin/bash "$@"',
         "shogun-test", _shell_path(binaries), _shell_path(root / script), *args],
        cwd=temporary, env=environment, input=stdin.encode(), capture_output=True, timeout=30,
    )
    return subprocess.CompletedProcess(result.args, result.returncode,
                                       result.stdout.decode("utf-8"), result.stderr.decode("utf-8", errors="replace"))


def _calls(fixture):
    path = fixture[2] / "calls.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_noninteractive_install_builds_and_does_not_launch_when_requested(shell_install):
    result = _run(shell_install, "install.sh", "--no-start")
    assert result.returncode == 0, result.stderr
    assert "Installation complete." in result.stdout
    calls = _calls(shell_install)
    assert "npm:ci" in calls and "npm:run build" in calls
    assert "launch:" not in calls
    assert ".[ronin]" not in calls
    app = shell_install[2] / "home/Desktop/Shogun.app/Contents"
    assert plistlib.loads((app / "Info.plist").read_bytes())["CFBundleExecutable"] == "Shogun"
    command = app / "Resources/Shogun.command"
    assert command.is_file()


@pytest.mark.parametrize("stage", ["pip", "browser", "database", "npm-ci", "npm-build"])
def test_install_failure_never_announces_success_or_starts_server(shell_install, stage):
    result = _run(shell_install, FAIL_STAGE=stage)
    assert result.returncode != 0
    assert "Installation complete" not in result.stdout
    assert "launch:" not in _calls(shell_install)


@pytest.mark.parametrize("script", ["install.sh", "Shogun-Install.command"])
@pytest.mark.parametrize("environment,message", [
    ({"FAIL_STAGE": "architecture"}, "arm64 Python"),
    ({"TEST_MACOS_VERSION": "13.7"}, "macOS 14"),
])
def test_unsupported_mac_stops_before_download_or_install(shell_install, script, environment, message):
    result = _run(shell_install, script, **environment)
    assert result.returncode != 0
    assert message in result.stdout
    assert "network-called" not in _calls(shell_install)
    assert "-m pip" not in _calls(shell_install)


def test_startup_build_failure_stops_before_launch(shell_install):
    root, binaries, _ = shell_install
    _write(root / "venv/bin/activate", ":\n")
    shutil.copyfile(binaries / "python3.12", root / "venv/bin/python")
    (root / "venv/bin/python").chmod(0o755)
    result = _run(shell_install, "start.sh", FAIL_STAGE="npm-build")
    assert result.returncode != 0
    assert "Frontend built" not in result.stdout
    assert "launch:" not in _calls(shell_install)


def test_existing_rosetta_venv_is_rejected_before_package_install(shell_install):
    root, _, _ = shell_install
    _write(root / "venv/bin/activate", ":\n")
    _write(root / "venv/bin/python", '''#!/bin/bash
case "$*" in
    *platform.machine*) exit 1 ;;
esac
exit 0
''')
    result = _run(shell_install)
    assert result.returncode != 0
    assert "Existing venv is not arm64" in result.stdout
    assert "-m pip" not in _calls(shell_install)


@pytest.mark.parametrize("script", ["install.sh", "Shogun-Install.command"])
def test_unsupported_node_stops_before_download_or_install(shell_install, script):
    result = _run(shell_install, script, FAIL_STAGE="node")
    assert result.returncode != 0
    assert "Node.js 22.12" in result.stdout
    assert "network-called" not in _calls(shell_install)
    assert "-m pip" not in _calls(shell_install)


def test_install_launch_uses_supervisor_and_preserves_setup_url(shell_install):
    result = _run(shell_install)
    assert result.returncode == 0, result.stderr
    assert "http://localhost:8000/setup:true" in _calls(shell_install)


def test_generated_command_quotes_special_characters_in_install_path(shell_install):
    result = _run(shell_install, "install.sh", "--no-start")
    assert result.returncode == 0, result.stderr
    root, _, temporary = shell_install
    command = temporary / "home/Desktop/Shogun.app/Contents/Resources/Shogun.command"
    shutil.copyfile(command, root / "generated.command")
    result = _run(shell_install, "generated.command")
    assert result.returncode == 0, result.stderr
    assert f"launch:{_shell_path(root)}:" in _calls(shell_install)


def test_uninstaller_refuses_unrecognized_directory(shell_install):
    (shell_install[0] / "shogun/__main__.py").unlink()
    result = _run(shell_install, "uninstall.sh")
    assert result.returncode != 0
    assert "Refusing to remove" in result.stderr
    assert "rm:" not in _calls(shell_install)


def test_uninstaller_targets_installation_instead_of_callers_directory(shell_install):
    result = _run(shell_install, "uninstall.sh", stdin="Y\n")
    assert result.returncode == 0, result.stderr
    calls = _calls(shell_install)
    assert f"rm:{_shell_path(shell_install[0])}\n" in calls
    assert f"rm:{_shell_path(shell_install[2])}\n" not in calls


def test_downloader_forwards_options_and_preserves_existing_setup(shell_install):
    root, binaries, temporary = shell_install
    commit = "a" * 40
    _write(root / "version.json", '{"version":"1.0.0"}')
    _write(root / "configs/setup.json", '{"source":"archive"}')
    archive = temporary / "source.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for path in root.rglob("*"):
            if path.is_file():
                package.write(path, f"Shogun-{commit}/{path.relative_to(root).as_posix()}")
    _write(temporary / "home/Shogun/configs/setup.json", '{"source":"user"}')
    _write(temporary / "home/Shogun/data/memory.txt", "keep me")
    _write(binaries / "curl", f'''#!/bin/bash
if [ "$2" = '-o' ]; then
    cp "$TEST_ARCHIVE" "$3"
else
    echo '  "sha": "{commit}",'
fi
''')
    result = _run(shell_install, "Shogun-Install.command", "--no-start", "--ronin=on",
                  TEST_ARCHIVE=_shell_path(archive))
    assert result.returncode == 0, result.stderr
    assert "launch:" not in _calls(shell_install)
    assert ".[ronin]" in _calls(shell_install)
    installed = temporary / "home/Shogun"
    assert (installed / "configs/setup.json").read_text() == '{"source":"user"}'
    assert (installed / "data/memory.txt").read_text() == "keep me"


def test_yellow_label_downloader_refuses_existing_productised_installation(shell_install):
    root, binaries, temporary = shell_install
    commit = "a" * 40
    _write(root / "version.json", '{"version":"1.0.0"}')
    _write(temporary / "home/Shogun/shogun/productisation/distribution.py", 'EDITION = "white_label"\n')
    _write(temporary / "home/Shogun/data/memory.txt", "keep me")
    archive = temporary / "source.zip"
    with zipfile.ZipFile(archive, "w") as package:
        for path in root.rglob("*"):
            if path.is_file():
                package.write(path, f"Shogun-{commit}/{path.relative_to(root).as_posix()}")
    _write(binaries / "curl", f'''#!/bin/bash
if [ "$2" = '-o' ]; then
    cp "$TEST_ARCHIVE" "$3"
else
    echo '  "sha": "{commit}",'
fi
''')
    result = _run(shell_install, "Shogun-Install.command", TEST_ARCHIVE=_shell_path(archive))
    assert result.returncode != 0
    assert "productised edition" in result.stdout
    assert "-m pip" not in _calls(shell_install)
    assert (temporary / "home/Shogun/data/memory.txt").read_text() == "keep me"


@pytest.mark.skipif(os.name == "nt", reason="native POSIX symlinks required")
def test_launcher_resolves_relative_symlink_without_gnu_readlink(shell_install):
    result = _run(shell_install, "install.sh", "--no-start")
    assert result.returncode == 0, result.stderr
    root, binaries, _ = shell_install
    _write(binaries / "readlink", '#!/bin/bash\n[ "$1" != -f ] || exit 1\nexec /usr/bin/readlink "$@"\n')
    (root / "links").mkdir()
    (root / "links/start-link").symlink_to("../start.sh")
    result = _run(shell_install, "links/start-link")
    assert result.returncode == 0, result.stderr
    assert f"launch:{_shell_path(root)}:" in _calls(shell_install)


@pytest.mark.parametrize("relative", [
    "Shogun-Install.command", "install.sh", "start.sh", "uninstall.sh",
    "Shogun-Server-Install.sh", "scripts/create_shortcut_mac.sh",
])
def test_bash_syntax_and_lf_line_endings(relative):
    assert b"\r\n" not in (ROOT / relative).read_bytes()
    result = subprocess.run([BASH, "-n", _shell_path(ROOT / relative)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
