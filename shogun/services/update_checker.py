"""
Shogun Update Checker — Compares local version.json against the remote GitHub version.
Runs on a background schedule (every 6 hours by default) and caches the result.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from shogun.services.release_metadata import get_release_metadata

logger = logging.getLogger("shogun.updates")

# ── Configuration ────────────────────────────────────────────────
REPO = "AlphaHorizon-AI/Shogun"
BRANCH = "main"
REMOTE_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
CHECK_INTERVAL_HOURS = 6

# ── Cached state ─────────────────────────────────────────────────
_cached_result: dict | None = None
_last_check: datetime | None = None
_last_fetch_error: dict | None = None


def _release_notes(value: object) -> list[str]:
    """Bound remote structured notes before they reach the browser."""
    if not isinstance(value, list):
        return []
    notes = [item.strip()[:500] for item in value if isinstance(item, str) and item.strip()]
    return notes[:50]


def _credential_file() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "data" / "update_credentials.json"


def get_update_token() -> str:
    """Return the update token without exposing it through the API."""
    from shogun.config import settings

    if settings.github_token:
        return settings.github_token.strip()
    path = _credential_file()
    if not path.exists():
        return ""
    try:
        from shogun.services.email_service import decrypt_password

        payload = json.loads(path.read_text(encoding="utf-8"))
        return decrypt_password(payload["github_token"]).strip()
    except Exception as exc:
        logger.warning("Could not read update credentials: %s", exc)
        return ""


def save_update_token(token: str) -> None:
    """Persist the update credential encrypted in the protected data directory."""
    from shogun.services.email_service import encrypt_password

    token = token.strip()
    if not token:
        raise ValueError("GitHub access token is required")
    path = _credential_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"github_token": encrypt_password(token)}, indent=2),
        encoding="utf-8",
    )


def update_token_configured() -> bool:
    return bool(get_update_token())


def _get_local_version() -> dict:
    """Read the local version.json from the project root."""
    metadata = get_release_metadata()
    return {
        **metadata,
        # Retain the historic key used by update responses and clients.
        "released": metadata.get("release_date") or "",
    }


async def _fetch_remote_version() -> dict | None:
    """
    Fetch the remote version.json from GitHub.

    Tries three strategies:
    1. GitHub Contents API (works for private repos if GITHUB_TOKEN is set)
    2. Raw githubusercontent (works for public repos)
    3. GitHub API without auth (works for public repos, rate-limited)
    """
    import base64

    global _last_fetch_error
    _last_fetch_error = None
    github_token = get_update_token()
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    headers["User-Agent"] = "Shogun-Updater"

    strategies = []

    # Strategy 1: GitHub Contents API (best for private repos)
    api_url = f"https://api.github.com/repos/{REPO}/contents/version.json?ref={BRANCH}"
    strategies.append(("GitHub API", api_url, True))

    # Strategy 2: Raw file (public repos only)
    raw_url = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/version.json"
    strategies.append(("Raw GitHub", raw_url, False))

    statuses: list[int] = []
    errors: list[str] = []
    for name, url, is_api in strategies:
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                req_headers = dict(headers) if is_api else {}
                resp = await client.get(url, headers=req_headers)
                statuses.append(resp.status_code)

                if resp.status_code == 200:
                    if is_api:
                        # GitHub API returns base64-encoded content
                        data = resp.json()
                        content = base64.b64decode(data["content"]).decode("utf-8")
                        return json.loads(content)
                    else:
                        return resp.json()

                logger.debug("%s returned %d", name, resp.status_code)
        except Exception as e:
            logger.debug("%s failed: %s", name, e)
            errors.append(str(e))

    logger.warning("All update check strategies failed for %s", REPO)
    auth_required = not github_token and any(status in {401, 403, 404} for status in statuses)
    invalid_token = bool(github_token) and any(status in {401, 403, 404} for status in statuses)
    if auth_required:
        message = "The update source requires GitHub access. Add an access token below to enable updates."
    elif invalid_token:
        message = "The saved GitHub access token was rejected. Please replace it."
    elif statuses:
        message = f"Update server returned HTTP {statuses[-1]}."
    else:
        message = "Could not reach the update server. Check the internet connection."
    _last_fetch_error = {
        "message": message,
        "auth_required": auth_required or invalid_token,
        "token_configured": bool(github_token),
        "http_status": statuses[-1] if statuses else None,
        "technical_detail": errors[-1] if errors else None,
    }
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
        fetch_error = _last_fetch_error or {}
        result = {
            "update_available": False,
            "local_version": local.get("version", "0.0.0"),
            "local_build": local.get("build", 0),
            "remote_version": None,
            "remote_build": None,
            "changelog": None,
            "released": None,
            "last_checked": now,
            "error": fetch_error.get("message", "Could not reach the update server."),
            "auth_required": fetch_error.get("auth_required", False),
            "token_configured": fetch_error.get("token_configured", update_token_configured()),
            "http_status": fetch_error.get("http_status"),
            "local_release": local,
            "security_changes": [],
            "breaking_changes": [],
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
            "auth_required": False,
            "token_configured": update_token_configured(),
            "local_release": local,
            "security_changes": _release_notes(remote.get("security_changes")) if update_available else [],
            "breaking_changes": _release_notes(remote.get("breaking_changes")) if update_available else [],
        }

    _cached_result = result
    _last_check = datetime.now(timezone.utc)
    return result


def get_local_version_sync() -> dict:
    """Synchronous helper for startup logging."""
    return _get_local_version()
