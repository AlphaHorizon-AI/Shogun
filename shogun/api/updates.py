"""
Shogun Updates API — Check for updates and trigger self-update.
"""

import json
import logging
import platform
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.services.release_metadata import get_release_metadata, write_release_metadata_evidence
from shogun.services.update_checker import (
    check_for_updates,
    get_local_version_sync,
    get_update_token,
    save_update_token,
    update_token_configured,
)

logger = logging.getLogger("shogun.api.updates")
router = APIRouter(prefix="/updates", tags=["updates"])
RUNNING_VERSION = get_local_version_sync()


class WhiteLabelUpgradeRequest(BaseModel):
    """One-use credential for the future private White Label release source."""

    github_token: SecretStr = Field(min_length=1, max_length=2048)


def _frontend_install_failure_detail(output: str) -> str:
    """Turn npm's noisy output into an actionable, safe updater message."""
    normalized = output.lower()
    if "eperm" in normalized or "eacces" in normalized or "permission denied" in normalized:
        return (
            "Frontend dependency installation was blocked by Windows file permissions "
            "or a locked file. Close other Node/npm processes and retry."
        )
    if "enospc" in normalized or "no space left" in normalized:
        return "Frontend dependency installation ran out of disk space. Free space and retry."
    if any(marker in normalized for marker in ("econnreset", "etimedout", "enotfound", "network")):
        return "Frontend dependencies could not be downloaded. Check the network connection and retry."
    if "eresolve" in normalized:
        return "Frontend dependencies contain an incompatible version constraint in the update package."
    return "Frontend dependency installation failed. Check the Shogun server log for npm details."


def _with_runtime_version_status(payload: dict) -> dict:
    """Attach whether the running server still needs a restart after update."""
    installed = get_local_version_sync()
    result = dict(payload)
    result["installed_version"] = installed.get("version", "0.0.0")
    result["installed_build"] = installed.get("build", 0)
    result["running_version"] = RUNNING_VERSION.get("version", "0.0.0")
    result["running_build"] = RUNNING_VERSION.get("build", 0)
    result["restart_required"] = installed.get("build", 0) != RUNNING_VERSION.get("build", 0)
    result["release"] = get_release_metadata()
    return result


def _full_git_sha(value: object) -> str | None:
    candidate = str(value or "").strip().lower()
    if len(candidate) == 40 and all(character in "0123456789abcdef" for character in candidate):
        return candidate
    return None


async def _download_update_archive(
    client,
    *,
    repo: str,
    branch: str,
    token: str,
    headers: dict[str, str],
):
    """Resolve main once and download that immutable source when possible."""
    warnings: list[str] = []
    source_commit: str | None = None
    try:
        commit_response = await client.get(
            f"https://api.github.com/repos/{repo}/commits/{branch}",
            headers=headers,
        )
        if commit_response.status_code == 200:
            source_commit = _full_git_sha(commit_response.json().get("sha"))
        if source_commit is None:
            warnings.append(
                "The update source commit could not be verified; no Git SHA will be claimed."
            )
    except Exception as exc:
        logger.warning("Update commit lookup failed (error_type=%s)", type(exc).__name__)
        warnings.append(
            "The update source commit could not be verified; no Git SHA will be claimed."
        )

    archive_ref = source_commit or branch
    if token:
        archive_url = f"https://api.github.com/repos/{repo}/zipball/{archive_ref}"
    elif source_commit:
        archive_url = f"https://github.com/{repo}/archive/{source_commit}.zip"
    else:
        archive_url = f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"

    logger.info("Downloading update from %s", archive_url)
    response = await client.get(archive_url, headers=headers)
    return response, source_commit, warnings, archive_url


def _persist_update_release_evidence(
    root: Path,
    manifest: dict,
    source_commit: str | None,
    warnings: list[str],
) -> None:
    """Record provenance without making an already-applied update fail."""
    try:
        write_release_metadata_evidence(root, manifest, source_commit)
    except Exception as exc:
        logger.warning("Update release evidence could not be written (error_type=%s)", type(exc).__name__)
        warnings.append(
            "The update was applied, but local release provenance could not be recorded."
        )


