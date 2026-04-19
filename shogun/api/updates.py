"""
Shogun Updates API — Check for updates and trigger self-update.
"""

import json
import logging
import subprocess
import sys
import platform
from pathlib import Path

from fastapi import APIRouter, HTTPException

from shogun.services.update_checker import check_for_updates, get_local_version_sync

logger = logging.getLogger("shogun.api.updates")
router = APIRouter(prefix="/updates", tags=["updates"])


@router.get("/check")
async def check_updates(force: bool = False):
    """
    Check if a newer version of Shogun is available on GitHub.

    Query params:
      - force: bypass the cache and check immediately
    """
    result = await check_for_updates(force=force)
    return result


@router.get("/version")
async def get_version():
    """Return the current local version info."""
    return get_local_version_sync()


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
    import httpx
    import zipfile
    import shutil
    import tempfile

    REPO = "AlphaHorizon-AI/Shogun"
    BRANCH = "main"
    ZIP_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"

    # Find project root
    root = Path(__file__).resolve().parent.parent.parent

    try:
        # Step 1: Download
        logger.info("Downloading update from %s", ZIP_URL)
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(ZIP_URL)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Download failed: HTTP {resp.status_code}")

        # Step 2: Save to temp
        tmp_zip = Path(tempfile.mktemp(suffix=".zip"))
        tmp_zip.write_bytes(resp.content)
        logger.info("Downloaded %d bytes to %s", len(resp.content), tmp_zip)

        # Step 3: Extract to temp directory
        tmp_extract = Path(tempfile.mkdtemp(prefix="shogun-update-"))
        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(tmp_extract)

        # Find the extracted folder (Shogun-main/)
        extracted_dirs = list(tmp_extract.iterdir())
        if not extracted_dirs:
            raise HTTPException(status_code=500, detail="ZIP extraction produced no files")
        source = extracted_dirs[0]

        # Step 4: Copy files (skip data/, venv/, node_modules/, .env)
        SKIP = {"data", "venv", "node_modules", ".env", "__pycache__", ".git"}
        updated_files = 0

        for item in source.rglob("*"):
            rel = item.relative_to(source)

            # Skip protected directories
            if any(part in SKIP for part in rel.parts):
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

        # Step 6: Rebuild frontend
        frontend_dir = root / "frontend"
        if (frontend_dir / "package.json").exists():
            logger.info("Rebuilding frontend...")
            try:
                npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"
                subprocess.run(
                    [npm_cmd, "install", "--silent"],
                    cwd=str(frontend_dir),
                    capture_output=True,
                    timeout=120,
                )
                subprocess.run(
                    [npm_cmd, "run", "build", "--silent"],
                    cwd=str(frontend_dir),
                    capture_output=True,
                    timeout=120,
                )
                logger.info("Frontend rebuilt successfully.")
            except Exception as e:
                logger.warning("Frontend rebuild failed: %s — you may need to rebuild manually", e)

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
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Update failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")
