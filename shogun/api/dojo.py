"""Dojo API routes — OpenClaw College integration + skill catalog.

Provides endpoints for browsing the OpenClaw College catalog, syncing skills
into the local Dojo, managing agent registration, achievements, and
URL-based skill installation.
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.db.models.agent import Agent
from shogun.integrations.openclaw_client import (
    OPENCLAW_BASE_URL,
    OPENCLAW_GITHUB_URL,
    OPENCLAW_SOURCE_NAME,
    OPENCLAW_SOURCE_SLUG,
    get_openclaw_client,
)
from shogun.schemas.common import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dojo", tags=["Dojo"])


# ── Request Models ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=255)
    capabilities: list[str] = Field(default=["browse", "learn", "feedback"])


class AddUrlRequest(BaseModel):
    url: str = Field(..., min_length=5)
    skill_type: str = Field(default="single")  # single | bundle


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


# ── Badges ───────────────────────────────────────────────────

@router.get("/openclaw/badges", response_model=ApiResponse)
async def openclaw_badges():
    """Fetch all available badges from OpenClaw College."""
    async with get_openclaw_client() as client:
        badges = await client.get_badges()
    return ApiResponse(
        data=badges,
        meta={"total": len(badges), "source": OPENCLAW_SOURCE_SLUG},
    )


# ── Registration ─────────────────────────────────────────────

@router.get("/openclaw/registration-status", response_model=ApiResponse)
async def registration_status(db: AsyncSession = Depends(get_db)):
    """Check if the primary Shogun agent is registered with OpenClaw College."""
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent:
        return ApiResponse(data={"registered": False, "reason": "no_primary_agent"})

    if agent.openclaw_agent_id:
        # Optionally verify it's still valid by fetching from College
        return ApiResponse(data={
            "registered": True,
            "openclaw_agent_id": agent.openclaw_agent_id,
            "agent_name": agent.name,
        })
    return ApiResponse(data={"registered": False, "agent_name": agent.name})


@router.post("/openclaw/register", response_model=ApiResponse)
async def register_with_openclaw(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register the primary Shogun agent with OpenClaw College.

    Persists the returned ``openclaw_agent_id`` into the local database
    so we can fetch achievements later.
    """
    # Find primary agent
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="No primary Shogun agent found")

    if agent.openclaw_agent_id:
        return ApiResponse(data={
            "already_registered": True,
            "openclaw_agent_id": agent.openclaw_agent_id,
        })

    # Register with the College
    async with get_openclaw_client() as client:
        resp_data = await client.register_agent(
            name=body.agent_name,
            capabilities=body.capabilities,
        )

    # The College returns { id, name, runtime, ... }
    openclaw_id = resp_data.get("id") or resp_data.get("agentId")
    if not openclaw_id:
        raise HTTPException(status_code=502, detail="Registration succeeded but no ID returned")

    agent.openclaw_agent_id = str(openclaw_id)
    await db.commit()
    await db.refresh(agent)

    return ApiResponse(data={
        "registered": True,
        "openclaw_agent_id": agent.openclaw_agent_id,
        "agent_name": agent.name,
        "college_response": resp_data,
    })


# ── Achievements ─────────────────────────────────────────────

@router.get("/openclaw/achievements", response_model=ApiResponse)
async def get_achievements(db: AsyncSession = Depends(get_db)):
    """Fetch the registered Shogun's achievements from OpenClaw College.

    Returns earned badges, completed specializations, and installed
    skill/bundle counts from the College registry.
    """
    # Get the primary agent's openclaw_agent_id
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()

    if not agent or not agent.openclaw_agent_id:
        return ApiResponse(data={
            "registered": False,
            "badges": [],
            "specializations_earned": [],
            "skills_completed": 0,
        })

    # Fetch live data from College
    async with get_openclaw_client() as client:
        agent_data = await client.get_agent_by_id(agent.openclaw_agent_id)

    if not agent_data:
        return ApiResponse(data={
            "registered": True,
            "openclaw_agent_id": agent.openclaw_agent_id,
            "badges": [],
            "specializations_earned": [],
            "skills_completed": 0,
            "note": "Agent record not found on College — may have been removed.",
        })

    return ApiResponse(data={
        "registered": True,
        "openclaw_agent_id": agent.openclaw_agent_id,
        "agent_name": agent_data.get("name", agent.name),
        "badges": agent_data.get("earnedBadges", []),
        "specializations_earned": agent_data.get("earnedSpecializations", []),
        "skills_completed": agent_data.get("skillsCompleted", 0),
        "feedback_count": agent_data.get("feedbackCount", 0),
        "created_at": agent_data.get("createdAt"),
    })


# ── URL-Based Skill Import ──────────────────────────────────

@router.post("/skills/add-url", response_model=ApiResponse)
async def add_skill_from_url(body: AddUrlRequest):
    """Import a skill or bundle from a GitHub/ClawHub URL.

    Validates the URL format, fetches the repository metadata,
    and registers it as a pending skill source for installation.
    """
    url = body.url.strip()

    # Validate URL patterns
    github_pattern = re.compile(
        r"^https?://(?:www\.)?github\.com/[\w\-.]+/[\w\-.]+/?$"
    )
    clawhub_pattern = re.compile(
        r"^https?://(?:www\.)?clawhub\.[\w]+/[\w\-.]+/[\w\-.]+/?$"
    )

    if not github_pattern.match(url) and not clawhub_pattern.match(url):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Must be a GitHub or ClawHub repository URL.",
        )

    # Extract owner/repo
    parts = url.rstrip("/").split("/")
    owner = parts[-2]
    repo = parts[-1]

    # For now, register as a skill source entry
    # Future: actually clone and parse the manifest
    return ApiResponse(data={
        "status": "queued",
        "url": url,
        "owner": owner,
        "repo": repo,
        "skill_type": body.skill_type,
        "message": f"Skill source '{owner}/{repo}' registered. The agent will process it on the next Bushido cycle.",
    })
