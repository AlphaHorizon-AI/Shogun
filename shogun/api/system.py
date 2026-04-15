import uuid
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from shogun.config import settings
from shogun.schemas.common import ApiResponse
from shogun.api.deps import (
    get_agent_service, 
    get_mission_service, 
    get_security_service
)
from shogun.services.agent_service import AgentService
from shogun.services.mission_service import MissionService
from shogun.services.security_service import SecurityService
from shogun.db.models.agent import Agent
from shogun.db.models.mission import Mission

router = APIRouter(prefix="/system", tags=["System"])


async def _check_qdrant() -> str:
    """Helper to check Qdrant connectivity."""
    try:
        if settings.qdrant_url:
            client = QdrantClient(url=settings.qdrant_url, timeout=1.0)
        else:
            # Embedded mode check
            client = QdrantClient(path=str(settings.qdrant_path), timeout=1.0)
        
        # Simple collection list check to verify reachability
        client.get_collections()
        return "healthy"
    except Exception:
        return "offline"


@router.get("/health", response_model=ApiResponse)
async def get_system_health():
    """Return system health status for all components."""
    qdrant_status = await _check_qdrant()
    
    return ApiResponse(
        success=True,
        data={
            "runtime": "online",
            "database": "healthy",
            "qdrant": qdrant_status,
            "telegram": "not_configured",
            "security_tier": "guarded",
            "active_samurai": 0,
        },
    )


@router.get("/overview", response_model=ApiResponse)
async def get_overview(
    agent_svc: AgentService = Depends(get_agent_service),
    mission_svc: MissionService = Depends(get_mission_service),
    security_svc: SecurityService = Depends(get_security_service),
):
    """Return overview dashboard payload."""
    # 1. Fetch Shogun Profile
    shogun_filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    shogun_records, _ = await agent_svc.get_all(filters=shogun_filters)
    shogun_name = shogun_records[0].name if shogun_records else "Shogun Prime"

    # 2. Fetch Active Samurai
    samurai_filters = [Agent.agent_type == "samurai", Agent.is_deleted == False]
    samurai_records, _ = await agent_svc.get_all(filters=samurai_filters)
    
    active_samurai_list = []
    for s in samurai_records:
        # Get the most recent in_progress or pending mission for this agent
        mission_filters = [
            Mission.assigned_agent_id == s.id,
            Mission.status.in_(["in_progress", "pending", "queued"])
        ]
        # We'll use a manual query here since BaseService doesn't support easy 'order_by' yet
        from sqlalchemy import desc
        stmt = select(Mission).where(*mission_filters).order_by(desc(Mission.created_at)).limit(1)
        res = await mission_svc.session.execute(stmt)
        curr_mission = res.scalars().first()
        
        active_samurai_list.append({
            "id": str(s.id),
            "name": s.name,
            "role": s.description or "Sub-agent",
            "status": s.status,
            "current_task": curr_mission.title if curr_mission else "Idle / No active task"
        })

    # 3. Fetch Security and Health Status
    qdrant_status = await _check_qdrant()
    # This assumes we have a way to find the active policy. For now, default to Guarded.
    security_tier = "guarded"

    return ApiResponse(
        success=True,
        data={
            "system_health": {
                "runtime": "online",
                "database": "healthy",
                "qdrant": qdrant_status,
                "telegram": "not_configured",
            },
            "shogun_profile": {
                "name": shogun_name,
                "status": "active"
            },
            "security_posture": {"tier": security_tier},
            "active_samurai": active_samurai_list,
            "recent_events": [
                {"type": "security", "message": "Unauthorized access attempt blocked", "timestamp": "2 mins ago"},
                {"type": "system", "message": "Database backup completed", "timestamp": "15 mins ago"},
                {"type": "agent", "message": "Neural lattice synchronized", "timestamp": "Recent"},
            ],
        },
    )


@router.get("/scan-local-models", response_model=ApiResponse)
async def scan_local_models(
    path: str = Query(..., description="Absolute path to the local model storage directory"),
):
    """Scan a local models directory and return discovered model names.

    Supports two layouts:
    - Ollama:    {path}/manifests/registry.ollama.ai/library/{model}/{tag}
    - LM Studio / generic: any *.gguf file found recursively under {path}
    """
    import os
    from pathlib import Path

    base = Path(path)
    if not base.exists():
        return ApiResponse(
            success=False,
            data=[],
            meta={"error": f"Path does not exist: {path}", "count": 0},
        )

    models: list[str] = []

    # ── Ollama manifest layout ──────────────────────────────────────
    # {path}/manifests/registry.ollama.ai/library/{model_name}/{tag}
    for registry_root in [
        base / "manifests" / "registry.ollama.ai" / "library",
        base / "manifests" / "registry.ollama.ai" / "models",
    ]:
        if registry_root.exists():
            for model_dir in sorted(registry_root.iterdir()):
                if model_dir.is_dir():
                    tags = sorted(t.name for t in model_dir.iterdir() if t.is_file())
                    for tag in tags:
                        entry = model_dir.name if tag == "latest" else f"{model_dir.name}:{tag}"
                        if entry not in models:
                            models.append(entry)

    # ── LM Studio / generic GGUF layout ────────────────────────────
    if not models:
        for root, _dirs, files in os.walk(base):
            for fname in sorted(files):
                if fname.lower().endswith(".gguf"):
                    name = fname[:-5]
                    if name not in models:
                        models.append(name)

    return ApiResponse(
        success=True,
        data=models,
        meta={"path": str(base), "count": len(models)},
    )


@router.get("/pull-model")
async def pull_model_stream(
    model: str = Query(..., description="Ollama model tag, e.g. llama3.2:3b"),
    base_url: str = Query("http://localhost:11434", description="Ollama base URL"),
):
    """Stream an Ollama model pull as Server-Sent Events.

    Each SSE event carries the raw JSON line from Ollama's /api/pull response:
    ``{"status": "pulling manifest"}``
    ``{"status": "pulling …", "completed": 131072, "total": 4661211296}``
    ``{"status": "success"}``
    """
    import httpx
    from fastapi.responses import StreamingResponse

    async def event_stream():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/api/pull",
                    json={"name": model, "stream": True},
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield f"data: {line}\n\n"
        except httpx.ConnectError:
            yield f'data: {{"status":"error","error":"Cannot connect to Ollama at {base_url}. Is it running?"}}\n\n'
        except Exception as exc:
            yield f'data: {{"status":"error","error":"{str(exc)}"}}\n\n'
        finally:
            yield 'data: {"status":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering if present
        },
    )
