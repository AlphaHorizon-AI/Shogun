"""Primary-Admin Team Mode and member-management endpoints."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.schemas.common import ApiResponse
from shogun.services.team_identity import (
    add_team_member,
    delete_team_member,
    get_team_state,
    set_team_mode,
)

router = APIRouter(prefix="/team", tags=["Team"])


class TeamModeUpdate(BaseModel):
    mode: Literal["single", "team"]


class TeamMemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    channel: Literal["telegram", "microsoft_teams"]
    telegram_user_id: str | None = None
    teams_aad_object_id: str | None = None
    teams_user_principal_name: str | None = None

    @model_validator(mode="after")
    def validate_channel_identity(self):
        if self.channel == "telegram" and not str(self.telegram_user_id or "").strip():
            raise ValueError("Telegram user ID is required.")
        if self.channel == "microsoft_teams" and not (
            str(self.teams_aad_object_id or "").strip()
            or str(self.teams_user_principal_name or "").strip()
        ):
            raise ValueError("Teams Entra Object ID or sign-in email is required.")
        return self


@router.get("", response_model=ApiResponse)
async def read_team(db: AsyncSession = Depends(get_db)):
    """Return the current Single/Team mode and active saved roster."""
    return ApiResponse(data=await get_team_state(db))


@router.put("/mode", response_model=ApiResponse)
async def update_team_mode(body: TeamModeUpdate, db: AsyncSession = Depends(get_db)):
    """Switch Single/Team mode and immediately update channel access."""
    try:
        return ApiResponse(data=await set_team_mode(db, body.mode))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/members", response_model=ApiResponse, status_code=201)
async def create_team_member(body: TeamMemberCreate, db: AsyncSession = Depends(get_db)):
    """Add a non-admin Telegram or Teams member."""
    try:
        return ApiResponse(data=await add_team_member(db, member=body.model_dump()))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/members/{member_id}", response_model=ApiResponse)
async def remove_team_member(member_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Revoke and remove a non-admin member; the Primary Admin is protected."""
    try:
        return ApiResponse(data=await delete_team_member(db, member_id))
    except ValueError as exc:
        detail = str(exc)
        status = 404 if detail == "Team Member not found." else 422
        raise HTTPException(status_code=status, detail=detail) from exc
