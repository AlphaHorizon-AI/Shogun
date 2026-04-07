"""Agent routes — CRUD for Shogun and Samurai agents."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_agent_service
from shogun.schemas.agents import AgentCreate, AgentResponse, AgentUpdate, SamuraiProfileCreate, SamuraiProfileResponse
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("", response_model=ApiResponse)
async def list_agents(
    agent_type: str | None = None,
    status: str | None = None,
    svc: AgentService = Depends(get_agent_service),
):
    filters = []
    from shogun.db.models.agent import Agent

    filters.append(Agent.is_deleted == False)
    if agent_type:
        filters.append(Agent.agent_type == agent_type)
    if status:
        filters.append(Agent.status == status)

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[AgentResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{agent_id}", response_model=ApiResponse)
async def get_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.get_by_id(agent_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    svc: AgentService = Depends(get_agent_service),
):
    data = body.model_dump()
    data["memory_scope"] = data["memory_scope"] if isinstance(data["memory_scope"], dict) else data["memory_scope"].model_dump()
    record = await svc.create(**data)
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.patch("/{agent_id}", response_model=ApiResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    svc: AgentService = Depends(get_agent_service),
):
    update_data = body.model_dump(exclude_unset=True)
    if "memory_scope" in update_data and update_data["memory_scope"] is not None:
        update_data["memory_scope"] = update_data["memory_scope"].model_dump() if hasattr(update_data["memory_scope"], "model_dump") else update_data["memory_scope"]
    record = await svc.update(agent_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("/{agent_id}/suspend", response_model=ApiResponse)
async def suspend_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.suspend(agent_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.post("/{agent_id}/resume", response_model=ApiResponse)
async def resume_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    record = await svc.resume(agent_id)
    if not record:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data=AgentResponse.model_validate(record))


@router.delete("/{agent_id}", response_model=ApiResponse)
async def delete_agent(
    agent_id: uuid.UUID,
    svc: AgentService = Depends(get_agent_service),
):
    deleted = await svc.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return ApiResponse(data={"deleted": True})


@router.put("/{agent_id}/samurai-profile", response_model=ApiResponse)
async def update_samurai_profile(
    agent_id: uuid.UUID,
    body: SamuraiProfileCreate,
    svc: AgentService = Depends(get_agent_service),
):
    profile = await svc.update_samurai_profile(agent_id, **body.model_dump())
    return ApiResponse(data=SamuraiProfileResponse.model_validate(profile))