@router.get("/check")
async def check_updates(force: bool = False):
    """
    Check if a newer version of Shogun is available on GitHub.

    Query params:
      - force: bypass the cache and check immediately
    """
    result = await check_for_updates(force=force)
    return _with_runtime_version_status(result)


@router.get("/version")
async def get_version():
    """Return the current local version info."""
    return _with_runtime_version_status(get_local_version_sync())


@router.get("/credentials")
async def update_credentials_status():
    """Report whether private update access is configured, never the secret itself."""
    return {"token_configured": update_token_configured()}


@router.post("/credentials")
async def configure_update_credentials(body: dict):
    """Save and validate a GitHub token used only for update downloads."""
    token = str(body.get("github_token", "")).strip()
    if not token:
        raise HTTPException(status_code=400, detail="GitHub access token is required")
    save_update_token(token)
    result = await check_for_updates(force=True)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "token_configured": True, "status": result}


@router.post("/white-label/upgrade")
async def start_white_label_upgrade(
    body: WhiteLabelUpgradeRequest,
    _actor: str = Depends(require_infrastructure_admin),
):
    """Accept a one-use token only after the approved White Label source is configured."""
    if not body.github_token.get_secret_value().strip():
        raise HTTPException(status_code=400, detail="White Label access token is required.")

    # The private repository and approved release filename are intentionally not
    # guessed. Until both are supplied, do not retain or attempt to use the token.
    raise HTTPException(
        status_code=503,
        detail=(
            "White Label upgrade is not configured yet. The approved private "
            "repository and release file must be added before this action can start."
        ),
    )


@router.post("/restart", status_code=202)
async def restart_shogun(_actor: str = Depends(require_infrastructure_admin)):
    """Gracefully stop Shogun and ask its launcher/supervisor to restart it."""
    from shogun.services.restart_service import request_restart

    try:
        return request_restart()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/shutdown", status_code=202)
async def shutdown_shogun(_actor: str = Depends(require_infrastructure_admin)):
    """Gracefully stop Tenshu and its launcher-owned desktop resources."""
    from shogun.services.restart_service import request_shutdown

    try:
        return request_shutdown()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/apply")
