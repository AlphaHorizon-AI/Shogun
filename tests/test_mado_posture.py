import pytest
from fastapi import HTTPException

from shogun.services.posture_guard import check_mado_browser_mode


def test_headless_only_posture_rejects_visible_mado_session():
    with pytest.raises(HTTPException) as exc_info:
        check_mado_browser_mode(
            "visible",
            {"active_tier": "tactical", "mado_headless_only": True},
        )

    assert exc_info.value.status_code == 403
    assert "headless" in exc_info.value.detail


def test_posture_allows_headless_session():
    check_mado_browser_mode(
        "headless",
        {"active_tier": "tactical", "mado_headless_only": True},
    )


def test_campaign_style_posture_can_allow_visible_session():
    check_mado_browser_mode(
        "visible",
        {"active_tier": "campaign", "mado_headless_only": False},
    )
