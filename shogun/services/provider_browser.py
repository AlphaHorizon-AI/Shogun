"""Open approved provider authorization and credential pages in the OS browser."""

from __future__ import annotations

import os
import webbrowser
from urllib.parse import urlsplit


class ProviderBrowserError(RuntimeError):
    """A provider page cannot be opened safely."""


_PROVIDER_SETUP_URLS: dict[tuple[str, str], str] = {
    ("openai", "api_key"): "https://platform.openai.com/api-keys",
    ("google", "api_key"): "https://aistudio.google.com/app/apikey",
    ("google", "oauth"): "https://console.cloud.google.com/apis/credentials",
    ("anthropic", "api_key"): "https://platform.claude.com/settings/keys",
}


def provider_setup_url(provider_type: str, auth_type: str) -> str:
    """Return the official setup page for a supported provider/auth pair."""

    try:
        return _PROVIDER_SETUP_URLS[(provider_type.casefold(), auth_type.casefold())]
    except KeyError as exc:
        raise ProviderBrowserError(
            f"No browser-assisted {auth_type} setup is registered for {provider_type}"
        ) from exc


def open_default_browser(url: str) -> bool:
    """Open a trusted HTTPS URL in the desktop's default browser.

    The caller owns URL authorization. This final guard prevents credentials,
    local files, or executable schemes from reaching the OS URL handler.
    """

    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ProviderBrowserError("Only public HTTPS provider pages can be opened")
    if os.environ.get("SHOGUN_NO_BROWSER", "").casefold() in {"1", "true", "yes", "on"}:
        return False
    try:
        if webbrowser.open(url, new=2, autoraise=True):
            return True
    except Exception:
        pass
    if hasattr(os, "startfile"):
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return True
        except OSError:
            pass
    return False
