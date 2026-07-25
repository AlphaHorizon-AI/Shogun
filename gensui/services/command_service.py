"""Command service — queues and manages commands dispatched to Shogun instances."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.db.models.command import Command


class CommandService:
    """Manages command dispatch to Shogun instances."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_pending(self, shogun_id: uuid.UUID) -> list[Command]:
        """Get all pending commands for a Shogun."""
        result = await self.session.execute(
            select(Command).where(
                Command.shogun_id == shogun_id,
                Command.status == "pending",
            ).order_by(Command.created_at)
        )
        return list(result.scalars().all())

    async def acknowledge(self, command_id: uuid.UUID, shogun_id: uuid.UUID) -> Command | None:
        """Mark a command as acknowledged by the Shogun."""
        result = await self.session.execute(
            select(Command).where(Command.id == command_id, Command.shogun_id == shogun_id)
        )
        cmd = result.scalars().first()
        if cmd is None:
            return None
        cmd.status = "acknowledged"
        cmd.acknowledged_at = datetime.now(timezone.utc)
        await self.session.flush()
        return cmd

    async def report_result(
        self,
        command_id: uuid.UUID,
        shogun_id: uuid.UUID,
        result_json: dict | None = None,
        error_message: str | None = None,
    ) -> Command | None:
        """Report the result of a command execution."""
        result = await self.session.execute(
            select(Command).where(Command.id == command_id, Command.shogun_id == shogun_id)
        )
        cmd = result.scalars().first()
        if cmd is None:
            return None
        cmd.status = "completed" if not error_message else "failed"
        cmd.result_json = result_json
        cmd.error_message = error_message
        cmd.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return cmd

    async def create(
        self,
        shogun_id: uuid.UUID,
        command_type: str,
        payload: dict | None = None,
    ) -> Command:
        """Create a new command for a Shogun."""
        cmd = Command(
            shogun_id=shogun_id,
            command_type=command_type,
            payload_json=payload or {},
        )
        self.session.add(cmd)
        await self.session.flush()
        await self.session.refresh(cmd)
        return cmd
