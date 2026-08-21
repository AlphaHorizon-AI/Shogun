from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from gensui.api.deps import get_api_key_identity
from gensui.api.identity import sso_status

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_reserved_service_account_key_fails_closed() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_api_key_identity("reserved-key", db=None)  # type: ignore[arg-type]

    assert exc_info.value.status_code == 503
    assert "not available" in str(exc_info.value.detail).casefold()


@pytest.mark.asyncio
async def test_sso_status_cannot_advertise_stored_configuration_as_login() -> None:
    result = await sso_status(db=None)  # type: ignore[arg-type]

    assert result["sso_enabled"] is False
    assert result["authentication_available"] is False
    assert "not implemented" in result["reason"].casefold()


def test_identity_ui_and_manual_mark_authentication_as_unavailable() -> None:
    identity = _text("gensui/frontend/src/pages/Identity.tsx")
    guide = _text("gensui/frontend/src/pages/Guide.tsx")
    readme = _text("README.md")

    for text in (identity, guide):
        assert "authentication" in text.casefold()
        assert "not available" in text.casefold() or "unavailable" in text.casefold()
    assert "No login path currently uses it" in identity
    assert "no Gensui API endpoint accepts those keys" in guide
    assert "Signed OIDC-token verification is not implemented" in guide
    assert "Stored providers remain inactive" in guide
    assert "not accepted for API or SSO authentication" in readme


def test_gensui_locales_preserve_identity_and_posture_boundaries() -> None:
    locale_paths = sorted((ROOT / "gensui" / "frontend" / "src" / "i18n").glob("*.json"))
    assert len(locale_paths) == 14

    for path in locale_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "authentication are not available" in payload["identity"]["subtitle"], path.name
        guide = payload["guide"]
        assert "does not accept service-account keys" in guide["security_enterprise_id_full_desc"], path.name
        assert "not a complete host, network" in guide["security_postures_detail_full_desc"], path.name
        assert "external models, tools, and Nexus remain enabled" in guide["posture_restricted"], path.name
        assert "not an enforcement guarantee" in guide["posture_observe_only"], path.name
        assert "production-ready" not in json.dumps(payload).casefold(), path.name
        assert "permissive (l5)" not in json.dumps(payload).casefold(), path.name
        assert "paranoid (l100)" not in json.dumps(payload).casefold(), path.name


def test_stored_sso_configuration_is_forced_inactive_server_side() -> None:
    service = _text("gensui/services/identity_service.py")
    api = _text("gensui/api/identity.py")

    assert "is_active=False" in service
    assert "is_primary=False" in service
    assert "auto_create_users=False" in service
    assert "provider.is_active = False" in service
    assert "provider.is_primary = False" in service
    assert '"sso_enabled": False' in api
    assert '"authentication_available": False' in api
