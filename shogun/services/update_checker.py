"""
Shogun Update Checker — Compares local version.json against the remote GitHub version.
Runs on a background schedule (every 6 hours by default) and caches the result.
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger("shogun.updates")

# ── Configuration ────────────────────────────────────────────────
REPO = "AlphaHorizon-AI/Shogun"
BRANCH = "main"
REMOTE_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
CHECK_INTERVAL_HOURS = 6

# ── Cached state ─────────────────────────────────────────────────
_cached_result: Optional[dict] = None
_last_check: Optional[datetime] = None


def _get_local_version() -> dict:
    """Read the local version.json from the project root."""
    # Walk up from this file to find the project root
    root = Path(__file__).resolve().parent.parent.parent
    version_file = root / "version.json"

    if not version_file.exists():
        logger.warning("Local version.json not found at %s", version_file)
        return {"version": "0.0.0", "build": 0, "channel": "unknown", "released": "", "changelog": ""}

    try:
        return json.loads(version_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read local version.json: %s", e)
        return {"version": "0.0.0", "build": 0, "channel": "unknown", "released": "", "changelog": ""}


async def _fetch_remote_version() -> Optional[dict]:
    """Fetch the remote version.json from GitHub."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(REMOTE_URL)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("Remote version check returned %d", resp.status_code)
            return None
    except Exception as e:
        logger.debug("Remote version check failed (offline?): %s", e)
        return None


async def check_for_updates(force: bool = False) -> dict:
    """
    Compare local and remote version.json.

    Returns a dict with:
      - update_available: bool
      - local_version: str
      - local_build: int
      - remote_version: str (if available)
      - remote_build: int (if available)
      - changelog: str (if update available)
      - released: str (if update available)
      - last_checked: ISO timestamp
    """
    global _cached_result, _last_check

    # Return cached result if recent and not forced
    if not force and _cached_result and _last_check:
        age_hours = (datetime.now(timezone.utc) - _last_check).total_seconds() / 3600
        if age_hours < CHECK_INTERVAL_HOURS:
            return _cached_result

    local = _get_local_version()
    remote = await _fetch_remote_version()

    now = datetime.now(timezone.utc).isoformat()

    if remote is None:
        result = {
            "update_available": False,
            "local_version": local.get("version", "0.0.0"),
            "local_build": local.get("build", 0),
            "remote_version": None,
            "remote_build": None,
            "changelog": None,
            "released": None,
            "last_checked": now,
            "error": "Could not reach update server. Check your internet connection.",
        }
    else:
        local_build = local.get("build", 0)
        remote_build = remote.get("build", 0)
        update_available = remote_build > local_build

        result = {
            "update_available": update_available,
            "local_version": local.get("version", "0.0.0"),
            "local_build": local_build,
            "remote_version": remote.get("version", "unknown"),
            "remote_build": remote_build,
            "changelog": remote.get("changelog", "") if update_available else None,
            "released": remote.get("released", "") if update_available else None,
            "last_checked": now,
        }

    _cached_result = result
    _last_check = datetime.now(timezone.utc)
    return result


def get_local_version_sync() -> dict:
    """Synchronous helper for startup logging."""
    return _get_local_version()
