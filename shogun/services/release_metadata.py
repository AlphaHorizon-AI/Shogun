"""Canonical, non-sensitive product and release identity for Shogun.

The version manifest remains the release authority. A source commit may be
provided by the manifest, an official build environment, a generated release
evidence file, or (for developer checkouts) Git. Instance identifiers and
other deployment-specific values deliberately do not belong here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

PRODUCT = "Shogun AFM"
DEVELOPER = "Alpha Horizon"
OFFICIAL_REPOSITORY = "AlphaHorizon-AI/Shogun"
OFFICIAL_REPOSITORY_URL = f"https://github.com/{OFFICIAL_REPOSITORY}"
_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,64}$")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_sha(value: object) -> str | None:
    candidate = str(value or "").strip()
    return candidate.lower() if _SHA_PATTERN.fullmatch(candidate) else None


def _git_sha(root: Path) -> str | None:
    """Return checkout HEAD as a base-source identifier, if available."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return _clean_sha(completed.stdout)


def _git_tracked_modifications(root: Path) -> bool | None:
    """Report tracked checkout changes; untracked instance data is out of scope.

    ``None`` means the installed distribution is not a readable Git checkout,
    so local modification status cannot be established from Git.
    """
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if status.returncode != 0:
        return None
    return bool(status.stdout.strip())


def _safe_note_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def write_release_metadata_evidence(
    root: Path,
    manifest: dict[str, Any],
    git_sha: str | None,
) -> Path:
    """Persist non-sensitive provenance for an in-place official update."""
    source_commit = _clean_sha(git_sha)
    if git_sha and (source_commit is None or len(source_commit) != 40):
        raise ValueError("Release evidence requires a full 40-character Git SHA")
    try:
        build = int(manifest.get("build", 0))
    except (TypeError, ValueError):
        build = 0
    payload = {
        "schema_version": 1,
        "product": str(manifest.get("name") or PRODUCT),
        "version": str(manifest.get("version") or "unknown"),
        "build": build,
        "release_date": manifest.get("released"),
        "git_sha": source_commit,
        "official_repository": OFFICIAL_REPOSITORY,
        # Prevent a copied-over Git checkout or immutable container environment
        # from being mistaken for the source of files installed by the updater.
        "source_overlay": True,
    }
    path = root.resolve() / "configs" / "release_metadata.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def get_release_metadata(root: Path | None = None) -> dict[str, Any]:
    """Return the installed official-release identity without instance metadata.

    ``release-metadata.json`` is an optional build artifact. Its values fill
    gaps in ``version.json`` but never replace version/build values declared by
    the installed manifest.
    """
    project_root = (root or _project_root()).resolve()
    manifest = _read_json_object(project_root / "version.json")
    build_evidence = _read_json_object(project_root / "configs" / "release_metadata.json")
    if not build_evidence:
        build_evidence = _read_json_object(project_root / "release-metadata.json")

    evidence_matches_manifest = (
        str(build_evidence.get("version") or "") == str(manifest.get("version") or "")
        and str(build_evidence.get("build") or "") == str(manifest.get("build") or "")
    )
    updater_overlay = evidence_matches_manifest and build_evidence.get("source_overlay") is True

    sha_candidates = (
        ("manifest", manifest.get("git_sha")),
        ("manifest", manifest.get("source_commit")),
        ("release_evidence", build_evidence.get("git_sha") if evidence_matches_manifest else None),
        ("build_environment", os.getenv("SHOGUN_GIT_SHA") if not updater_overlay else None),
        ("build_environment", os.getenv("GITHUB_SHA") if not updater_overlay else None),
    )
    git_sha = None
    git_sha_source = None
    for source, value in sha_candidates:
        if cleaned := _clean_sha(value):
            git_sha = cleaned
            git_sha_source = source
            break
    if git_sha is None and not updater_overlay:
        git_sha = _git_sha(project_root)
        if git_sha is not None:
            git_sha_source = "git_checkout"

    # An updater overlay is intentionally compared with a different checkout
    # HEAD, so Git dirtiness is not meaningful evidence about the overlay.
    working_tree_modified = None if updater_overlay else _git_tracked_modifications(project_root)
    if updater_overlay:
        distribution_status = "update_overlay_unverified"
    elif working_tree_modified is True:
        distribution_status = "locally_modified"
    elif working_tree_modified is False:
        distribution_status = "tracked_checkout_clean"
    elif evidence_matches_manifest:
        distribution_status = "release_evidence_present"
    else:
        distribution_status = "unverified"

    build = manifest.get("build", 0)
    try:
        build = int(build)
    except (TypeError, ValueError):
        build = 0

    product = str(manifest.get("name") or PRODUCT).strip() or PRODUCT
    version = str(manifest.get("version") or "0.0.0").strip() or "0.0.0"
    release_date = str(
        manifest.get("released")
        or (build_evidence.get("release_date") if evidence_matches_manifest else "")
        or ""
    ).strip()
    channel = str(manifest.get("channel") or "unknown").strip() or "unknown"

    return {
        "product": product,
        "version": version,
        "build": build,
        "release_id": f"{version}+build.{build}",
        "channel": channel,
        "release_date": release_date or None,
        "git_sha": git_sha,
        "git_sha_source": git_sha_source,
        "working_tree_modified": working_tree_modified,
        "distribution_status": distribution_status,
        "developer": DEVELOPER,
        "official_repository": OFFICIAL_REPOSITORY,
        "official_repository_url": OFFICIAL_REPOSITORY_URL,
        "changelog": str(manifest.get("changelog") or "").strip(),
        "security_changes": _safe_note_list(manifest.get("security_changes")),
        "breaking_changes": _safe_note_list(manifest.get("breaking_changes")),
    }
