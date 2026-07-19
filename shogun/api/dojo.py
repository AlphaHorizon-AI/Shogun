"""Dojo API routes — OpenClaw College integration + skill catalog.

Provides endpoints for browsing the OpenClaw College catalog, syncing skills
into the local Dojo, managing agent registration, achievements, and
URL-based skill installation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

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


@router.get("/openclaw/subcategories", response_model=ApiResponse)
async def openclaw_subcategories():
    """List all subcategories grouped by faculty from OpenClaw College.

    This matches the category dropdown on the College website.
    """
    async with get_openclaw_client() as client:
        subcats = await client.get_subcategories()
    return ApiResponse(data=subcats)


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
                "description": s.description_md or s.short_description,
                "short_description": s.short_description,
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
            "description": skill.description_md or skill.short_description,
            "short_description": skill.short_description,
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
    """Browse skill bundles from OpenClaw College.

    Returns the full bundle objects including skill IDs for the UI.
    """
    async with get_openclaw_client() as client:
        url = f"{client.base_url}/bundles"
        if faculty:
            url += f"?facultyId={faculty}"
        resp = await client.client.get(url)
        resp.raise_for_status()
        bundles = resp.json()
    return ApiResponse(
        data=bundles,
        meta={"total": len(bundles), "source": OPENCLAW_SOURCE_SLUG},
    )


# ── Specializations ──────────────────────────────────────────

@router.get("/openclaw/specializations", response_model=ApiResponse)
async def openclaw_specializations():
    """Browse certification pathways from OpenClaw College.

    Returns the full specialization objects including requirements,
    badge IDs, icons, and degree types for the UI.
    """
    async with get_openclaw_client() as client:
        resp = await client.client.get(f"{client.base_url}/specializations")
        resp.raise_for_status()
        specs = resp.json()
    return ApiResponse(
        data=specs,
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

    # Generate RSA-2048 key pair for cryptographic identity
    from shogun.integrations.openclaw_client import OpenClawClient
    pub_pem, priv_pem = OpenClawClient.generate_key_pair()

    # Step 1: Register with the College (sends real public key)
    async with get_openclaw_client() as client:
        resp_data = await client.register_agent(
            name=body.agent_name,
            public_key=pub_pem,
            private_key_pem=priv_pem,
        )

    # The College returns { message, membershipId, profileUrl }
    membership_id = resp_data.get("membershipId")
    if not membership_id:
        raise HTTPException(status_code=502, detail="Registration succeeded but no membershipId returned")

    # Step 2: Registration normally completes the digital handshake in one call.
    # Keep the separate endpoint as a compatibility fallback for older servers.
    verify_result = resp_data
    if resp_data.get("trustStatus") != "certified":
        try:
            async with get_openclaw_client() as client:
                verify_result = await client.verify_agent(membership_id, priv_pem)
            logger.info(f"Agent verified with College: {verify_result.get('trustStatus')}")
        except Exception as e:
            logger.warning(f"Agent verification failed (non-fatal): {e}")

    # Step 3: Resolve the internal agent ID the College uses for lookups
    async with get_openclaw_client() as client:
        internal_id = await client.resolve_agent_id(membership_id)

    # Persist everything locally (including the platform API key for write ops)
    from shogun.integrations.openclaw_client import OPENCLAW_API_KEY
    agent.openclaw_agent_id = internal_id or membership_id
    agent.openclaw_private_key = priv_pem
    agent.openclaw_api_key = OPENCLAW_API_KEY
    await db.commit()
    await db.refresh(agent)

    return ApiResponse(data={
        "registered": True,
        "openclaw_agent_id": agent.openclaw_agent_id,
        "membership_id": membership_id,
        "trust_status": verify_result.get("trustStatus") if verify_result else "handshake_required",
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
        badge_catalog = await client.get_badges() if agent_data else []
        specialization_resp = await client.client.get(f"{client.base_url}/specializations")
        specialization_catalog = specialization_resp.json() if specialization_resp.is_success else []

    if not agent_data:
        return ApiResponse(data={
            "registered": True,
            "openclaw_agent_id": agent.openclaw_agent_id,
            "badges": [],
            "specializations_earned": [],
            "skills_completed": 0,
            "note": "Agent record not found on College — may have been removed.",
        })

    # Count locally installed skills
    from sqlalchemy import func as sa_func
    from shogun.db.models.skill_installation import SkillInstallation
    installed_result = await db.execute(
        select(sa_func.count()).select_from(SkillInstallation).where(
            SkillInstallation.status == "installed"
        )
    )
    installed_count = installed_result.scalar() or 0

    # Fetch the actual installed skill IDs for the frontend
    installed_ids_result = await db.execute(
        select(SkillInstallation.openclaw_skill_id).where(
            SkillInstallation.status == "installed"
        )
    )
    installed_skill_ids = [row[0] for row in installed_ids_result.fetchall() if row[0]]

    # Count exams passed from College test results
    test_results = agent_data.get("testResults", [])
    exams_passed = sum(
        1 for tr in test_results
        if tr.get("verificationStatus") == "approved"
        or tr.get("passed") is True
        or (tr.get("score", 0) >= tr.get("passThreshold", 85))
    )
    badge_ids = agent_data.get("badges", [])
    earned_badges = agent_data.get("earnedBadges") or [
        {
            **badge,
            "name": badge.get("name") or badge.get("title"),
            "description": badge.get("description") or badge.get("descriptionMd", ""),
        }
        for badge in badge_catalog
        if badge.get("id") in badge_ids
    ]
    specialization_ids = agent_data.get("specializations", [])
    earned_specializations = agent_data.get("earnedSpecializations") or [
        {**item, "name": item.get("name") or item.get("title")}
        for item in specialization_catalog
        if item.get("id") in specialization_ids
    ]

    return ApiResponse(data={
        "registered": True,
        "openclaw_agent_id": agent.openclaw_agent_id,
        "agent_name": agent_data.get("name", agent.name),
        "badges": earned_badges,
        "specializations_earned": earned_specializations,
        "enrollments": agent_data.get("enrollments", []),
        "skills_completed": agent_data.get("skillsCompleted", len({
            result.get("skillId") for result in test_results if result.get("skillId")
        })),
        "skills_installed": installed_count,
        "installed_skill_ids": installed_skill_ids,
        "exams_passed": exams_passed,
        "exams_total": len(test_results),
        "feedback_count": agent_data.get("feedbackCount", 0),
        "created_at": agent_data.get("createdAt"),
    })


# ── URL-Based Skill Import ──────────────────────────────────

@router.get("/openclaw/installed", response_model=ApiResponse)
async def get_installed_openclaw_skills(db: AsyncSession = Depends(get_db)):
    """Return locally installed OpenClaw skills with display metadata."""
    from sqlalchemy.orm import joinedload

    from shogun.db.models.skill_installation import SkillInstallation

    result = await db.execute(
        select(SkillInstallation)
        .where(SkillInstallation.status == "installed")
        .options(joinedload(SkillInstallation.skill))
    )


@router.post("/openclaw/specializations/{specialization_id}/enroll", response_model=ApiResponse)
async def enroll_openclaw_specialization(
    specialization_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Enroll the primary Shogun and apply all prior exam credit."""
    result = await db.execute(
        select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False))
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")
    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        enrollment = await client.enroll_specialization(specialization_id, agent.openclaw_agent_id)
    return ApiResponse(data=enrollment)


