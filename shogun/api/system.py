"""System routes — health, overview, runtime diagnostics."""

from __future__ import annotations

from fastapi import APIRouter

from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/health", response_model=ApiResponse)
async def get_system_health():
    """Return system health status for all components."""
    return ApiResponse(
        success=True,
        data={
            "runtime": "online",
            "database": "healthy",
            "qdrant": "unknown",
            "telegram": "not_configured",
            "security_tier": "guarded",
            "active_samurai": 0,
        },
    )


@router.get("/overview", response_model=ApiResponse)
async def get_overview():
    """Return overview dashboard payload."""
    return ApiResponse(
        success=True,
        data={
            "system_health": {
                "runtime": "online",
                "database": "healthy",
                "qdrant": "unknown",
                "telegram": "not_configured",
            },
            "shogun_profile": None,
            "security_posture": {"tier": "guarded"},
            "active_samurai": [],
            "recent_events": [],
        },
    )
