from __future__ import annotations

import pytest
from fastapi import HTTPException

from shogun.api import ronin, setup
from shogun.config import Settings


def test_server_deployment_mode_is_configurable() -> None:
    configured = Settings(_env_file=None, deployment_mode="server")

    assert configured.deployment_mode == "server"


@pytest.mark.asyncio
async def test_setup_status_reports_server_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup.settings, "deployment_mode", "server")

    response = await setup.get_setup_status()

    assert response.data["deployment_mode"] == "server"
    assert response.data["ronin_available"] is False


@pytest.mark.asyncio
async def test_server_mode_reports_ronin_as_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup.settings, "deployment_mode", "server")

    response = await setup.check_ronin_deps()

    assert response.data["recommendation"] == "unavailable"
    assert response.data["ronin_enabled_in_setup"] is False


@pytest.mark.asyncio
async def test_server_mode_blocks_desktop_activation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ronin.settings, "deployment_mode", "server")

    with pytest.raises(HTTPException) as exc_info:
        await ronin.enable_desktop_control({"confirmation": "ENABLE RONIN DESKTOP CONTROL"})

    assert exc_info.value.status_code == 409