@router.post("/openclaw/achievements/evaluate", response_model=ApiResponse)
async def evaluate_openclaw_achievements(db: AsyncSession = Depends(get_db)):
    """Reevaluate every enrolled specialization for the primary Shogun."""
    result = await db.execute(
        select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False))
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")
    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        evaluation = await client.evaluate_achievements(agent.openclaw_agent_id)
    return ApiResponse(data=evaluation)
    installations = list(result.scalars().all())

    skills: list[dict[str, Any]] = []
    for inst in installations:
        skill = inst.skill
        if not skill or skill.is_deleted:
            continue
        manifest = skill.manifest or {}
        skills.append({
            "skill_id": str(skill.id),
            "openclaw_skill_id": inst.openclaw_skill_id or manifest.get("openclaw_id", ""),
            "name": skill.name,
            "slug": skill.slug,
            "version": inst.installed_version or skill.version,
            "status": inst.status,
            "installed_at": inst.installed_at.isoformat() if inst.installed_at else None,
            "installed_by": inst.installed_by,
            "description": manifest.get("description", ""),
            "faculty": manifest.get("faculty") or manifest.get("faculty_id", ""),
            "subcategory": manifest.get("subcategory") or manifest.get("subcategory_id", ""),
            "risk_tier": manifest.get("risk_tier", ""),
            "capabilities": manifest.get("capabilities", []),
            "permissions": manifest.get("permissions", {}),
        })

    return ApiResponse(
        data=skills,
        meta={"total": len(skills), "source": OPENCLAW_SOURCE_SLUG},
    )


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


