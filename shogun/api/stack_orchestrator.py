"""Stack Orchestrator runtime-control API."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.schemas.common import ApiResponse
from shogun.schemas.stack_orchestrator import (
    StackArtifactResponse,
    StackCheckpointResponse,
    StackOrchestratorCreate,
    StackPlanDecision,
    StackRunResponse,
    StackStepDecision,
    StackStepResponse,
    StackVerificationResponse,
)
from shogun.services.stack_orchestrator import StackOrchestratorService

router = APIRouter(prefix="/stacks/orchestrator", tags=["Stack Orchestrator"])


def _response(stack, steps=()) -> StackRunResponse:
    data = StackRunResponse.model_validate(stack)
    data.steps = [StackStepResponse.model_validate(step) for step in steps]
    return data


def _bad_request(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 404 if "not found" in message.lower() or "does not exist" in message.lower() else 422
    return HTTPException(status_code=status, detail=message)


@router.post("/create", response_model=ApiResponse, status_code=201)
async def create_stack_run(body: StackOrchestratorCreate, db: AsyncSession = Depends(get_db)):
    service = StackOrchestratorService(db)
    try:
        stack = await service.create(body)
        stack, steps = await service.get(stack.id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=_response(stack, steps))


@router.get("", response_model=ApiResponse)
async def list_stack_runs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    service = StackOrchestratorService(db)
    runs = await service.list_runs(limit)
    return ApiResponse(data=[_response(run) for run in runs], meta={"total": len(runs)})


@router.post("/{stack_run_id}/plan-decision", response_model=ApiResponse)
async def decide_stack_plan(
    stack_run_id: uuid.UUID,
    body: StackPlanDecision,
    db: AsyncSession = Depends(get_db),
):
    service = StackOrchestratorService(db)
    try:
        await service.approve_plan(stack_run_id, body)
        stack, steps = await service.get(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=_response(stack, steps))


@router.post("/{stack_run_id}/step-decision", response_model=ApiResponse)
async def decide_stack_step(
    stack_run_id: uuid.UUID,
    body: StackStepDecision,
    db: AsyncSession = Depends(get_db),
):
    service = StackOrchestratorService(db)
    try:
        await service.approve_step(stack_run_id, body.step_id, body.approved, body.reason)
        stack, steps = await service.get(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=_response(stack, steps))


@router.post("/{stack_run_id}/start", response_model=ApiResponse)
async def start_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _transition(stack_run_id, "start", db)


@router.post("/{stack_run_id}/pause", response_model=ApiResponse)
async def pause_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _transition(stack_run_id, "pause", db)


@router.post("/{stack_run_id}/resume", response_model=ApiResponse)
async def resume_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _transition(stack_run_id, "resume", db)


@router.post("/{stack_run_id}/cancel", response_model=ApiResponse)
async def cancel_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _transition(stack_run_id, "cancel", db)


@router.post("/{stack_run_id}/recover", response_model=ApiResponse)
async def recover_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _transition(stack_run_id, "recover", db)


async def _transition(stack_run_id: uuid.UUID, action: str, db: AsyncSession) -> ApiResponse:
    service = StackOrchestratorService(db)
    try:
        await getattr(service, action)(stack_run_id)
        stack, steps = await service.get(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=_response(stack, steps), meta={"action": action})


@router.get("/{stack_run_id}", response_model=ApiResponse)
async def get_stack_run(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = StackOrchestratorService(db)
    try:
        stack, steps = await service.get(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=_response(stack, steps))


@router.get("/{stack_run_id}/tree", response_model=ApiResponse)
async def get_stack_tree(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        tree = await StackOrchestratorService(db).tree(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=tree)


@router.get("/{stack_run_id}/checkpoints", response_model=ApiResponse)
async def get_stack_checkpoints(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        rows = await StackOrchestratorService(db).checkpoints(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=[StackCheckpointResponse.model_validate(row) for row in rows])


@router.get("/{stack_run_id}/artifacts", response_model=ApiResponse)
async def get_stack_artifacts(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        rows = await StackOrchestratorService(db).artifacts(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=[StackArtifactResponse.model_validate(row) for row in rows])


@router.get("/{stack_run_id}/verifications", response_model=ApiResponse)
async def get_stack_verifications(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        rows = await StackOrchestratorService(db).verifications(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=[StackVerificationResponse.model_validate(row) for row in rows])


@router.get("/{stack_run_id}/summary", response_model=ApiResponse)
async def get_stack_summary(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = StackOrchestratorService(db)
    try:
        stack, _ = await service.get(stack_run_id)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    return ApiResponse(data=stack.final_summary or {"status": stack.status, "objective": stack.objective})
