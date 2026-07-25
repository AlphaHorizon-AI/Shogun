"""Commands API — Shogun instances poll for pending commands."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, get_shogun_identity
from gensui.services.command_service import CommandService

router = APIRouter(prefix="/commands", tags=["commands"])


@router.get("/{shogun_id}")
async def get_pending_commands(
    shogun_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: dict = Depends(get_shogun_identity),
):
    """Get pending commands for a Shogun instance."""
    if str(shogun_id) != identity["shogun_id"]:
        return []
    svc = CommandService(db)
    commands = await svc.get_pending(shogun_id)
    return [
        {
            "id": str(cmd.id),
            "command_type": cmd.command_type,
            "payload": cmd.payload_json,
            "created_at": cmd.created_at.isoformat() if cmd.created_at else None,
        }
        for cmd in commands
    ]


class CommandAckRequest(BaseModel):
    pass


class CommandResultRequest(BaseModel):
    result: dict | None = None
    error: str | None = None


@router.post("/{command_id}/ack")
async def acknowledge_command(
    command_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: dict = Depends(get_shogun_identity),
):
    """Acknowledge receipt of a command."""
    svc = CommandService(db)
    cmd = await svc.acknowledge(command_id, uuid.UUID(identity["shogun_id"]))
    if cmd is None:
        return {"status": "not_found"}
    return {"status": "acknowledged"}


@router.post("/{command_id}/result")
async def report_command_result(
    command_id: uuid.UUID,
    req: CommandResultRequest,
    db: AsyncSession = Depends(get_db),
    identity: dict = Depends(get_shogun_identity),
):
    """Report the result of a command execution."""
    svc = CommandService(db)
    cmd = await svc.report_result(
        command_id,
        uuid.UUID(identity["shogun_id"]),
        req.result,
        req.error,
    )
    if cmd is None:
        return {"status": "not_found"}
    return {"status": cmd.status}
