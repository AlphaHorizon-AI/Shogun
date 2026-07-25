"""Nexus External Gateway FastAPI Router."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.nexus.core.agent_registry import AgentRegistry
from shogun.nexus.core.capability_registry import CapabilityRegistry
from shogun.nexus.core.router import NexusRouter
from shogun.nexus.core.task_manager import TaskManager
from shogun.nexus.gateway.auth_handler import get_authenticated_agent
from shogun.nexus.gateway.response_handler import ResponseHandler
from shogun.nexus.protocols.a2a_adapter import A2AAdapter, A2ATaskRequest
from shogun.nexus.protocols.internal_shogun_adapter import InternalShogunAdapter
from shogun.nexus.schemas.agent_capability import AgentCapabilityResponse
from shogun.schemas.common import ApiResponse
from shogun.nexus.schemas.external_agent import ExternalAgentRegister, ExternalAgentResponse
from shogun.nexus.schemas.nexus_response import NexusResponse
from shogun.nexus.schemas.nexus_task import NexusTaskResponse
from shogun.nexus.security.audit_logger import NexusAuditLogger
from shogun.nexus.security.policy_hooks import PolicyHooks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nexus", tags=["Nexus Gateway"])


# ── External Agent Management ────────────────────────────────

@router.post("/external/register-agent", response_model=ApiResponse)
async def register_agent(body: ExternalAgentRegister, db: AsyncSession = Depends(get_db)):
    """Register a new trusted external enterprise agent.
    
    Returns the agent credentials including the API Token.
    """
    registry = AgentRegistry(db)
    try:
        agent = await registry.register_agent(body)
        return ApiResponse(
            data={
                **ExternalAgentResponse.model_validate(agent).model_dump(exclude={"token"}),
                "token": agent._issued_token,
            },
            meta={"message": "Agent registered successfully. Save the token; it is shown only once."}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/external/agents", response_model=ApiResponse)
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all registered external enterprise agents."""
    registry = AgentRegistry(db)
    agents = await registry.list_agents()
    return ApiResponse(data=[ExternalAgentResponse.model_validate(a) for a in agents])


# ── Capability Discovery ─────────────────────────────────────

@router.get("/capabilities", response_model=ApiResponse)
async def list_capabilities(db: AsyncSession = Depends(get_db)):
    """List all available capabilities exposed by Shogun agents."""
    registry = CapabilityRegistry(db)
    caps = await registry.list_capabilities()
    return ApiResponse(data=[AgentCapabilityResponse.model_validate(c) for c in caps])


# ── A2A Task Entry Point ─────────────────────────────────────

@router.post("/external/a2a/task", response_model=NexusResponse)
async def receive_a2a_task(
    body: A2ATaskRequest,
    background_tasks: BackgroundTasks,
    agent: Any = Depends(get_authenticated_agent),
    db: AsyncSession = Depends(get_db)
):
    """Receive an external A2A task request, validate policy, route and execute."""
    t_start = time.monotonic()
    
    # 1. Map to normalized task schema
    task_req = A2AAdapter.to_normalized_task(body)
    task_req.source_agent_id = str(agent.id)
    task_req.source_platform = agent.platform
    
    # 2. Persist task as pending
    manager = TaskManager(db)
    task = await manager.create_task(task_req)
    
    # 3. Log task receipt (L1/L2)
    audit_event_id = await NexusAuditLogger.log_task_received(task, agent)
    task.audit_metadata = {**task.audit_metadata, "receipt_event_id": audit_event_id}
    await db.commit()

    # 4. Evaluate Security Policies
    allowed, approval_required, policy_reason = await PolicyHooks.evaluate_task(task, agent)
    await NexusAuditLogger.log_policy_decision(task, agent, allowed, policy_reason)
    
    if not allowed:
        # Update status to blocked and return response
        task = await manager.update_task_status(
            task.id,
            status="blocked",
            error=policy_reason
        )
        latency = int((time.monotonic() - t_start) * 1000)
        await NexusAuditLogger.log_task_completion(task, agent, "blocked", latency, error_msg=policy_reason)
        return ResponseHandler.package_response(task, audit_event_id)

    # 5. Route the Task to an agent
    try:
        router_svc = NexusRouter(db)
        target_agent = await router_svc.route_task(task)
    except ValueError as exc:
        task = await manager.update_task_status(
            task.id,
            status="failed",
            error=str(exc)
        )
        latency = int((time.monotonic() - t_start) * 1000)
        await NexusAuditLogger.log_task_completion(task, agent, "failed", latency, error_msg=str(exc))
        return ResponseHandler.package_response(task, audit_event_id)

    # 6. Execute the Task on the Agent
    # Update state to executing
    task = await manager.update_task_status(task.id, status="executing")
    
    adapter = InternalShogunAdapter(db)
    result = await adapter.execute_on_agent(task, target_agent)
    
    # 7. Update status to completed or failed
    status = "completed" if result.get("status") == "success" else "failed"
    error_msg = result.get("output") if status == "failed" else None
    
    task = await manager.update_task_status(
        task.id,
        status=status,
        result=result,
        error=error_msg
    )
    
    latency = int((time.monotonic() - t_start) * 1000)
    await NexusAuditLogger.log_task_completion(task, agent, status, latency, error_msg=error_msg)
    
    return ResponseHandler.package_response(task, audit_event_id)


