"""Prepare pinned Yellow Label updates before promoting application files.

Persistent state is never part of promotion or code recovery. Package installation
in the existing environment is not transactional; failures report that limitation.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from shogun.security_maintenance import CERTIFI_MINIMUM

logger = logging.getLogger(__name__)
PROTECTED_TOP_LEVEL = frozenset(
    {
        "data",
        "venv",
        "node_modules",
        "configs",
        "vault",
        "logs",
        "scratch",
        ".states",
        ".git",
        ".agents",
        ".codex",
        "AGENTS.md",
    }
)


class UpdateInstallError(RuntimeError):
    """Safe operator-facing update failure."""


@contextmanager
def installation_update_lock(root: Path):
    """Coordinate workers/processes; a crashed updater requires operator recovery."""
    state = root / ".states"
    state.mkdir(exist_ok=True)
    lock = state / "update-install.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise UpdateInstallError("Another update or an interrupted update requires attention before retrying.") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def require_clean_application_checkout(root: Path) -> None:
    if not (root / ".git").exists():
        return
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode or result.stdout.strip():
        raise UpdateInstallError("Local application changes must be preserved and reviewed before applying an update.")


def extract_update_archive(archive: Path, destination: Path) -> Path:
    """Accept one ordinary source tree, without traversal, links or device paths."""
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if not members or len(members) > 50_000 or sum(item.file_size for item in members) > 1_000_000_000:
            raise UpdateInstallError("The update archive is empty or exceeds supported size limits.")
        roots = set()
        for item in members:
            path = PurePosixPath(item.filename)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or ":" in item.filename
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise UpdateInstallError("Unsafe path found in update package.")
            roots.add(path.parts[0])
        if len(roots) != 1:
            raise UpdateInstallError("The update package must contain one source directory.")
        bundle.extractall(destination)
    source = destination / roots.pop()
    if not source.is_dir():
        raise UpdateInstallError("The update package has no source directory.")
    return source


def validate_update_source(source: Path) -> dict:
    for name in (
        "pyproject.toml",
        "version.json",
        "shogun/edition.py",
        "shogun/security_maintenance.py",
        "frontend/package-lock.json",
        "frontend/package.json",
    ):
        if not (source / name).is_file():
            raise UpdateInstallError("The pinned update is missing required release files.")
    try:
        manifest = json.loads((source / "version.json").read_text(encoding="utf-8"))
        edition = ast.parse((source / "shogun/edition.py").read_text(encoding="utf-8"))
        edition_names = [
            node.value.value
            for node in edition.body
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and any(isinstance(target, ast.Name) and target.id == "EDITION_NAME" for target in node.targets)
        ]
        if (
            not isinstance(manifest, dict)
            or not isinstance(manifest.get("version"), str)
            or type(manifest.get("build")) is not int
            or edition_names != ["yellow-label"]
        ):
            raise ValueError("Incompatible release identity")
    except (ValueError, SyntaxError, OSError) as exc:
        raise UpdateInstallError("The pinned release has invalid metadata or is not Yellow Label.") from exc
    return manifest


def _run_preparation(command: list[str], *, cwd: Path, environment: dict[str, str], stage: str) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateInstallError(
            f"{stage} failed. Application files were not changed; dependency changes may need recovery."
        ) from exc
    if result.returncode:
        # Package-manager output may contain private index URLs or tokens.
        logger.error("Update preparation failed (stage=%s, exit_code=%s)", stage, result.returncode)
        raise UpdateInstallError(
            f"{stage} failed. Application files were not changed; dependency changes may need recovery."
        )


def _protected(relative: Path) -> bool:
    first = relative.parts[0]
    return (
        first in PROTECTED_TOP_LEVEL
        or first.startswith(".venv")
        or first.startswith(".env")
        and first not in {".env.example", ".env.server.example"}
        or any(part in {"node_modules", "__pycache__"} for part in relative.parts)
    )


def promote_application_files(source: Path, root: Path, backup: Path) -> int:
    """Keep original code for recovery and restore it on a partial copy failure."""
    entries = []
    for item in sorted(source.rglob("*")):
        relative = item.relative_to(source)
        if _protected(relative) or not item.is_file():
            continue
        destination = root / relative
        if not destination.resolve().is_relative_to(root.resolve()) or destination.is_symlink():
            raise UpdateInstallError("An application path escapes the installation; update stopped.")
        if destination.exists() and not destination.is_file():
            raise UpdateInstallError("An application file conflicts with an existing directory.")
        original = backup / relative if destination.exists() else None
        if original is not None:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(destination, original)
        entries.append((item, destination, original))

    promoted = []
    try:
        for item, destination, original in entries:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".shogun-update-", delete=False) as handle:
                staged = Path(handle.name)
            try:
                shutil.copy2(item, staged)
                os.replace(staged, destination)
                promoted.append((destination, original))
            finally:
                staged.unlink(missing_ok=True)
    except OSError as exc:
        try:
            for destination, original in reversed(promoted):
                if original is None:
                    destination.unlink()
                else:
                    os.replace(original, destination)
        except OSError as recovery_error:
            logger.error("Application code recovery failed (error_type=%s)", type(recovery_error).__name__)
            raise UpdateInstallError(
                "Update copy and code recovery failed. Stop and use the retained code backup; "
                "dependency changes may remain."
            ) from recovery_error
        raise UpdateInstallError(
            "Update copy failed; original application files were restored. Dependency changes may remain."
        ) from exc
    return len(promoted)


def prepare_and_install_update(
    source: Path, root: Path, environment: dict[str, str], source_commit: str
) -> tuple[dict, int, str]:
    manifest = validate_update_source(source)
    frontend = source / "frontend"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm", path=environment["PATH"])
    if not npm:
        raise UpdateInstallError("npm is unavailable in the corrected Node environment.")
    _run_preparation(
        [npm, "ci", "--no-audit", "--no-fund", "--strict-ssl=true", "--engine-strict"],
        cwd=frontend,
        environment=environment,
        stage="Frontend dependency installation",
    )
    _run_preparation([npm, "run", "build", "--silent"], cwd=frontend, environment=environment, stage="Frontend build")
    _run_preparation(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            f"{source}[office]",
            f"certifi>={CERTIFI_MINIMUM}",
        ],
        cwd=source,
        environment=environment,
        stage="Python dependency installation",
    )
    _run_preparation(
        [sys.executable, "-m", "pip", "check"],
        cwd=source,
        environment=environment,
        stage="Python dependency validation",
    )
    _run_preparation(
        [sys.executable, str(source / "shogun/security_maintenance.py"), "check", "--node"],
        cwd=source,
        environment=environment,
        stage="Security prerequisite validation",
    )
    # Backup creation happens after successful preparation and before promotion.
    backup = Path(tempfile.mkdtemp(prefix=f"update-backup-{source_commit[:12]}-", dir=root / ".states"))
    count = promote_application_files(source, root, backup)
    return manifest, count, str(backup.relative_to(root))
