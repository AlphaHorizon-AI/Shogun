"""
Shogun Updates API — Check for updates and trigger self-update.
"""

import asyncio
import hashlib
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.security_maintenance import SecurityMaintenanceError, check_python_security, node_environment
from shogun.services.release_metadata import get_release_metadata, write_release_metadata_evidence
from shogun.services.update_checker import (
    check_for_updates,
    get_local_version_sync,
    get_update_token,
    save_update_token,
    update_token_configured,
)
from shogun.services.update_installer import (
    UpdateInstallError,
    extract_update_archive,
    installation_update_lock,
    prepare_and_install_update,
    require_clean_application_checkout,
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
    """Resolve an immutable source; unavailable provenance stops the update."""
    try:
        commit_response = await client.get(
            f"https://api.github.com/repos/{repo}/commits/{branch}",
            headers=headers,
        )
        source_commit = _full_git_sha(commit_response.json().get("sha")) if commit_response.status_code == 200 else None
    except Exception as exc:
        logger.warning("Update commit lookup failed (error_type=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=502, detail="The immutable update source could not be resolved; update stopped."
        ) from exc
    if source_commit is None:
        raise HTTPException(
            status_code=502, detail="The immutable update source could not be verified; update stopped."
        )
    warnings: list[str] = []
    if token:
        archive_url = f"https://api.github.com/repos/{repo}/zipball/{source_commit}"
    else:
        archive_url = f"https://github.com/{repo}/archive/{source_commit}.zip"

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
        warnings.append("The update was applied, but local release provenance could not be recorded.")


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


def _install_downloaded_update(content: bytes, root: Path, environment: dict[str, str], source_commit: str) -> dict:
    """The worker owns its lock/temp files even if the HTTP caller disconnects."""
    try:
        with installation_update_lock(root):
            require_clean_application_checkout(root)
            with tempfile.TemporaryDirectory(prefix="shogun-update-") as temporary:
                archive = Path(temporary) / "source.zip"
                archive.write_bytes(content)
                source = extract_update_archive(archive, Path(temporary) / "source")
                manifest, count, backup_reference = prepare_and_install_update(source, root, environment, source_commit)
            warnings: list[str] = []
            _persist_update_release_evidence(root, manifest, source_commit, warnings)
            return {
                "success": True,
                "files_updated": count,
                "new_version": manifest["version"],
                "new_build": manifest["build"],
                "git_sha": source_commit,
                "archive_sha256": hashlib.sha256(content).hexdigest(),
                "code_backup": backup_reference,
                "changelog": manifest.get("changelog", ""),
                "message": "Update prepared and application files installed. Restart Shogun to activate and verify it.",
                "restart_required": True,
                "verification_pending": True,
                "warnings": warnings,
            }
    except Exception as exc:
        # The HTTP task may already be cancelled; preserve an operational error.
        logger.error("Update installation worker failed (error_type=%s)", type(exc).__name__)
        raise


@router.post("/apply")
async def apply_update(_actor: str = Depends(require_infrastructure_admin)):
    """Prepare one pinned Yellow Label release, then promote only application files."""
    import httpx

    root = Path(__file__).resolve().parent.parent.parent
    try:
        check_python_security()
        environment = node_environment()
    except SecurityMaintenanceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        await asyncio.to_thread(require_clean_application_checkout, root)
        headers = {"User-Agent": "Shogun-Updater"}
        token = get_update_token()
        if token:
            headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response, source_commit, _warnings, _archive_url = await _download_update_archive(
                client,
                repo="AlphaHorizon-AI/Shogun",
                branch="main",
                token=token,
                headers=headers,
            )
        if response.status_code != 200:
            raise HTTPException(
                status_code=502, detail="The pinned update could not be downloaded. Check access and retry."
            )
        if len(response.content) > 200_000_000:
            raise HTTPException(status_code=502, detail="The update archive exceeds the supported size.")
        return await asyncio.to_thread(_install_downloaded_update, response.content, root, environment, source_commit)
    except HTTPException:
        raise
    except UpdateInstallError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Update failed (error_type=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail="Update failed. Application activation was not confirmed; review local recovery status.",
        ) from exc
