"""Agent routes — CRUD for Shogun and Samurai agents."""

from __future__ import annotations

import uuid
import shutil
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File

from shogun.api.deps import get_agent_service
from shogun.schemas.agents import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    SamuraiProfileCreate,
    SamuraiProfileResponse,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/shogun", response_model=ApiResponse)
async def get_primary_shogun(svc: AgentService = Depends(get_agent_service)):
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await svc.get_all(filters=filters)
    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun not found")
    return ApiResponse(data=AgentResponse.model_validate(records[0]))


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


@router.post("/{agent_id}/avatar", response_model=ApiResponse)
async def upload_agent_avatar(
    agent_id: uuid.UUID,
    file: UploadFile = File(...),
    svc: AgentService = Depends(get_agent_service),
):
    """Upload a profile picture for an agent."""
    from shogun.config import settings
    
    # Verify agent exists
    agent = await svc.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Determine file extension and create unique filename
    ext = Path(file.filename).suffix or ".png"
    filename = f"avatar_{agent_id.hex}_{int(datetime.now().timestamp())}{ext}"
    
    # Ensure directory exists (redundant since settings.ensure_directories() is called on startup)
    upload_dir = Path(settings.uploads_path)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = upload_dir / filename
    
    try:
        with open(dest_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Update agent record with the new avatar URL
        avatar_url = f"/uploads/{filename}"
        await svc.update(agent_id, avatar_url=avatar_url)
        
        return ApiResponse(data={"avatar_url": avatar_url})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")


@router.put("/{agent_id}/samurai-profile", response_model=ApiResponse)
async def update_samurai_profile(
    agent_id: uuid.UUID,
    body: SamuraiProfileCreate,
    svc: AgentService = Depends(get_agent_service),
):
    profile = await svc.update_samurai_profile(agent_id, **body.model_dump())
    return ApiResponse(data=SamuraiProfileResponse.model_validate(profile))


@router.post("/shogun/chat", response_model=ApiResponse)
async def shogun_chat(
    body: dict,
    svc: AgentService = Depends(get_agent_service),
):
    """Bridge for the React frontend to communicate with the primary Shogun."""
    user_msg = body.get("message", "")
    # Placeholder for real LLM dispatch logic
    # In a later iteration, this would call the agent's act() method
    response = f"Shogun acknowledges: '{user_msg}'. Terminal bridge established."
    
    return ApiResponse(
        success=True,
        data={
            "response": response,
            "role": "shogun",
            "timestamp": datetime.now().strftime("%H:%M")
        }
    )
