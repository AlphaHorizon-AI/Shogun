import asyncio

import pytest

from shogun.services.toolgate_confirm import (
    get_pending_count,
    register_confirmation,
    resolve_confirmation,
    wait_for_confirmation,
)


@pytest.mark.asyncio
async def test_confirmation_is_registered_before_stream_wait_begins() -> None:
    confirm_id = "immediate-ui-approval"
    register_confirmation(
        confirm_id=confirm_id,
        tool_name="patch_agent_flow",
        args={"flow_id": "flow-1"},
        risk_level="medium",
        reason="One-time workflow edit approval",
    )

    assert get_pending_count() == 1
    assert resolve_confirmation(confirm_id, True) is True
    assert await asyncio.wait_for(wait_for_confirmation(confirm_id), timeout=0.5) is True
    assert get_pending_count() == 0
