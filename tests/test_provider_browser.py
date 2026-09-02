from __future__ import annotations

import pytest

from shogun.services.provider_browser import (
    ProviderBrowserError,
    open_default_browser,
    provider_setup_url,
)


@pytest.mark.parametrize(
    ("provider_type", "auth_type", "expected_host"),
    [
        ("openai", "api_key", "platform.openai.com"),
        ("google", "api_key", "aistudio.google.com"),
        ("google", "oauth", "console.cloud.google.com"),
        ("anthropic", "api_key", "platform.claude.com"),
    ],
)
def test_provider_setup_urls_are_explicitly_registered(
    provider_type: str, auth_type: str, expected_host: str
) -> None:
    assert expected_host in provider_setup_url(provider_type, auth_type)


def test_provider_setup_rejects_unregistered_auth_pair() -> None:
    with pytest.raises(ProviderBrowserError, match="No browser-assisted"):
        provider_setup_url("openai", "oauth")


def test_default_browser_opens_https_page(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[str] = []
    monkeypatch.delenv("SHOGUN_NO_BROWSER", raising=False)
    monkeypatch.setattr(
        "shogun.services.provider_browser.webbrowser.open",
        lambda url, **_kwargs: opened.append(url) or True,
    )

    assert open_default_browser("https://platform.openai.com/api-keys") is True
    assert opened == ["https://platform.openai.com/api-keys"]


def test_default_browser_rejects_non_https_url() -> None:
    with pytest.raises(ProviderBrowserError, match="Only public HTTPS"):
        open_default_browser("file:///C:/secrets.txt")
