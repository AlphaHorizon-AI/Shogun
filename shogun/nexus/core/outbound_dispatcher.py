"""Outbound Dispatch — send tasks FROM Shogun TO external enterprise agents.

This is the reverse direction of the inbound A2A gateway. When Shogun needs
to delegate work to an external platform (e.g. ask Salesforce to update a
CRM record, ask M365 to schedule a meeting), it dispatches via this service.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.nexus import ExternalAgentModel, NexusTaskModel
from shogun.nexus.security.outbound import validate_nexus_destination

logger = logging.getLogger(__name__)


class OutboundDispatcher:
    """Dispatches tasks from Shogun to registered external agents."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispatch_task(
        self,
        agent_id: uuid.UUID,
        action: str,
        input_context: dict[str, Any] | None = None,
        callback_url: str | None = None,
    ) -> NexusTaskModel:
        """Send a task to an external enterprise agent.

        The external agent must have an endpoint_url configured and its
        direction must be 'outbound' or 'bidirectional'.
        """
        # 1. Look up the agent
        agent = await self.db.get(ExternalAgentModel, agent_id)
        if agent is None or agent.is_deleted:
            raise ValueError(f"External agent {agent_id} not found.")
        if not agent.is_active:
            raise ValueError(f"External agent '{agent.name}' is deactivated.")
        if agent.direction == "inbound":
            raise ValueError(
                f"Agent '{agent.name}' is inbound-only — cannot dispatch tasks to it."
            )
        if not agent.endpoint_url:
            raise ValueError(
                f"Agent '{agent.name}' has no endpoint_url — cannot dispatch."
            )

        # 2. Create the outbound task record
        task = NexusTaskModel(
            source_agent_id=f"shogun::{uuid.uuid4().hex[:12]}",
            source_platform="shogun",
            source_protocol="outbound_dispatch",
            requested_action=action,
            task_description=f"Outbound task to {agent.platform}: {action}",
            required_capabilities=[action],
            input_context=input_context or {},
            data_sensitivity="internal",
            allowed_tools=[],
            approval_required=False,
            callback_url=callback_url,
            status="dispatching",
            result={},
            audit_metadata={
                "direction": "outbound",
                "target_agent_id": str(agent.id),
                "target_platform": agent.platform,
            },
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        # 3. HTTP POST to the external agent's endpoint
        t_start = time.monotonic()
        payload = {
            "task_id": str(task.id),
            "action": action,
            "input": input_context or {},
            "source": "shogun",
            "callback_url": callback_url,
        }

        try:
            destination = validate_nexus_destination(agent.endpoint_url)
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    destination.pinned_url,
                    json=payload,
                    headers={
                        "Host": destination.host_header,
                        "Content-Type": "application/json",
                        "X-Shogun-Task-Id": str(task.id),
                    },
                    extensions=destination.request_extensions,
                )

            latency_ms = int((time.monotonic() - t_start) * 1000)

            if resp.status_code < 400:
                task.status = "dispatched"
                task.result = {
                    "remote_status_code": resp.status_code,
                    "remote_response": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"body": resp.text[:500]},
                    "latency_ms": latency_ms,
                }
                logger.info(
                    "[OutboundDispatch] Task %s dispatched to %s (%s) in %dms",
                    task.id, agent.name, agent.platform, latency_ms,
                )
            else:
                task.status = "dispatch_failed"
                task.result = {
                    "remote_status_code": resp.status_code,
                    "error": resp.text[:500],
                    "latency_ms": latency_ms,
                }
                logger.warning(
                    "[OutboundDispatch] Task %s dispatch failed: HTTP %d from %s",
                    task.id, resp.status_code, agent.endpoint_url,
                )

        except Exception as exc:
            latency_ms = int((time.monotonic() - t_start) * 1000)
            task.status = "dispatch_failed"
            task.result = {
                "error": str(exc),
                "latency_ms": latency_ms,
            }
            logger.error(
                "[OutboundDispatch] Task %s network error dispatching to %s: %s",
                task.id, agent.endpoint_url, exc,
            )

        await self.db.flush()
        return task

    async def list_dispatchable_agents(self) -> list[ExternalAgentModel]:
        """List all agents that can receive outbound tasks."""
        result = await self.db.execute(
            select(ExternalAgentModel).where(
                ExternalAgentModel.is_deleted == False,
                ExternalAgentModel.is_active == True,
                ExternalAgentModel.direction.in_(["outbound", "bidirectional"]),
                ExternalAgentModel.endpoint_url.isnot(None),
            )
        )
        return list(result.scalars().all())