async def apply_update():
    """
    Download and apply the latest version from GitHub.

    This will:
    1. Download the latest ZIP from GitHub
    2. Extract it over the current installation (preserving data/)
    3. Rebuild the frontend
    4. Return a message asking the user to restart
    """
    import shutil
    import tempfile
    import zipfile

    import httpx

    repo = "AlphaHorizon-AI/Shogun"
    branch = "main"
    token = get_update_token()

    # Find project root
    root = Path(__file__).resolve().parent.parent.parent
    source_commit: str | None = None
    warnings: list[str] = []

    try:
        # Step 1: Download
        headers = {"User-Agent": "Shogun-Updater"}
        if token:
            headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            })
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp, source_commit, source_warnings, _archive_url = await _download_update_archive(
                client,
                repo=repo,
                branch=branch,
                token=token,
                headers=headers,
            )
            warnings.extend(source_warnings)
            if resp.status_code != 200:
                if resp.status_code in {401, 403, 404}:
                    raise HTTPException(
                        status_code=502,
                        detail="GitHub denied access to the update. Check the access token in Updates.",
                    )
                raise HTTPException(status_code=502, detail=f"Download failed: HTTP {resp.status_code}")

        # Step 2: Save to temp
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temporary:
            tmp_zip = Path(temporary.name)
        tmp_zip.write_bytes(resp.content)
        logger.info("Downloaded %d bytes to %s", len(resp.content), tmp_zip)

        # Step 3: Extract to temp directory
        tmp_extract = Path(tempfile.mkdtemp(prefix="shogun-update-"))
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            extract_root = tmp_extract.resolve()
            for member in zf.infolist():
                destination = (tmp_extract / member.filename).resolve()
                if destination != extract_root and extract_root not in destination.parents:
                    raise HTTPException(status_code=400, detail="Unsafe path found in update package")
            zf.extractall(tmp_extract)

        # Find the extracted folder (Shogun-main/)
        extracted_dirs = list(tmp_extract.iterdir())
        if not extracted_dirs or not extracted_dirs[0].is_dir():
            raise HTTPException(status_code=500, detail="ZIP extraction produced no files")
        source = extracted_dirs[0]

        source_frontend_dir = source / "frontend"
        if (source_frontend_dir / "package.json").exists():
            logger.info("Building frontend from update package...")
            try:
                npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                npm_cache = tmp_extract / ".npm-cache"
                install_command = "ci" if (source_frontend_dir / "package-lock.json").exists() else "install"
                npm_install = subprocess.run(
                    [
                        npm_cmd,
                        install_command,
                        "--no-audit",
                        "--no-fund",
                        "--cache",
                        str(npm_cache),
                    ],
                    cwd=str(source_frontend_dir),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if npm_install.returncode != 0:
                    npm_output = "\n".join(
                        part for part in (npm_install.stdout, npm_install.stderr) if part
                    )
                    logger.error("Frontend npm %s failed: %s", install_command, npm_output[-4000:])
                    raise HTTPException(
                        status_code=500,
                        detail=f"{_frontend_install_failure_detail(npm_output)} Shogun was not changed.",
                    )

                npm_build = subprocess.run(
                    [npm_cmd, "run", "build", "--silent"],
                    cwd=str(source_frontend_dir),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if npm_build.returncode != 0:
                    logger.error("Frontend npm build failed: %s", npm_build.stderr[-4000:])
                    raise HTTPException(
                        status_code=500,
                        detail="Frontend update build failed. Shogun was not changed.",
                    )
                logger.info("Frontend package built successfully.")
            except HTTPException:
                raise
            except Exception as e:
                logger.error("Frontend update build failed before copy: %s", e, exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Frontend update build failed before files were changed.",
                )

        # Step 4: Copy files (skip top-level data/, venv/, node_modules/, .env)
        # Only skip these at the top level — nested dirs like shogun/data/ must be copied.
        skip_toplevel = {
            "data", "venv", ".venv", "node_modules", ".env", "__pycache__", ".git",
            "configs", "vault", "logs", "scratch", ".states",
        }
        updated_files = 0

        for item in source.rglob("*"):
            rel = item.relative_to(source)

            # Skip protected top-level directories only
            if rel.parts[0] in skip_toplevel:
                continue
            if "node_modules" in rel.parts or "__pycache__" in rel.parts:
                continue

            dest = root / rel
            if item.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                updated_files += 1

        # Step 5: Cleanup
        tmp_zip.unlink(missing_ok=True)
        shutil.rmtree(tmp_extract, ignore_errors=True)

        logger.info("Update applied: %d files updated", updated_files)

        # Step 6: Refresh Python dependencies
        dependency_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", ".[office]", "--disable-pip-version-check"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if dependency_result.returncode != 0:
            warnings.append("Python dependency refresh failed; see server logs.")
            logger.warning("Dependency refresh failed: %s", dependency_result.stderr[-2000:])

        # Read the new version
        new_version = json.loads((root / "version.json").read_text(encoding="utf-8"))
        _persist_update_release_evidence(root, new_version, source_commit, warnings)

        return {
            "success": True,
            "files_updated": updated_files,
            "new_version": new_version.get("version", "unknown"),
            "new_build": new_version.get("build", 0),
            "git_sha": source_commit,
            "changelog": new_version.get("changelog", ""),
            "message": "Update applied successfully. Please restart Shogun to complete the update.",
            "restart_required": True,
            "warnings": warnings,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
