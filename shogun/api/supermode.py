"""Supermode mission and Mission Control API."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.db.engine import async_session_factory
from shogun.db.models.supermode import (
    MissionAgent,
    MissionApproval,
    MissionArtifact,
    MissionEvent,
    MissionLearning,
    MissionPlan,
    MissionTask,
)
from shogun.schemas.common import ApiResponse
from shogun.schemas.supermode import (
    AgentFlowCandidateRequest,
    ApprovalResolveRequest,
    MissionAgentCreateRequest,
    MissionPatchRequest,
    MissionSteerRequest,
    ReplanRequest,
    SupermodeMissionCreate,
)
from shogun.supermode.planner import revise_plan
from shogun.supermode.service import SupermodeMissionService, record_dict
from shogun.supermode.state_machine import transition_mission

router = APIRouter(prefix="/supermode", tags=["Supermode"])


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


async def _require_mission(service: SupermodeMissionService, mission_id: uuid.UUID):
    mission = await service.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Supermode mission not found")
    return mission


@router.post("/missions", response_model=ApiResponse, status_code=201)
async def create_supermode_mission(body: SupermodeMissionCreate, db: AsyncSession = Depends(get_db)):
    from shogun.services.posture_guard import check_supermode_access

    posture = await check_supermode_access()
    try:
        mission = await SupermodeMissionService(db).create(body, posture=posture)
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(
        data={
            **record_dict(mission),
            "mission_control_url": f"/chat?tab=mission-control&mission={mission.id}",
        }
    )


@router.get("/missions", response_model=ApiResponse)
async def list_supermode_missions(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    missions = await SupermodeMissionService(db).list(status=status, limit=limit)
    return ApiResponse(data=[record_dict(item) for item in missions], meta={"total": len(missions)})


@router.get("/missions/{mission_id}", response_model=ApiResponse)
async def get_supermode_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    return ApiResponse(data=await service.detail(mission))


@router.delete("/missions/{mission_id}", response_model=ApiResponse)
async def delete_supermode_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Delete one terminal mission run while retaining generated workspace files."""
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        await service.delete(mission)
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(
        data={
            "deleted": True,
            "mission_id": str(mission_id),
            "artifacts_retained": True,
        }
    )


@router.patch("/missions/{mission_id}", response_model=ApiResponse)
async def patch_supermode_mission(
    mission_id: uuid.UUID,
    body: MissionPatchRequest,
    db: AsyncSession = Depends(get_db),
):
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(mission, key, value)
    mission.updated_at = datetime.now(timezone.utc)
    return ApiResponse(data=record_dict(mission))


@router.post("/missions/{mission_id}/pause", response_model=ApiResponse)
async def pause_supermode_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        await service.pause(mission)
    except ValueError as exc:
        raise _conflict(exc) from exc
    await db.commit()
    return ApiResponse(data=record_dict(mission))


@router.post("/missions/{mission_id}/resume", response_model=ApiResponse)
async def resume_supermode_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.services.posture_guard import check_supermode_access

    await check_supermode_access()
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        await service.resume(mission)
    except ValueError as exc:
        raise _conflict(exc) from exc
    await db.commit()
    return ApiResponse(data=record_dict(mission))


@router.post("/missions/{mission_id}/cancel", response_model=ApiResponse)
async def cancel_supermode_mission(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    await service.cancel(mission)
    await db.commit()
    return ApiResponse(data=record_dict(mission))


@router.post("/missions/{mission_id}/steer", response_model=ApiResponse)
async def steer_supermode_mission(
    mission_id: uuid.UUID,
    body: MissionSteerRequest,
    db: AsyncSession = Depends(get_db),
):
    from shogun.services.posture_guard import check_supermode_access

    await check_supermode_access()
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        await service.steer(
            mission,
            instruction=body.instruction,
            add_constraints=body.add_constraints,
            remove_constraints=body.remove_constraints,
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(data=record_dict(mission))


@router.post("/missions/{mission_id}/replan", response_model=ApiResponse)
async def replan_supermode_mission(
    mission_id: uuid.UUID,
    body: ReplanRequest,
    db: AsyncSession = Depends(get_db),
):
    from shogun.services.posture_guard import check_supermode_access

    await check_supermode_access()
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    if mission.status != "running":
        raise HTTPException(status_code=409, detail="Only a running mission can be replanned")
    try:
        await transition_mission(db, mission, "replanning", reason=body.reason)
        plan = await revise_plan(db, mission, reason=body.reason, mutation={"type": "manual_replan"})
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(data=record_dict(plan))


async def _records(db: AsyncSession, model, mission_id: uuid.UUID, order_by):
    return [
        record_dict(item)
        for item in (
            await db.scalars(select(model).where(model.mission_id == mission_id).order_by(order_by))
        ).all()
    ]


@router.get("/missions/{mission_id}/agents", response_model=ApiResponse)
async def list_mission_agents(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionAgent, mission_id, MissionAgent.created_at))


@router.get("/missions/{mission_id}/tasks", response_model=ApiResponse)
async def list_mission_tasks(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionTask, mission_id, MissionTask.created_at))