# ── Task Status & Callback Endpoints ─────────────────────────

def _agent_owns_task(task, agent) -> bool:
    target = (task.audit_metadata or {}).get("target_agent_id")
    return task.source_agent_id == str(agent.id) or target == str(agent.id)


@router.get("/external/task/{task_id}", response_model=ApiResponse)
async def get_task_status(
    task_id: uuid.UUID,
    agent: Any = Depends(get_authenticated_agent),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the current details and execution status of a task."""
    manager = TaskManager(db)
    task = await manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if not _agent_owns_task(task, agent):
        raise HTTPException(status_code=404, detail="Task not found.")
        
    return ApiResponse(data=NexusTaskResponse.model_validate(task))


@router.post("/external/task/{task_id}/callback", response_model=ApiResponse)
async def receive_task_callback(
    task_id: uuid.UUID,
    body: dict[str, Any],
    agent: Any = Depends(get_authenticated_agent),
    db: AsyncSession = Depends(get_db)
):
    """Receive or mock remote callback updates for a task."""
    manager = TaskManager(db)
    task = await manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
    if not _agent_owns_task(task, agent):
        raise HTTPException(status_code=404, detail="Task not found.")
        
    status = body.get("status", "completed")
    if status not in {"completed", "failed", "blocked"}:
        raise HTTPException(status_code=422, detail="Invalid callback status")
    result = body.get("result", {})
    error = body.get("error")
    
    task = await manager.update_task_status(task_id, status=status, result=result, error=error)
    return ApiResponse(
        data=NexusTaskResponse.model_validate(task),
        meta={"message": f"Task callback status updated successfully to '{status}'"}
    )


# ── Outbound Dispatch (Shogun → External Agent) ─────────────

class OutboundDispatchRequest(BaseModel):
    """Request body for dispatching a task to an external agent."""
    agent_id: str = Field(..., description="UUID of the target external agent")
    action: str = Field(..., description="The action to request, e.g. 'crm.update_contact'")
    input_context: dict[str, Any] = Field(default_factory=dict, description="Input data for the task")
    callback_url: str | None = Field(None, description="Optional URL for the external agent to call back with results")


@router.post("/external/dispatch", response_model=ApiResponse)
async def dispatch_outbound_task(
    body: OutboundDispatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Dispatch a task FROM Shogun TO an external enterprise agent.

    This is the reverse of the inbound A2A flow. Use this when Shogun needs
    to delegate work to an external platform (e.g. update a CRM record in
    Salesforce, schedule a meeting in Microsoft 365, create a ticket in ServiceNow).
    """
    from shogun.nexus.core.outbound_dispatcher import OutboundDispatcher

    dispatcher = OutboundDispatcher(db)
    try:
        task = await dispatcher.dispatch_task(
            agent_id=uuid.UUID(body.agent_id),
            action=body.action,
            input_context=body.input_context,
            callback_url=body.callback_url,
        )
        await db.commit()
        return ApiResponse(
            data=NexusTaskResponse.model_validate(task),
            meta={"message": f"Task dispatched to external agent (status: {task.status})"}
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/external/dispatchable-agents", response_model=ApiResponse)
async def list_dispatchable_agents(db: AsyncSession = Depends(get_db)):
    """List all external agents that can receive outbound tasks from Shogun."""
    from shogun.nexus.core.outbound_dispatcher import OutboundDispatcher

    dispatcher = OutboundDispatcher(db)
    agents = await dispatcher.list_dispatchable_agents()
    return ApiResponse(data=[ExternalAgentResponse.model_validate(a) for a in agents])

