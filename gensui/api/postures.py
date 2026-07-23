"""Postures API — security posture definition management."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, get_current_admin, require_role
from gensui.services.posture_service import PostureService

router = APIRouter(prefix="/postures", tags=["postures"])


class AdvancedToolGateRule(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=120)
    pattern: str = Field(min_length=1, max_length=200)
    match_type: Literal["contains", "word"] = "contains"
    action: Literal["confirm", "block"] = "confirm"
    tools: list[str] = Field(default_factory=list, max_length=50)
    case_sensitive: bool = False
    enabled: bool = True


class AdvancedToolGateControls(BaseModel):
    enabled: bool = False
    rules: list[AdvancedToolGateRule] = Field(default_factory=list, max_length=100)


class CreatePostureRequest(BaseModel):
    name: str
    description: str | None = None
    level: int = 10
    allow_external_models: bool = True
    allow_local_models: bool = True
    allow_tool_execution: bool = True
    allow_mado: bool = True
    allow_memory_write: bool = True
    allow_memory_read: bool = True
    allow_agent_flow: bool = True
    allow_nexus: bool = True
    allow_samurai_delegation: bool = True
    allow_scheduled_triggers: bool = True
    allow_autonomous_loops: bool = True
    allow_external_web: bool = True
    allow_file_write: bool = True
    allow_external_api: bool = True
    rules_json: dict | None = None
    advanced_toolgate_json: AdvancedToolGateControls | None = None


@router.get("")
async def list_postures(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """List all security postures."""
    svc = PostureService(db)
    postures = await svc.list_postures()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "level": p.level,
            "is_builtin": p.is_builtin,
            "allow_external_models": p.allow_external_models,
            "allow_local_models": p.allow_local_models,
            "allow_tool_execution": p.allow_tool_execution,
            "allow_mado": p.allow_mado,
            "allow_memory_write": p.allow_memory_write,
            "allow_memory_read": p.allow_memory_read,
            "allow_agent_flow": p.allow_agent_flow,
            "allow_nexus": p.allow_nexus,
            "allow_samurai_delegation": p.allow_samurai_delegation,
            "allow_scheduled_triggers": p.allow_scheduled_triggers,
            "allow_autonomous_loops": p.allow_autonomous_loops,
            "allow_external_web": p.allow_external_web,
            "allow_file_write": p.allow_file_write,
            "allow_external_api": p.allow_external_api,
            "tool_overrides_json": p.tool_overrides_json,
            "advanced_toolgate_json": p.advanced_toolgate_json or {"enabled": False, "rules": []},
        }
        for p in postures
    ]


@router.post("")
async def create_posture(
    req: CreatePostureRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Create a new custom security posture."""
    svc = PostureService(db)
    posture = await svc.create(
        name=req.name,
        description=req.description,
        level=req.level,
        is_builtin=False,
        created_by=admin["id"],
        allow_external_models=req.allow_external_models,
        allow_local_models=req.allow_local_models,
        allow_tool_execution=req.allow_tool_execution,
        allow_mado=req.allow_mado,
        allow_memory_write=req.allow_memory_write,
        allow_memory_read=req.allow_memory_read,
        allow_agent_flow=req.allow_agent_flow,
        allow_nexus=req.allow_nexus,
        allow_samurai_delegation=req.allow_samurai_delegation,
        allow_scheduled_triggers=req.allow_scheduled_triggers,
        allow_autonomous_loops=req.allow_autonomous_loops,
        allow_external_web=req.allow_external_web,
        allow_file_write=req.allow_file_write,
        allow_external_api=req.allow_external_api,
        rules_json=req.rules_json,
        advanced_toolgate_json=(
            req.advanced_toolgate_json.model_dump()
            if req.advanced_toolgate_json
            else {"enabled": False, "rules": []}
        ),
    )
    return {"id": str(posture.id), "name": posture.name}


class UpdatePostureRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    level: int | None = None
    allow_external_models: bool | None = None
    allow_local_models: bool | None = None
    allow_tool_execution: bool | None = None
    allow_mado: bool | None = None
    allow_memory_write: bool | None = None
    allow_memory_read: bool | None = None
    allow_agent_flow: bool | None = None
    allow_nexus: bool | None = None
    allow_samurai_delegation: bool | None = None
    allow_scheduled_triggers: bool | None = None
    allow_autonomous_loops: bool | None = None
    allow_external_web: bool | None = None
    allow_file_write: bool | None = None
    allow_external_api: bool | None = None
    tool_overrides_json: dict | None = None
    advanced_toolgate_json: AdvancedToolGateControls | None = None
    rules_json: dict | None = None


@router.patch("/{posture_id}")
async def update_posture(
    posture_id: uuid.UUID,
    req: UpdatePostureRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Update a security posture. Built-in postures cannot be renamed."""
    svc = PostureService(db)
    posture = await svc.get_by_id(posture_id)
    if posture is None:
        raise HTTPException(status_code=404, detail="Posture not found")

    # Built-in postures cannot be renamed
    if posture.is_builtin and req.name is not None and req.name != posture.name:
        raise HTTPException(status_code=403, detail="Cannot rename built-in postures")

    # Build update dict (only non-None fields)
    update_fields = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = await svc.update(posture_id, **update_fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="Update failed")

    return {
        "id": str(updated.id),
        "name": updated.name,
        "description": updated.description,
        "level": updated.level,
        "is_builtin": updated.is_builtin,
        "allow_external_models": updated.allow_external_models,
        "allow_local_models": updated.allow_local_models,
        "allow_tool_execution": updated.allow_tool_execution,
        "allow_mado": updated.allow_mado,
        "allow_memory_write": updated.allow_memory_write,
        "allow_memory_read": updated.allow_memory_read,
        "allow_agent_flow": updated.allow_agent_flow,
        "allow_nexus": updated.allow_nexus,
        "allow_samurai_delegation": updated.allow_samurai_delegation,
        "allow_scheduled_triggers": updated.allow_scheduled_triggers,
        "allow_autonomous_loops": updated.allow_autonomous_loops,
        "allow_external_web": updated.allow_external_web,
        "allow_file_write": updated.allow_file_write,
        "allow_external_api": updated.allow_external_api,
        "tool_overrides_json": updated.tool_overrides_json,
        "advanced_toolgate_json": (
            updated.advanced_toolgate_json or {"enabled": False, "rules": []}
        ),
    }


@router.delete("/{posture_id}")
async def delete_posture(
    posture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Delete a custom posture. Built-in postures cannot be deleted."""
    svc = PostureService(db)
    posture = await svc.get_by_id(posture_id)
    if posture is None:
        raise HTTPException(status_code=404, detail="Posture not found")
    if posture.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in postures")

    # Unassign from any members referencing this posture
    from sqlalchemy import update as sql_update
    from gensui.db.models.shogun_member import ShogunMember
    from gensui.db.models.member_group import MemberGroup

    await db.execute(
        sql_update(ShogunMember)
        .where(ShogunMember.individual_posture_id == posture_id)
        .values(individual_posture_id=None)
    )
    await db.execute(
        sql_update(ShogunMember)
        .where(ShogunMember.effective_posture_id == posture_id)
        .values(effective_posture_id=None)
    )
    await db.execute(
        sql_update(MemberGroup)
        .where(MemberGroup.posture_id == posture_id)
        .values(posture_id=None)
    )

    await db.delete(posture)
    await db.flush()
    return {"deleted": str(posture_id), "name": posture.name}