@router.get("/missions/{mission_id}/plans", response_model=ApiResponse)
async def list_mission_plans(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionPlan, mission_id, MissionPlan.version))


@router.get("/missions/{mission_id}/events", response_model=ApiResponse)
async def list_mission_events(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionEvent, mission_id, MissionEvent.created_at.desc()))


@router.get("/missions/{mission_id}/artifacts", response_model=ApiResponse)
async def list_mission_artifacts(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionArtifact, mission_id, MissionArtifact.created_at.desc()))


@router.get("/missions/{mission_id}/learning", response_model=ApiResponse)
async def list_mission_learning(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionLearning, mission_id, MissionLearning.created_at.desc()))


@router.get("/missions/{mission_id}/approvals", response_model=ApiResponse)
async def list_mission_approvals(mission_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    await _require_mission(SupermodeMissionService(db), mission_id)
    return ApiResponse(data=await _records(db, MissionApproval, mission_id, MissionApproval.requested_at.desc()))


@router.post("/missions/{mission_id}/agents", response_model=ApiResponse, status_code=201)
async def create_mission_specialist(
    mission_id: uuid.UUID,
    body: MissionAgentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    from shogun.services.posture_guard import check_subagent_limit, check_supermode_access

    await check_supermode_access()
    await check_subagent_limit()
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        agent, task = await service.add_specialist(
            mission,
            role_name=body.role_name,
            role_description=body.role_description,
            objective=body.objective,
            spawn_reason=body.spawn_reason,
            required_capabilities=body.required_capabilities,
            required_tools=body.required_tools,
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(data={"agent": record_dict(agent), "task": record_dict(task)})


@router.delete("/missions/{mission_id}/agents/{agent_id}", response_model=ApiResponse)
async def terminate_mission_specialist(
    mission_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    agent = await service.terminate_agent(mission, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Mission agent not found")
    return ApiResponse(data=record_dict(agent))


@router.post("/approvals/{approval_id}/resolve", response_model=ApiResponse)
async def resolve_mission_approval(
    approval_id: uuid.UUID,
    body: ApprovalResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    approval = await db.get(MissionApproval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Mission approval not found")
    try:
        await SupermodeMissionService(db).resolve_approval(
            approval, resolution=body.resolution, note=body.note
        )
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(data=record_dict(approval))


@router.post("/missions/{mission_id}/agentflow-candidate", response_model=ApiResponse, status_code=201)
async def create_agentflow_from_mission(
    mission_id: uuid.UUID,
    body: AgentFlowCandidateRequest,
    db: AsyncSession = Depends(get_db),
):
    from shogun.services.posture_guard import check_supermode_access

    await check_supermode_access()
    service = SupermodeMissionService(db)
    mission = await _require_mission(service, mission_id)
    try:
        flow = await service.create_agentflow_candidate(mission, name=body.name)
    except ValueError as exc:
        raise _conflict(exc) from exc
    return ApiResponse(
        data={
            "id": str(flow.id),
            "name": flow.name,
            "status": flow.status,
            "editor_url": "/samurai#agent-flow",
        }
    )


@router.get("/missions/{mission_id}/stream")
async def stream_mission_events(mission_id: uuid.UUID, request: Request):
    """Best-effort SSE; REST remains authoritative after any disconnect."""

    async def events():
        cursor: datetime | None = None
        while not await request.is_disconnected():
            async with async_session_factory() as session:
                query = select(MissionEvent).where(MissionEvent.mission_id == mission_id)
                if cursor:
                    query = query.where(MissionEvent.created_at > cursor)
                records = list((await session.scalars(query.order_by(MissionEvent.created_at))).all())
                for record in records:
                    cursor = record.created_at
                    yield f"data: {json.dumps(record_dict(record), default=str)}\n\n"
            if not records:
                yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