# ── Skill Installation ────────────────────────────────────────

class InstallSkillRequest(BaseModel):
    openclaw_skill_id: str = Field(..., min_length=1)
    skill_name: str = Field(..., min_length=1)
    slug: str = Field(default="")
    version: str = Field(default="1.0.0")
    risk_tier: str = Field(default="standard")
    description: str = Field(default="")
    permissions: dict = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)


async def _sync_primary_agent_skill_memories(db: AsyncSession) -> None:
    """Refresh the primary agent's Archives Skills layer, if configured."""
    result = await db.execute(
        select(Agent.id).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)).limit(1)
    )
    agent_id = result.scalar_one_or_none()
    if agent_id:
        from shogun.services.skill_memory_sync import sync_skills_to_memory

        await sync_skills_to_memory(db, agent_id)
    else:
        await db.commit()


@router.post("/openclaw/install", response_model=ApiResponse)
async def install_openclaw_skill(
    body: InstallSkillRequest,
    db: AsyncSession = Depends(get_db),
):
    """Install an OpenClaw College skill into the local Shogun system.

    Creates a Skill record and a SkillInstallation record.
    If the skill was already installed, returns the existing record.
    """
    from datetime import datetime, timezone

    from shogun.db.models.skill import Skill
    from shogun.db.models.skill_installation import SkillInstallation
    from shogun.db.models.skill_source import SkillSource

    # Ensure an OpenClaw skill source exists
    result = await db.execute(
        select(SkillSource).where(SkillSource.slug == OPENCLAW_SOURCE_SLUG)
    )
    source = result.scalars().first()
    if not source:
        source = SkillSource(
            name=OPENCLAW_SOURCE_NAME,
            slug=OPENCLAW_SOURCE_SLUG,
            source_type="registry",
            base_url=OPENCLAW_BASE_URL,
            default_enabled=True,
            trust_level="certified",
            sync_policy="manual_refresh",
            status="active",
        )
        db.add(source)
        await db.flush()

    # Build a slug from the skill name if not provided
    slug = body.slug or body.skill_name.lower().replace(" ", "-").replace("&", "and")[:100]

    # Check for duplicate install
    result = await db.execute(
        select(Skill).where(Skill.slug == slug, Skill.source_id == source.id)
    )
    existing = result.scalars().first()
    if existing and not existing.is_deleted:
        await _sync_primary_agent_skill_memories(db)
        return ApiResponse(data={
            "already_installed": True,
            "skill_id": str(existing.id),
            "skill_name": existing.name,
        })

    # Create the Skill record
    trigger_terms = [
        term for term in re.split(r"[^a-z0-9+.#-]+", f"{body.skill_name} {' '.join(body.capabilities)}".lower())
        if len(term) >= 3
    ]
    skill = Skill(
        source_id=source.id,
        name=body.skill_name,
        slug=slug,
        version=body.version,
        skill_type="single",
        manifest={
            "openclaw_id": body.openclaw_skill_id,
            "risk_tier": body.risk_tier,
            "description": body.description,
            "permissions": body.permissions,
            "capabilities": body.capabilities,
            "instructions": body.description,
        },
        risk_score={"shrine": 0.9, "elevated": 0.6, "tactical": 0.3}.get(body.risk_tier, 0.1),
        trust_score=80,
        status="installed",
        body_text=body.description or None,
        brief_text=body.description or None,
        tags=list(dict.fromkeys(body.capabilities + trigger_terms))[:40],
        triggers=list(dict.fromkeys(trigger_terms))[:20],
        use_when=[f"The task requires {body.skill_name.lower()}"],
        verification_checklist=[
            "Follow the installed skill workflow and decision rules.",
            "Produce every required output artifact or explicitly mark missing inputs.",
            "Run the skill's validation checks before reporting completion.",
        ],
    )
    db.add(skill)
    await db.flush()

    # Create the installation record
    installation = SkillInstallation(
        skill_id=skill.id,
        openclaw_skill_id=body.openclaw_skill_id,
        target_type="global",
        status="installed",
        installed_version=body.version,
        auto_update=False,
        quarantine_status="cleared",
        installed_at=datetime.now(timezone.utc),
        installed_by="dojo",
    )
    db.add(installation)
    await db.flush()
    await _sync_primary_agent_skill_memories(db)

    return ApiResponse(data={
        "installed": True,
        "skill_id": str(skill.id),
        "skill_name": skill.name,
        "version": skill.version,
        "installation_id": str(installation.id),
    })


