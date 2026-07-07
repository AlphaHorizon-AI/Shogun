import pytest

from shogun.services.tool_gate import GateAction, check_tool_access


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
