from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from fastapi import HTTPException

import shogun.api.agent_flow as agent_flow_api
from shogun.schemas.agent_flow import AgentFlowBulkDeleteRequest


@pytest.mark.asyncio
async def test_bulk_delete_deduplicates_and_syncs_each_flow(monkeypatch):
    first_id = uuid.uuid4()
    second_id = uuid.uuid4()
    records = {
        first_id: SimpleNamespace(id=first_id, is_deleted=False),
        second_id: SimpleNamespace(id=second_id, is_deleted=False),
    }
    service = SimpleNamespace(
        get_by_id=AsyncMock(side_effect=lambda flow_id: records.get(flow_id)),
        delete=AsyncMock(return_value=True),
    )
    sync = AsyncMock(return_value={})
    monkeypatch.setattr(agent_flow_api, "_sync_live_flow_schedule", sync)

    response = await agent_flow_api.delete_flows_bulk(
        AgentFlowBulkDeleteRequest(flow_ids=[first_id, second_id, first_id]),
        service,
    )

    assert response.data["deleted_count"] == 2
    assert response.data["deleted_flow_ids"] == [str(first_id), str(second_id)]
    assert service.delete.await_count == 2
    assert sync.await_count == 2


@pytest.mark.asyncio
async def test_bulk_delete_validates_whole_selection_before_mutating(monkeypatch):
    existing_id = uuid.uuid4()
    missing_id = uuid.uuid4()
    existing = SimpleNamespace(id=existing_id, is_deleted=False)
    service = SimpleNamespace(
        get_by_id=AsyncMock(side_effect=lambda flow_id: existing if flow_id == existing_id else None),
        delete=AsyncMock(return_value=True),
    )
    sync = AsyncMock(return_value={})
    monkeypatch.setattr(agent_flow_api, "_sync_live_flow_schedule", sync)

    with pytest.raises(HTTPException) as caught:
        await agent_flow_api.delete_flows_bulk(
            AgentFlowBulkDeleteRequest(flow_ids=[existing_id, missing_id]),
            service,
        )

    assert caught.value.status_code == 404
    assert str(missing_id) in caught.value.detail["missing_flow_ids"]
    service.delete.assert_not_awaited()
    sync.assert_not_awaited()
