"""
Shogun Updates API — Check for updates and trigger self-update.
"""

import json
import logging
import platform
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

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


def _with_runtime_version_status(payload: dict) -> dict:
    """Attach whether the running server still needs a restart after update."""
    installed = get_local_version_sync()
    result = dict(payload)
    result["installed_version"] = installed.get("version", "0.0.0")
    result["installed_build"] = installed.get("build", 0)
    result["running_version"] = RUNNING_VERSION.get("version", "0.0.0")
    result["running_build"] = RUNNING_VERSION.get("build", 0)
    result["restart_required"] = installed.get("build", 0) != RUNNING_VERSION.get("build", 0)
    return result


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
    zip_url = (
        f"https://api.github.com/repos/{repo}/zipball/{branch}"
        if token
        else f"https://github.com/{repo}/archive/refs/heads/{branch}.zip"
    )

    # Find project root
    root = Path(__file__).resolve().parent.parent.parent

    try:
        # Step 1: Download
        logger.info("Downloading update from %s", zip_url)
        headers = {"User-Agent": "Shogun-Updater"}
        if token:
            headers.update({
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            })
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(zip_url, headers=headers)
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
        warnings: list[str] = []

        source_frontend_dir = source / "frontend"
        if (source_frontend_dir / "package.json").exists():
            logger.info("Building frontend from update package...")
            try:
                npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                npm_install = subprocess.run(
                    [npm_cmd, "install", "--silent"],
                    cwd=str(source_frontend_dir),
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if npm_install.returncode != 0:
                    logger.error("Frontend npm install failed: %s", npm_install.stderr[-4000:])
                    raise HTTPException(
                        status_code=500,
                        detail="Frontend update build failed during npm install. Shogun was not changed.",
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

        return {
            "success": True,
            "files_updated": updated_files,
            "new_version": new_version.get("version", "unknown"),
            "new_build": new_version.get("build", 0),
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
