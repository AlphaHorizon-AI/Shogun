"""Nexus task manager module."""

from __future__ import annotations

import logging
import time
import uuid
import httpx
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.nexus import NexusTaskModel
from shogun.nexus.schemas.nexus_task import NexusTaskCreate
from shogun.nexus.security.outbound import validate_nexus_destination

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages normalized task creation, updates, and asynchronous callbacks."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(self, req: NexusTaskCreate) -> NexusTaskModel:
        """Create a new NexusTask record in the database."""
        task = NexusTaskModel(
            source_agent_id=req.source_agent_id,
            source_platform=req.source_platform,
            source_protocol=req.source_protocol,
            requested_action=req.requested_action,
            task_description=req.task_description,
            required_capabilities=req.required_capabilities,
            input_context=req.input_context,
            data_sensitivity=req.data_sensitivity,
            allowed_tools=req.allowed_tools,
            approval_required=req.approval_required,
            callback_url=req.callback_url,
            status="pending",
            result={},
            audit_metadata=req.audit_metadata
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_task(self, task_id: uuid.UUID) -> NexusTaskModel | None:
        """Retrieve a task by its unique database ID."""
        return await self.db.get(NexusTaskModel, task_id)

    async def update_task_status(
        self,
        task_id: uuid.UUID,
        status: str,
        result: dict | None = None,
        error: str | None = None
    ) -> NexusTaskModel:
        """Update task status and store outcomes."""
        task = await self.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found.")

        task.status = status
        task.updated_at = datetime.now(timezone.utc)
        
        res = result or {}
        if error:
            res["error"] = error
        task.result = res

        await self.db.commit()
        await self.db.refresh(task)

        # Trigger callback if configured
        if task.callback_url and status in ("completed", "failed", "blocked"):
            await self._trigger_callback(task)

        return task

    async def _trigger_callback(self, task: NexusTaskModel) -> None:
        """Fire an HTTP POST callback back to the requesting enterprise agent."""
        payload = {
            "task_id": str(task.id),
            "status": task.status,
            "result": task.result,
            "ts": time.time()
        }
        logger.info("Firing task callback to %s for task %s", task.callback_url, task.id)
        try:
            destination = validate_nexus_destination(task.callback_url)
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    destination.pinned_url,
                    json=payload,
                    headers={"Host": destination.host_header},
                    extensions=destination.request_extensions,
                )
                if resp.status_code >= 400:
                    logger.warning("Callback to %s returned status %d", task.callback_url, resp.status_code)
        except Exception as exc:
            logger.error("Failed to deliver callback to %s: %s", task.callback_url, exc)
            # Do not block execution or raise on callback failures
            pass
