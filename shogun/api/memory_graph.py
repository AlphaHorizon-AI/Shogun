"""Kiroku MemoryGraph CRUD, backfill, traversal, and conflict APIs."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.schemas.common import ApiResponse
from shogun.schemas.memory_graph import (
    MemoryConflictCreate,
    MemoryConflictResolve,
    MemoryConflictResponse,
    MemoryGraphBackfillRequest,
    MemoryGraphBackfillResponse,
    MemoryGraphEdgeCreate,
    MemoryGraphEdgeResponse,
    MemoryGraphNeighborhoodResponse,
    MemoryGraphNodeCreate,
    MemoryGraphNodeResponse,
    MemoryGraphNodeUpdate,
)
from shogun.services.memory_graph_service import MemoryGraphService

router = APIRouter(prefix="/memory-graph", tags=["Kiroku MemoryGraph"])


def get_memory_graph_service(db: AsyncSession = Depends(get_db)) -> MemoryGraphService:
    return MemoryGraphService(db)


@router.get("/nodes", response_model=ApiResponse[list[MemoryGraphNodeResponse]])
async def list_nodes(
    node_type: str | None = None,
    status: str | None = "active",
    tenant_id: str = "local",
    workspace_id: str | None = None,
    project_id: str | None = None,
    agent_id: uuid.UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    nodes, total = await svc.repository.nodes(
        node_type=node_type,
        status=status,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        project_id=project_id,
        agent_id=agent_id,
        offset=offset,
        limit=limit,
    )
    return ApiResponse(
        data=[MemoryGraphNodeResponse.model_validate(node) for node in nodes],
        meta={"total": total, "offset": offset, "limit": limit},
    )


@router.get("/search", response_model=ApiResponse[list[MemoryGraphNodeResponse]])
async def search_nodes(
    query: str = Query(..., min_length=1),
    tenant_id: str = "local",
    node_type: str | None = None,
    project_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    nodes, total = await svc.repository.nodes(
        query=query,
        tenant_id=tenant_id,
        node_type=node_type,
        project_id=project_id,
        limit=limit,
    )
    return ApiResponse(
        data=[MemoryGraphNodeResponse.model_validate(node) for node in nodes],
        meta={"total": total},
    )


@router.post("/nodes", response_model=ApiResponse[MemoryGraphNodeResponse], status_code=201)
async def create_node(
    body: MemoryGraphNodeCreate,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    try:
        node = await svc.create_node(body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=MemoryGraphNodeResponse.model_validate(node))


@router.get("/nodes/{node_id}", response_model=ApiResponse[MemoryGraphNodeResponse])
async def get_node(
    node_id: uuid.UUID,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    node = await svc.repository.node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return ApiResponse(data=MemoryGraphNodeResponse.model_validate(node))


@router.put("/nodes/{node_id}", response_model=ApiResponse[MemoryGraphNodeResponse])
async def update_node(
    node_id: uuid.UUID,
    body: MemoryGraphNodeUpdate,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    node = await svc.update_node(node_id, body)
    if node is None:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return ApiResponse(data=MemoryGraphNodeResponse.model_validate(node))


@router.delete("/nodes/{node_id}", response_model=ApiResponse[dict])
async def deprecate_node(
    node_id: uuid.UUID,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    if not await svc.deprecate_node(node_id):
        raise HTTPException(status_code=404, detail="Graph node not found")
    return ApiResponse(data={"node_id": str(node_id), "status": "deprecated"})


@router.get("/nodes/{node_id}/neighborhood", response_model=ApiResponse[MemoryGraphNeighborhoodResponse])
async def node_neighborhood(
    node_id: uuid.UUID,
    depth: int = Query(1, ge=1, le=2),
    limit: int = Query(250, ge=1, le=1000),
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    try:
        nodes, edges = await svc.neighborhood(node_id, depth=depth, limit=limit)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(
        data=MemoryGraphNeighborhoodResponse(
            root_node_id=node_id,
            nodes=[MemoryGraphNodeResponse.model_validate(node) for node in nodes],
            edges=[MemoryGraphEdgeResponse.model_validate(edge) for edge in edges],
        )
    )


@router.get("/edges", response_model=ApiResponse[list[MemoryGraphEdgeResponse]])
async def list_edges(
    node_id: uuid.UUID | None = None,
    relationship_type: str | None = None,
    limit: int = Query(250, ge=1, le=1000),
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    edges = await svc.repository.edges(
        node_id=node_id, relationship_type=relationship_type, limit=limit
    )
    return ApiResponse(data=[MemoryGraphEdgeResponse.model_validate(edge) for edge in edges])


@router.post("/edges", response_model=ApiResponse[MemoryGraphEdgeResponse], status_code=201)
async def create_edge(
    body: MemoryGraphEdgeCreate,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    try:
        edge = await svc.create_edge(body)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=MemoryGraphEdgeResponse.model_validate(edge))


@router.post("/backfill", response_model=ApiResponse[MemoryGraphBackfillResponse])
async def backfill_graph(
    body: MemoryGraphBackfillRequest,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    return ApiResponse(data=await svc.backfill(**body.model_dump()))


@router.get("/conflicts", response_model=ApiResponse[list[MemoryConflictResponse]])
async def list_conflicts(
    resolution_status: str | None = "needs_review",
    limit: int = Query(100, ge=1, le=500),
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    conflicts = await svc.repository.conflicts(
        resolution_status=resolution_status, limit=limit
    )
    return ApiResponse(data=[MemoryConflictResponse.model_validate(item) for item in conflicts])


@router.post("/conflicts", response_model=ApiResponse[MemoryConflictResponse], status_code=201)
async def create_conflict(
    body: MemoryConflictCreate,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    try:
        conflict = await svc.create_conflict(**body.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=MemoryConflictResponse.model_validate(conflict))


@router.post(
    "/conflicts/{conflict_id}/resolve",
    response_model=ApiResponse[MemoryConflictResponse],
)
async def resolve_conflict(
    conflict_id: uuid.UUID,
    body: MemoryConflictResolve,
    svc: MemoryGraphService = Depends(get_memory_graph_service),
):
    try:
        conflict = await svc.resolve_conflict(conflict_id, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if conflict is None:
        raise HTTPException(status_code=404, detail="Memory conflict not found")
    return ApiResponse(data=MemoryConflictResponse.model_validate(conflict))