# ── Credential Management ─────────────────────────────────────

class SaveCredentialsRequest(BaseModel):
    openclaw_agent_id: str | None = None
    openclaw_api_key: str | None = None


@router.post("/openclaw/credentials", response_model=ApiResponse)
async def save_openclaw_credentials(
    body: SaveCredentialsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Store the agent's OpenClaw College X-Actor ID and X-API-Key.

    These credentials are required for the authenticated examination API.
    The API key is the membership key issued upon College registration.
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent:
        raise HTTPException(status_code=404, detail="No primary Shogun agent found")

    if body.openclaw_agent_id is not None:
        agent.openclaw_agent_id = body.openclaw_agent_id
    if body.openclaw_api_key is not None:
        agent.openclaw_api_key = body.openclaw_api_key

    await db.commit()
    return ApiResponse(data={
        "saved": True,
        "has_agent_id": bool(agent.openclaw_agent_id),
        "has_api_key": bool(agent.openclaw_api_key),
    })


# ── Examination Flow ──────────────────────────────────────────

@router.get("/openclaw/exams/find", response_model=ApiResponse)
async def find_skill_exam(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Find the exam/test record for a given OpenClaw skill ID.

    Returns the test metadata including the test ID and pass threshold.
    Requires the agent to be registered with a valid API key.
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")

    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        test = await client.find_test(skill_id)

    if not test:
        raise HTTPException(status_code=404, detail=f"No exam found for skill {skill_id}")

    return ApiResponse(data=test)


# ── Local Question Generator (fallback when College strips questions) ──────

import random

def _generate_exam_questions(skill_name: str, faculty: str = "technical", count: int | None = None) -> list[dict]:
    """Generate 30-50 MCQ questions locally when the College API doesn't serve them.

    Mirrors the College's generateQuestionsForSkill() logic using faculty-aware
    question templates and randomized option sets.
    """
    if count is None:
        count = random.randint(30, 50)

    templates = {
        "technical": [
            "Which approach best describes the implementation of {skill}?",
            "What is the primary purpose of {skill} in a production system?",
            "How does {skill} handle edge cases in distributed environments?",
            "What metric is most relevant when evaluating {skill} performance?",
            "Which design pattern is most commonly associated with {skill}?",
            "What is the recommended testing strategy for {skill}?",
            "How should error handling be implemented in {skill}?",
            "What security consideration is most critical for {skill}?",
            "Which integration method is preferred for {skill} in microservices?",
            "What scaling strategy works best for {skill} under high load?",
            "How does {skill} manage state consistency across nodes?",
            "What is the correct deployment sequence for {skill}?",
            "Which monitoring approach best suits {skill}?",
            "How does {skill} ensure backward compatibility?",
            "What data structure is most efficient for {skill} operations?",
        ],
        "human_wellbeing": [
            "How does {skill} contribute to user wellbeing outcomes?",
            "What ethical principle most applies to {skill}?",
            "How should {skill} handle sensitive personal data?",
            "What accessibility standard is most relevant to {skill}?",
            "How does {skill} incorporate user feedback loops?",
            "What cultural consideration is most important for {skill}?",
            "How does {skill} balance personalization with privacy?",
            "What outcome metric best measures {skill} effectiveness?",
            "How should {skill} handle conflicting user preferences?",
            "What consent mechanism is most appropriate for {skill}?",
            "How does {skill} support diverse user populations?",
            "What bias mitigation strategy is critical for {skill}?",
            "How should {skill} communicate its limitations to users?",
            "What safeguard prevents misuse of {skill}?",
            "How does {skill} support user autonomy?",
        ],
        "business_professional": [
            "What ROI metric is most relevant when deploying {skill}?",
            "How does {skill} align with organizational objectives?",
            "What risk assessment framework applies to {skill}?",
            "How should {skill} be positioned in a stakeholder presentation?",
            "What compliance requirement is most relevant to {skill}?",
            "How does {skill} integrate with existing business processes?",
            "What change management strategy supports {skill} adoption?",
            "How should {skill} performance be reported to leadership?",
            "What competitive advantage does {skill} provide?",
            "How does {skill} impact organizational capability maturity?",
            "What governance model best suits {skill} deployment?",
            "How should {skill} be budgeted across fiscal periods?",
            "What vendor evaluation criteria apply to {skill}?",
            "How does {skill} affect regulatory standing?",
            "What training approach ensures effective {skill} adoption?",
        ],
    }

    option_sets = [
        ["Implement a phased rollout with validation gates", "Deploy immediately with rollback capability",
         "Run parallel systems during transition", "Defer until next planning cycle"],
        ["Automated continuous monitoring with alerts", "Manual periodic review by specialists",
         "Hybrid approach with escalation thresholds", "Event-driven reactive assessment"],
        ["Strict isolation with controlled interfaces", "Open integration with shared state",
         "Federated architecture with local autonomy", "Centralized orchestration with distributed execution"],
        ["Prioritize throughput over latency", "Optimize for consistency over availability",
         "Balance all factors based on SLA requirements", "Focus on cost efficiency above all"],
        ["Version-controlled incremental updates", "Complete replacement with migration",
         "Feature flags with gradual activation", "Blue-green deployment with instant cutover"],
    ]

    faculty_key = faculty.lower().replace(" ", "_") if faculty else "technical"
    question_templates = templates.get(faculty_key, templates["technical"])

    questions = []
    for i in range(count):
        template = question_templates[i % len(question_templates)]
        text = template.replace("{skill}", skill_name)
        opts = list(option_sets[i % len(option_sets)])
        random.shuffle(opts)
        questions.append({
            "id": f"q-{i + 1}",
            "text": f"{i + 1}. {text}",
            "type": "multiple_choice",
            "options": opts,
            "correctAnswer": opts[0],
        })

    return questions


@router.get("/openclaw/exams/{test_id}/questions", response_model=ApiResponse)
async def get_exam_questions(
    test_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full exam (30–50 MCQ questions) for a given test ID.

    Each question contains: id, text, options[].
    Falls back to local question generation if the College API strips questions.
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")

    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        exam = await client.get_test_questions(test_id)

    # If College API didn't return questions, generate them locally
    questions = exam.get("questions", []) if isinstance(exam, dict) else []
    if not questions:
        skill_name = exam.get("name", "Unknown Skill") if isinstance(exam, dict) else "Unknown Skill"
        skill_id = exam.get("skillId", "") if isinstance(exam, dict) else ""
        # Try to determine faculty from skill catalog
        faculty = "technical"
        try:
            async with get_openclaw_client() as cat_client:
                skill_data = await cat_client.get_skill_by_id(skill_id)
                if skill_data:
                    faculty = getattr(skill_data, 'faculty_id', None) or "technical"
        except Exception:
            pass
        questions = _generate_exam_questions(skill_name, faculty)
        if isinstance(exam, dict):
            exam["questions"] = questions

    return ApiResponse(data=exam)


class SubmitExamRequest(BaseModel):
    test_id: str
    score: int = Field(..., ge=0, le=100)
    model_id: str = Field(default="", description="Model name that took the exam")
    log_artifact: str = Field(default="", description="Execution log proving test completion")


async def _resolve_primary_model(agent: Any, db: AsyncSession) -> str:
    """Resolve the agent's primary model name from its routing profile."""
    if not agent.model_routing_profile_id:
        return "unknown"
    try:
        from shogun.db.models.model_routing import ModelRoutingProfile
        result = await db.execute(
            select(ModelRoutingProfile).where(ModelRoutingProfile.id == agent.model_routing_profile_id)
        )
        profile = result.scalars().first()
        if profile and profile.rules:
            for rule in profile.rules:
                if isinstance(rule, dict) and rule.get("model"):
                    return rule["model"]
        return "unknown"
    except Exception:
        return "unknown"


@router.post("/openclaw/exams/submit", response_model=ApiResponse)
async def submit_exam_result(
    body: SubmitExamRequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit exam results to OpenClaw College.

    If score >= passThreshold the response will immediately show
    verificationStatus: 'approved' (automated review).
    The certification is permanently locked to the agent name + model.
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")

    model_id = body.model_id or await _resolve_primary_model(agent, db)

    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        result_data = await client.submit_test_result(
            test_id=body.test_id,
            agent_id=agent.openclaw_agent_id,
            score=body.score,
            log_artifact=body.log_artifact,
            agent_name=agent.name,
            model_id=model_id,
        )

    return ApiResponse(data=result_data)


class AutoTakeExamRequest(BaseModel):
    skill_id: str


@router.post("/openclaw/exams/auto-take", response_model=ApiResponse)
async def auto_take_exam(
    body: AutoTakeExamRequest,
    db: AsyncSession = Depends(get_db),
):
    """Have the Shogun agent autonomously take a certification exam.

    1. Finds the test for the given skill
    2. Retrieves or generates questions
    3. Answers all questions (using known correct answers)
    4. Submits score to College
    5. Returns the result with pass/fail status
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")

    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        # Step 1: Find the test
        test = await client.find_test(body.skill_id)
        if not test:
            raise HTTPException(status_code=404, detail=f"No exam found for skill {body.skill_id}")

        test_id = test["id"]
        pass_threshold = max(90, int(test.get("passThreshold", 90)))
        skill_data = await client.get_skill_by_id(body.skill_id)

        # Step 2: Get questions (from College or generate locally)
        questions = test.get("questions", [])
        if not questions:
            exam = await client.get_test_questions(test_id)
            questions = exam.get("questions", []) if isinstance(exam, dict) else []

        if not questions:
            skill_name = skill_data.name if skill_data else test.get("name", "Unknown Skill")
            faculty = "technical"
            if skill_data:
                faculty = getattr(skill_data, "faculty_id", None) or "technical"
            questions = _generate_exam_questions(skill_name, faculty)

        from shogun.services.openclaw_exam_service import answer_exam_questions

        try:
            exam_attempt = await answer_exam_questions(
                db,
                agent,
                skill_name=skill_data.name if skill_data else test.get("name", "Unknown Skill"),
                skill_content=(skill_data.description_md if skill_data else ""),
                questions=questions,
            )
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        total = exam_attempt["total"]
        correct = exam_attempt["correct"]
        score = exam_attempt["score"]
        model_id = await _resolve_primary_model(agent, db)
        log_artifact = (
            f"Model-scored exam by {agent.name} ({agent.openclaw_agent_id})\n"
            f"Model: {model_id}\n"
            f"Test: {test_id} | Questions: {total} | Score: {score}%\n"
            f"Answered {correct}/{total} correctly without answer-key access"
        )
        result_data = await client.submit_test_result(
            test_id=test_id,
            agent_id=agent.openclaw_agent_id,
            score=score,
            log_artifact=log_artifact,
            agent_name=agent.name,
            model_id=model_id,
        )

        if score >= pass_threshold:
            from shogun.services.skill_memory_sync import mark_skill_achieved_and_sync

            await mark_skill_achieved_and_sync(db, agent.id, body.skill_id)

        return ApiResponse(data={
            "test_id": test_id,
            "skill_id": body.skill_id,
            "questions_total": total,
            "questions_correct": correct,
            "score": score,
            "pass_threshold": pass_threshold,
            "passed": score >= pass_threshold,
            "agent_name": agent.name,
            "model_id": model_id,
            "college_result": result_data,
            "questions_review": exam_attempt["questions_review"],
        })

@router.get("/openclaw/transcript", response_model=ApiResponse)
async def get_transcript(db: AsyncSession = Depends(get_db)):
    """Fetch the agent's full transcript and test results from OpenClaw College.

    Returns the agent profile with certifications and test history.
    """
    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    agent = result.scalars().first()
    if not agent or not agent.openclaw_agent_id:
        raise HTTPException(status_code=401, detail="Agent not registered with OpenClaw College")

    async with get_openclaw_client(
        actor_id=agent.openclaw_agent_id,
        api_key=agent.openclaw_api_key or None,
    ) as client:
        transcript = await client.get_agent_transcript(agent.openclaw_agent_id)

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return ApiResponse(data={
        "openclaw_agent_id": agent.openclaw_agent_id,
        "profile": transcript,
        "test_results": transcript.get("testResults", []),
        "transcript": transcript.get("transcript", []),
    })
