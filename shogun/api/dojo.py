"""Dojo API routes — OpenClaw College integration + skill catalog.

Provides endpoints for browsing the OpenClaw College catalog, syncing skills
into the local Dojo, and managing the default learning source.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shogun.integrations.openclaw_client import (
    OPENCLAW_BASE_URL,
    OPENCLAW_GITHUB_URL,
    OPENCLAW_SOURCE_NAME,
    OPENCLAW_SOURCE_SLUG,
    get_openclaw_client,
)
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/dojo", tags=["Dojo"])


# ── Health ────────────────────────────────────────────────────

@router.get("/openclaw/health", response_model=ApiResponse)
async def openclaw_health():
    """Check if the OpenClaw College API is reachable."""
    async with get_openclaw_client() as client:
        healthy = await client.health_check()
    return ApiResponse(
        data={
            "source": OPENCLAW_SOURCE_NAME,
            "slug": OPENCLAW_SOURCE_SLUG,
            "api_url": OPENCLAW_BASE_URL,
            "github_url": OPENCLAW_GITHUB_URL,
            "healthy": healthy,
        }
    )


# ── Stats ─────────────────────────────────────────────────────

@router.get("/openclaw/stats", response_model=ApiResponse)
async def openclaw_stats():
    """Get OpenClaw College platform statistics."""
    async with get_openclaw_client() as client:
        stats = await client.get_stats()
    return ApiResponse(
        data={
            "skills": stats.skills,
            "bundles": stats.bundles,
            "specializations": stats.specializations,
            "badges": stats.badges,
            "agents": stats.agents,
            "categories": stats.categories,
            "faculties": stats.faculties,
            "subcategories": stats.subcategories,
        }
    )


# ── Categories ────────────────────────────────────────────────

@router.get("/openclaw/categories", response_model=ApiResponse)
async def openclaw_categories():
    """List all skill categories from OpenClaw College."""
    async with get_openclaw_client() as client:
        cats = await client.get_categories()
    return ApiResponse(data=cats)


# ── Skills ────────────────────────────────────────────────────

@router.get("/openclaw/skills", response_model=ApiResponse)
async def openclaw_skills(
    faculty: str | None = None,
    subcategory: str | None = None,
    risk_tier: str | None = None,
    search: str | None = None,
    limit: int = 100,
):
    """Browse skills from the OpenClaw College catalog.

    Returns up to `limit` skills, optionally filtered by faculty,
    subcategory, risk tier, or search query.
    """
    async with get_openclaw_client() as client:
        skills = await client.get_skills(
            faculty=faculty,
            subcategory=subcategory,
            risk_tier=risk_tier,
            search=search,
            limit=limit,
        )
    return ApiResponse(
        data=[
            {
                "id": s.id,
                "slug": s.slug,
                "name": s.name,
                "description": s.short_description,
                "faculty": s.faculty_id,
                "subcategory": s.subcategory_id,
                "risk_tier": s.risk_tier,
                "version": s.version,
                "capabilities": s.capabilities,
                "permissions": {
                    "network": s.network_access,
                    "filesystem_read": s.filesystem_read,
                    "filesystem_write": s.filesystem_write,
                    "credentials": s.credential_access,
                    "shell": s.shell_execution,
                },
            }
            for s in skills
        ],
        meta={"total": len(skills), "source": OPENCLAW_SOURCE_SLUG},
    )


@router.get("/openclaw/skills/{skill_id}", response_model=ApiResponse)
async def openclaw_skill_detail(skill_id: str):
    """Get details for a specific OpenClaw College skill."""
    async with get_openclaw_client() as client:
        skill = await client.get_skill_by_id(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
    return ApiResponse(
        data={
            "id": skill.id,
            "slug": skill.slug,
            "name": skill.name,
            "description": skill.short_description,
            "faculty": skill.faculty_id,
            "subcategory": skill.subcategory_id,
            "author": skill.author_name,
            "risk_tier": skill.risk_tier,
            "version": skill.version,
            "capabilities": skill.capabilities,
            "permissions": {
                "network": skill.network_access,
                "filesystem_read": skill.filesystem_read,
                "filesystem_write": skill.filesystem_write,
                "credentials": skill.credential_access,
                "shell": skill.shell_execution,
            },
        }
    )


# ── Bundles ───────────────────────────────────────────────────

@router.get("/openclaw/bundles", response_model=ApiResponse)
async def openclaw_bundles(faculty: str | None = None):
    """Browse skill bundles from OpenClaw College."""
    async with get_openclaw_client() as client:
        bundles = await client.get_bundles(faculty=faculty)
    return ApiResponse(
        data=[
            {
                "id": b.id,
                "name": b.name,
                "slug": b.slug,
                "description": b.description,
                "faculty": b.faculty_id,
                "skill_count": b.skill_count,
            }
            for b in bundles
        ],
        meta={"total": len(bundles), "source": OPENCLAW_SOURCE_SLUG},
    )


# ── Specializations ──────────────────────────────────────────

@router.get("/openclaw/specializations", response_model=ApiResponse)
async def openclaw_specializations():
    """Browse certification pathways from OpenClaw College."""
    async with get_openclaw_client() as client:
        specs = await client.get_specializations()
    return ApiResponse(
        data=[
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "description": s.description,
                "faculty": s.faculty_id,
                "badge_count": s.badge_count,
            }
            for s in specs
        ],
        meta={"total": len(specs), "source": OPENCLAW_SOURCE_SLUG},
    )
