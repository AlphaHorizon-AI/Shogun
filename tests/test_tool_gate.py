import json

import pytest

from shogun.services.tool_gate import (
    GateAction,
    apply_gensui_overrides,
    check_tool_access,
    get_gensui_overrides,
    get_local_overrides,
    set_local_overrides,
)


@pytest.fixture(autouse=True)
def restore_toolgate_overrides(tmp_path, monkeypatch):
    from shogun.services import tool_gate

    original_local = get_local_overrides()
    monkeypatch.setattr(tool_gate, "_LOCAL_OVERRIDES_PATH", tmp_path / "toolgate_overrides.json")
    apply_gensui_overrides({})
    set_local_overrides({})
    yield
    tool_gate._local_overrides = original_local
    apply_gensui_overrides({})


@pytest.mark.asyncio
async def test_campaign_mode_allows_high_risk_email_without_confirmation():
    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
    )

    assert decision.action == GateAction.ALLOW


@pytest.mark.asyncio
async def test_campaign_preset_override_can_still_confirm_email():
    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
        campaign_preset={
            "name": "Confirmed comms",
            "tool_overrides": {"send_email": "confirm"},
        },
    )

    assert decision.action == GateAction.CONFIRM


@pytest.mark.asyncio
async def test_campaign_cannot_relax_gensui_block():
    apply_gensui_overrides({"send_email": "block"})

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
        campaign_preset={
            "name": "Open communications",
            "tool_overrides": {"send_email": "allow"},
        },
    )

    assert decision.action == GateAction.BLOCK
    assert "gensui" in decision.reason


@pytest.mark.asyncio
async def test_local_policy_can_tighten_gensui_allow():
    apply_gensui_overrides({"send_email": "allow"})
    set_local_overrides({"send_email": "confirm"})

    decision = await check_tool_access(
        mode="campaign",
        tool_name="send_email",
        args={"to_address": "person@example.com", "subject": "Hi", "body": "Hello"},
    )

    assert decision.action == GateAction.CONFIRM
    assert "local" in decision.reason


@pytest.mark.asyncio
async def test_parameter_safety_cannot_be_relaxed_by_explicit_allow():
    apply_gensui_overrides({"desktop_type": "allow"})

    decision = await check_tool_access(
        mode="ronin_desktop",
        tool_name="desktop_type",
        args={"text": "api_key=secret"},
    )

    assert decision.action == GateAction.CONFIRM
    assert "credential" in decision.reason.lower()


def test_cached_gensui_policy_is_reapplied_for_offline_startup(tmp_path):
    from shogun.services.gensui_client import GensuiClient

    cache_path = tmp_path / "gensui_membership.json"
    cache_path.write_text(
        json.dumps(
            {
                "shogun_id": "managed-shogun",
                "effective_posture": {"tool_overrides": {"send_email": "block"}},
            }
        ),
        encoding="utf-8",
    )
    client = GensuiClient.__new__(GensuiClient)
    client._cache_path = cache_path
    client._shogun_id = None
    client._effective_posture = None

    client._load_cache()

    assert client._shogun_id == "managed-shogun"
    assert client._effective_posture["tool_overrides"]["send_email"] == "block"
    assert get_gensui_overrides()["send_email"] == "block"
