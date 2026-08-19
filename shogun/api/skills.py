"""Skill routes — CRUD, import, install for the Dojo."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db, get_skill_service, get_skill_source_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.skills import (
    ActiveSkillRunResponse,
    SkillActivationRequest,
    SkillActivationResponse,
    SkillOutcomeRequest,
    SkillResponse,
    SkillSourceCreate,
    SkillSourceResponse,
    SkillTrajectoryExportRequest,
)
from shogun.services.active_skill_service import SkillActivationService, SkillEmbeddingService
from shogun.services.event_logger import EventLogger
from shogun.services.skill_service import SkillService, SkillSourceService
from shogun.services.skill_trajectory_service import SkillTrajectoryExporter

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("/sources", response_model=ApiResponse)
async def list_sources(svc: SkillSourceService = Depends(get_skill_source_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[SkillSourceResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/sources", response_model=ApiResponse, status_code=201)
async def add_source(
    body: SkillSourceCreate,
    svc: SkillSourceService = Depends(get_skill_source_service),
):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=SkillSourceResponse.model_validate(record))


@router.get("", response_model=ApiResponse)
async def list_skills(
    source_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    svc: SkillService = Depends(get_skill_service),
):
    from shogun.db.models.skill import Skill
    filters = [Skill.is_deleted == False]
    if source_id:
        filters.append(Skill.source_id == source_id)
    if status:
        filters.append(Skill.status == status)
    if search:
        filters.append(Skill.name.ilike(f"%{search.strip()}%"))

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[SkillResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/activate", response_model=ApiResponse)
async def activate_skills(body: SkillActivationRequest, db: AsyncSession = Depends(get_db)):
    service = SkillActivationService(db)
    result = await service.activate(body)
    await db.commit()
    return ApiResponse(data=SkillActivationResponse.model_validate(result))


@router.post("/outcome", response_model=ApiResponse)
async def report_skill_outcome(body: SkillOutcomeRequest, db: AsyncSession = Depends(get_db)):
    service = SkillActivationService(db)
    try:
        record = await service.outcome(body.active_skill_run_id, body.outcome, body.outcome_summary)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return ApiResponse(data={"id": str(record.id), "outcome": record.outcome})


@router.get("/active-runs", response_model=ApiResponse)
async def list_active_skill_runs(
    run_id: str | None = None,
    stack_run_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    from shogun.db.models.active_skill_run import ActiveSkillRun
    from shogun.db.models.skill import Skill

    query = (
        select(ActiveSkillRun, Skill.name)
        .join(Skill, Skill.id == ActiveSkillRun.skill_id)
        .order_by(ActiveSkillRun.created_at.desc())
        .limit(limit)
    )
    if run_id:
        query = query.where(ActiveSkillRun.run_id == run_id)
    if stack_run_id:
        query = query.where(ActiveSkillRun.stack_run_id == stack_run_id)
    rows = (await db.execute(query)).all()
    data = []
    for record, skill_name in rows:
        payload = ActiveSkillRunResponse.model_validate(record).model_dump()
        payload["skill_name"] = skill_name
        data.append(payload)
    return ApiResponse(data=data, meta={"total": len(data)})


@router.get("/trajectories", response_model=ApiResponse)
async def list_skill_trajectories(
    skill_id: uuid.UUID | None = None,
    run_id: str | None = None,
    stack_run_id: uuid.UUID | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    outcome: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_trajectory import SkillEpisode, SkillTrajectory

    query = select(SkillTrajectory, SkillEpisode, Skill.name).join(
        SkillEpisode, SkillEpisode.id == SkillTrajectory.skill_episode_id
    ).join(Skill, Skill.id == SkillTrajectory.skill_id)
    if skill_id:
        query = query.where(SkillTrajectory.skill_id == skill_id)
    if run_id:
        query = query.where(SkillTrajectory.run_id == run_id)
    if stack_run_id:
        query = query.where(SkillTrajectory.stack_run_id == stack_run_id)
    if agent_id:
        query = query.where(SkillEpisode.agent_id == agent_id)
    if model_id:
        query = query.where(SkillEpisode.model_id == model_id)
    if outcome:
        query = query.where(SkillTrajectory.final_outcome == outcome)
    if from_date:
        query = query.where(SkillTrajectory.created_at >= from_date)
    if to_date:
        query = query.where(SkillTrajectory.created_at <= to_date)
    rows = (await db.execute(query.order_by(SkillTrajectory.created_at.desc()).limit(limit))).all()
    data = [{
        "id": str(item.id), "skill_episode_id": str(item.skill_episode_id), "skill_id": str(item.skill_id),
        "skill_name": name, "skill_version": item.skill_version, "run_id": item.run_id,
        "stack_run_id": str(item.stack_run_id) if item.stack_run_id else None,
        "step_run_id": str(item.step_run_id) if item.step_run_id else None,
        "task_summary": episode.task_summary, "model_id": episode.model_id, "model_profile": episode.model_profile,
        "agent_id": episode.agent_id, "posture": episode.posture, "status": episode.status,
        "final_outcome": item.final_outcome, "contribution": item.contribution, "score": item.score,
        "created_at": item.created_at, "finalized_at": item.finalized_at,
    } for item, episode, name in rows]
    return ApiResponse(data=data, meta={"total": len(data)})


@router.post("/trajectories/export")
async def export_skill_trajectories(body: SkillTrajectoryExportRequest, db: AsyncSession = Depends(get_db)):
    return await _export_skill_trajectories_impl(body, db)


@router.get("/trajectories/{trajectory_id}", response_model=ApiResponse)
async def get_skill_trajectory(trajectory_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_trajectory import (
        SkillEpisode,
        SkillImprovementCandidate,
        SkillToolLink,
        SkillTrajectory,
        SkillVerificationLink,
    )

    item = await db.get(SkillTrajectory, trajectory_id)
    if not item:
        raise HTTPException(status_code=404, detail="Skill trajectory not found")
    episode = await db.get(SkillEpisode, item.skill_episode_id)
    skill = await db.get(Skill, item.skill_id)
    tools = list((await db.execute(select(SkillToolLink).where(SkillToolLink.skill_episode_id == episode.id))).scalars().all())
    verifications = list((await db.execute(select(SkillVerificationLink).where(SkillVerificationLink.skill_episode_id == episode.id))).scalars().all())
    improvements = list((await db.execute(select(SkillImprovementCandidate).where(SkillImprovementCandidate.based_on_trajectory_id == item.id))).scalars().all())
    return ApiResponse(data={
        "id": str(item.id), "skill_name": skill.name if skill else str(item.skill_id),
        "trajectory": item.trajectory_json, "episode": {
            "id": str(episode.id), "status": episode.status, "task_summary": episode.task_summary,
            "selection_reason": episode.selection_reason, "model_id": episode.model_id,
            "model_profile": episode.model_profile, "posture": episode.posture,
            "flow_id": episode.flow_id, "node_id": episode.node_id, "agent_id": episode.agent_id,
            "started_at": episode.started_at, "completed_at": episode.completed_at,
        },
        "tool_links": [{"id": str(link.id), "tool_call_id": link.tool_call_id, "tool_name": link.tool_name,
                        "input_summary": link.tool_input_summary, "output_summary": link.tool_output_summary,
                        "status": link.status, "created_at": link.created_at} for link in tools],
        "verification_links": [{"id": str(link.id), "verification_id": link.verification_id,
                                "type": link.verification_type, "expected": link.expected_result,
                                "observed": link.observed_result, "status": link.status,
                                "score": link.score, "created_at": link.created_at} for link in verifications],
        "improvement_candidates": [{"id": str(candidate.id), "issue_type": candidate.issue_type,
                                    "observed_problem": candidate.observed_problem,
                                    "suggested_improvement": candidate.suggested_improvement,
                                    "validation_idea": candidate.validation_idea, "priority": candidate.priority,
                                    "status": candidate.status} for candidate in improvements],
    })


@router.get("/episodes", response_model=ApiResponse)
async def list_skill_episodes(
    skill_id: uuid.UUID | None = None, run_id: str | None = None,
    status: str | None = None, limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_trajectory import SkillEpisode

    query = select(SkillEpisode, Skill.name).join(Skill, Skill.id == SkillEpisode.skill_id)
    if skill_id:
        query = query.where(SkillEpisode.skill_id == skill_id)
    if run_id:
        query = query.where(SkillEpisode.run_id == run_id)
    if status:
        query = query.where(SkillEpisode.status == status)
    rows = (await db.execute(query.order_by(SkillEpisode.created_at.desc()).limit(limit))).all()
    return ApiResponse(data=[{
        "id": str(item.id), "active_skill_run_id": str(item.active_skill_run_id) if item.active_skill_run_id else None,
        "skill_id": str(item.skill_id), "skill_name": name, "skill_version": item.skill_version,
        "run_id": item.run_id, "stack_run_id": str(item.stack_run_id) if item.stack_run_id else None,
        "step_run_id": str(item.step_run_id) if item.step_run_id else None, "flow_id": item.flow_id,
        "node_id": item.node_id, "agent_id": item.agent_id, "model_id": item.model_id,
        "posture": item.posture, "task_summary": item.task_summary,
        "selection_reason": item.selection_reason, "injection_mode": item.injection_mode,
        "status": item.status, "started_at": item.started_at, "completed_at": item.completed_at,
    } for item, name in rows], meta={"total": len(rows)})


@router.get("/improvement-candidates", response_model=ApiResponse)
async def list_skill_improvement_candidates(
    skill_id: uuid.UUID | None = None, status: str | None = None,
    limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db),
):
    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_trajectory import SkillImprovementCandidate

    query = select(SkillImprovementCandidate, Skill.name).join(Skill, Skill.id == SkillImprovementCandidate.skill_id)
    if skill_id:
        query = query.where(SkillImprovementCandidate.skill_id == skill_id)
    if status:
        query = query.where(SkillImprovementCandidate.status == status)
    rows = (await db.execute(query.order_by(SkillImprovementCandidate.created_at.desc()).limit(limit))).all()
    return ApiResponse(data=[{
        "id": str(item.id), "skill_id": str(item.skill_id), "skill_name": name,
        "skill_version": item.skill_version, "based_on_trajectory_id": str(item.based_on_trajectory_id) if item.based_on_trajectory_id else None,
        "issue_type": item.issue_type, "observed_problem": item.observed_problem,
        "suggested_improvement": item.suggested_improvement, "validation_idea": item.validation_idea,
        "priority": item.priority, "status": item.status, "created_at": item.created_at,
    } for item, name in rows], meta={"total": len(rows)})


async def _export_skill_trajectories_impl(body: SkillTrajectoryExportRequest, db: AsyncSession):
    from shogun.db.models.skill_trajectory import SkillEpisode, SkillTrajectory

    if body.include_raw_prompts or body.include_full_tool_outputs:
        raise HTTPException(status_code=403, detail="Raw prompt and full tool-output export is disabled; summary-only export is enforced.")
    if body.format not in {"jsonl", "markdown", "zip"}:
        raise HTTPException(status_code=422, detail="Export format must be jsonl, markdown, or zip.")
    query = select(SkillTrajectory).join(SkillEpisode, SkillEpisode.id == SkillTrajectory.skill_episode_id)
    if body.skill_ids:
        query = query.where(SkillTrajectory.skill_id.in_(body.skill_ids))
    if body.skill_version:
        query = query.where(SkillTrajectory.skill_version == body.skill_version)
    if body.model_id:
        query = query.where(SkillEpisode.model_id == body.model_id)
    if body.outcome:
        query = query.where(SkillTrajectory.final_outcome == body.outcome)
    if body.minimum_score is not None:
        query = query.where(SkillTrajectory.score >= body.minimum_score)
    if body.from_date:
        query = query.where(SkillTrajectory.created_at >= body.from_date)
    if body.to_date:
        query = query.where(SkillTrajectory.created_at <= body.to_date)
    rows = (await db.execute(
        query.with_only_columns(SkillTrajectory, SkillEpisode)
        .order_by(SkillTrajectory.created_at.desc())
    )).all()
    if body.task_type:
        rows = [
            (item, episode) for item, episode in rows
            if (episode.metadata_json or {}).get("usage_location") == body.task_type
        ]
    items = [item for item, _episode in rows]
    content, content_type, filename = await SkillTrajectoryExporter(db).export(items, body.format)
    await EventLogger.emit(
        category="skill", event_type="skill.trajectory.exported", action=f"Exported {len(items)} redacted skill trajectories",
        detail={"format": body.format, "count": len(items), "redacted": True}, db_session=db,
    )
    await db.commit()
    return Response(content=content, media_type=content_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{skill_id}/performance", response_model=ApiResponse)
async def get_skill_performance(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_trajectory import SkillEpisode, SkillImprovementCandidate, SkillTrajectory

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    rows = (await db.execute(select(SkillTrajectory, SkillEpisode).join(
        SkillEpisode, SkillEpisode.id == SkillTrajectory.skill_episode_id
    ).where(SkillTrajectory.skill_id == skill_id))).all()
    outcomes = [item.final_outcome for item, _ in rows]
    model_scores: dict[str, list[float]] = {}
    for item, episode in rows:
        if episode.model_id:
            model_scores.setdefault(episode.model_id, []).append(item.score)
    averages = {model: sum(scores) / len(scores) for model, scores in model_scores.items()}
    candidates = list((await db.execute(select(SkillImprovementCandidate).where(
        SkillImprovementCandidate.skill_id == skill_id
    ).order_by(SkillImprovementCandidate.created_at.desc()).limit(10))).scalars().all())
    return ApiResponse(data={
        "skill_id": str(skill.id), "skill_name": skill.name, "skill_version": skill.version,
        "uses": len(rows), "successes": outcomes.count("success"),
        "partial_successes": outcomes.count("partial_success"), "failures": outcomes.count("failure"),
        "blocked": outcomes.count("blocked"),
        "average_score": round(sum(item.score for item, _ in rows) / len(rows), 3) if rows else 0.0,
        "best_model": max(averages, key=averages.get) if averages else None,
        "worst_model": min(averages, key=averages.get) if averages else None,
        "model_performance": averages,
        "common_failure_modes": list(dict.fromkeys(item.observed_problem for item in candidates))[:5],
        "improvement_candidates": len(candidates), "last_used": skill.last_used_at,
    })


async def _set_skill_status(skill_id: uuid.UUID, status: str, db: AsyncSession):
    from shogun.db.models.skill import Skill
    from shogun.services.enterprise_transformation_skill import assert_skill_mutable

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    if status != "installed":
        try:
            assert_skill_mutable(skill, f"set status to {status!r} on")
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    skill.status = status
    await EventLogger.emit(
        category="skill", event_type=f"skill.{status}",
        action=f"Skill '{skill.name}' {status}", detail={"skill_id": str(skill.id)}, db_session=db,
    )
    await db.commit()
    return ApiResponse(data=SkillResponse.model_validate(skill))


@router.post("/{skill_id}/enable", response_model=ApiResponse)
async def enable_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_skill_status(skill_id, "installed", db)


@router.post("/{skill_id}/disable", response_model=ApiResponse)
async def disable_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_skill_status(skill_id, "disabled", db)


@router.post("/{skill_id}/rebuild-brief", response_model=ApiResponse)
async def rebuild_skill_brief(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    brief = await SkillActivationService(db).rebuild_brief(skill)
    await db.commit()
    return ApiResponse(data={"skill_id": str(skill.id), "brief": brief})


@router.post("/{skill_id}/reindex", response_model=ApiResponse)
async def reindex_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    try:
        embedding_id = await SkillEmbeddingService.index(skill)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Skill index unavailable: {exc}") from exc
    await EventLogger.emit(
        category="skill", event_type="skill.indexed", action=f"Skill '{skill.name}' indexed",
        detail={"skill_id": str(skill.id), "embedding_id": embedding_id}, db_session=db,
    )
    await db.commit()
    return ApiResponse(data={"skill_id": str(skill.id), "embedding_id": embedding_id})


@router.get("/{skill_id}", response_model=ApiResponse)
async def get_skill(skill_id: uuid.UUID, svc: SkillService = Depends(get_skill_service)):
    record = await svc.get_by_id(skill_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    return ApiResponse(data=SkillResponse.model_validate(record))
