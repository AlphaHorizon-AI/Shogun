"""Tool connector routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_tool_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.tools import ToolConnectorCreate, ToolConnectorResponse, ToolConnectorUpdate
from shogun.services.tool_service import ToolService

router = APIRouter(prefix="/tools", tags=["Tools"])


@router.get("", response_model=ApiResponse)
async def list_tools(svc: ToolService = Depends(get_tool_service)):
    from shogun.db.models.tool_connector import ToolConnector
    records, total = await svc.get_all(filters=[ToolConnector.is_deleted == False])
    return ApiResponse(
        data=[ToolConnectorResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{tool_id}", response_model=ApiResponse)
async def get_tool(tool_id: uuid.UUID, svc: ToolService = Depends(get_tool_service)):
    record = await svc.get_by_id(tool_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ApiResponse(data=ToolConnectorResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_tool(body: ToolConnectorCreate, svc: ToolService = Depends(get_tool_service)):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=ToolConnectorResponse.model_validate(record))


@router.patch("/{tool_id}", response_model=ApiResponse)
async def update_tool(
    tool_id: uuid.UUID,
    body: ToolConnectorUpdate,
    svc: ToolService = Depends(get_tool_service),
):
    record = await svc.update(tool_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ApiResponse(data=ToolConnectorResponse.model_validate(record))


@router.post("/{tool_id}/test", response_model=ApiResponse)
async def test_tool(tool_id: uuid.UUID):
    return ApiResponse(data={"status": "test_not_implemented", "tool_id": str(tool_id)})


@router.post("/{tool_id}/disable", response_model=ApiResponse)
async def disable_tool(tool_id: uuid.UUID, svc: ToolService = Depends(get_tool_service)):
    record = await svc.update(tool_id, status="disabled")
    if not record:
        raise HTTPException(status_code=404, detail="Tool not found")
    return ApiResponse(data=ToolConnectorResponse.model_validate(record))
