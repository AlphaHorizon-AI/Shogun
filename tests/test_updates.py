from pathlib import Path

import pytest
from fastapi import HTTPException

from shogun.api.updates import (
    WhiteLabelUpgradeRequest,
    _frontend_install_failure_detail,
    start_white_label_upgrade,
)


def test_frontend_install_failure_explains_locked_windows_file():
    detail = _frontend_install_failure_detail(
        "npm error code EPERM\nnpm error syscall stat\nnpm error operation not permitted"
    )

    assert "Windows file permissions" in detail
    assert "retry" in detail


def test_frontend_install_failure_explains_network_problem():
    detail = _frontend_install_failure_detail("npm error code ECONNRESET\nnetwork socket disconnected")

    assert "network connection" in detail


def test_frontend_install_failure_keeps_unknown_errors_safe():
    detail = _frontend_install_failure_detail("unexpected package manager failure")

    assert detail == "Frontend dependency installation failed. Check the Shogun server log for npm details."


@pytest.mark.asyncio
async def test_white_label_upgrade_stays_disabled_until_source_is_approved():
    token = "private-token-that-must-not-be-returned"

    with pytest.raises(HTTPException) as exc_info:
        await start_white_label_upgrade(
            WhiteLabelUpgradeRequest(github_token=token),
            "test_primary_admin",
        )

    assert exc_info.value.status_code == 503
    assert "private repository and release file" in str(exc_info.value.detail)
    assert token not in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_white_label_upgrade_rejects_blank_token():
    with pytest.raises(HTTPException) as exc_info:
        await start_white_label_upgrade(
            WhiteLabelUpgradeRequest(github_token="   "),
            "test_primary_admin",
        )

    assert exc_info.value.status_code == 400


def test_updates_page_offers_both_white_label_upgrade_paths():
    source = (
        Path(__file__).resolve().parents[1] / "frontend/src/pages/Updates.tsx"
    ).read_text(encoding="utf-8")

    assert "I need White Label access" in source
    assert "mailto:contact@alphahorizon.io" in source
    assert "I already have an access token" in source
    assert "type=\"password\"" in source
    assert "/api/v1/updates/white-label/upgrade" in source
    assert "setWhiteLabelToken('')" in source
