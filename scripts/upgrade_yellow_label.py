"""Upgrade an existing full Shogun Yellow Label installation in-place to Bare-Bones AgentFlow.

Preserves 100% of user data:
  - data/shogun.db (AgentFlows, nodes, edges, transformation profiles, providers, routing)
  - data/workspace/ (entire folder structure and files)
  - data/uploads/
  - configs/ (office_config.json, workspace.json, etc.)
  - .env (including VAULT_ENCRYPTION_KEY so encrypted provider API keys keep working)
  - vault/, logs/, venv/, .venv/

Obsolete full-Yellow-Label code files under shogun/, frontend/src/, frontend/dist/,
frontend/public/, and scripts/ are backed up into .states/ and safely pruned.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SOURCE_ROOT))

from shogun.services.release_metadata import write_release_metadata_evidence  # noqa: E402
from shogun.services.update_installer import (  # noqa: E402
    UpdateInstallError,
    installation_update_lock,
    promote_application_files,
    validate_update_source,
)


def _find_target_python(target: Path) -> Path | None:
    for rel in (".venv/Scripts/python.exe", "venv/Scripts/python.exe", ".venv/bin/python", "venv/bin/python"):
        candidate = target / rel
        if candidate.is_file():
            return candidate
    return None


def upgrade_installation(
    target_root: Path,
    *,
    source_root: Path = SOURCE_ROOT,
    install_deps: bool = True,
    allow_dirty_git: bool = False,
) -> dict:
    target = target_root.resolve(strict=True)
    source = source_root.resolve(strict=True)
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise UpdateInstallError("Target installation must be a separate directory from the source release.")
    if not (target / "version.json").is_file() and not (target / "shogun").is_dir():
        raise UpdateInstallError(f"Target does not appear to be a Shogun installation: {target}")
    if (target / ".git").exists() and not allow_dirty_git:
        raise UpdateInstallError(
            "Target is a Git repository checkout. Pass --allow-git only if you explicitly want to overwrite a checkout."
        )

    manifest = validate_update_source(source)

    with installation_update_lock(target):
        backup = Path(tempfile.mkdtemp(prefix="barebones-upgrade-backup-", dir=target / ".states"))
        promoted_count = promote_application_files(source, target, backup)
        write_release_metadata_evidence(target, manifest, None)

        if install_deps:
            py = _find_target_python(target)
            if py is not None:
                result = subprocess.run(
                    [str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-e", str(target)],
                    cwd=target,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    check=False,
                )
                if result.returncode != 0:
                    raise UpdateInstallError(
                        f"Application files promoted, but pip install failed (exit {result.returncode}): "
                        f"{(result.stderr or result.stdout)[-500:]}"
                    )

    return {
        "target": str(target),
        "version": manifest["version"],
        "build": manifest["build"],
        "files_promoted": promoted_count,
        "backup": str(backup.relative_to(target)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="Path to existing Yellow Label installation")
    parser.add_argument("--skip-deps", action="store_true", help="Skip pip install -e . in the target venv")
    parser.add_argument("--allow-git", action="store_true", help="Allow upgrading a target that contains .git")
    args = parser.parse_args()
    try:
        summary = upgrade_installation(
            args.target,
            install_deps=not args.skip_deps,
            allow_dirty_git=args.allow_git,
        )
    except (UpdateInstallError, OSError) as exc:
        print(f"Upgrade failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    print("\nUpgrade complete! Existing workspace folders, files, AgentFlows, and .env were preserved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
