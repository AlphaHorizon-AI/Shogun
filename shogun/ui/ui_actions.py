"""UI Actions — async bridge between Gradio event handlers and the service layer.

Since Gradio 6.0 supports async event handlers natively, all public
functions here are async coroutines.  They manage their own DB sessions
and return plain Python types that Gradio can consume.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from shogun.db.engine import async_session_factory


# ═══════════════════════════════════════════════════════════════
#  SHOGUN CONFIG
# ═══════════════════════════════════════════════════════════════

async def load_shogun_config() -> dict[str, Any]:
    """Load the primary Shogun agent + its persona from the DB."""
    from shogun.db.models.agent import Agent
    from shogun.db.models.persona import Persona
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Find the primary Shogun agent
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        agent = result.scalars().first()

        # Load all personas for the dropdown
        persona_result = await session.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = persona_result.scalars().all()
        persona_names = [p.name for p in personas]

        if agent:
            current_persona = ""
            persona_obj = None
            if agent.persona_id:
                for p in personas:
                    if str(p.id) == str(agent.persona_id):
                        current_persona = p.name
                        persona_obj = p
                        break

            return {
                "exists": True,
                "agent_id": str(agent.id),
                "name": agent.name,
                "persona": current_persona,
                "tone": persona_obj.tone if persona_obj else "analytical",
                "autonomy": persona_obj.autonomy if persona_obj else "medium",
                "risk_tolerance": persona_obj.risk_tolerance if persona_obj else "low",
                "verbosity": persona_obj.verbosity if persona_obj else "medium",
                "persona_names": persona_names,
                "status": agent.status,
            }
        else:
            return {
                "exists": False,
                "agent_id": None,
                "name": "Primary Shogun",
                "persona": "",
                "tone": "analytical",
                "autonomy": "medium",
                "risk_tolerance": "low",
                "verbosity": "medium",
                "persona_names": persona_names,
                "status": "draft",
            }


async def save_shogun_config(
    name: str,
    persona_name: str,
    tone: str,
    autonomy: int,
    risk_tolerance: str,
    verbosity: str,
) -> str:
    """Save the primary Shogun agent configuration."""
    from shogun.db.models.agent import Agent
    from shogun.db.models.persona import Persona
    from sqlalchemy import select

    async with async_session_factory() as session:
        # Find persona by name
        persona_id = None
        if persona_name:
            p_result = await session.execute(
                select(Persona).where(Persona.name == persona_name)
            )
            persona = p_result.scalars().first()
            if persona:
                persona_id = persona.id
                # Update persona attributes
                persona.tone = tone
                level_map = {0: "low", 10: "low", 20: "low", 30: "low",
                             40: "medium", 50: "medium", 60: "medium",
                             70: "high", 80: "high", 90: "high", 100: "high"}
                persona.autonomy = level_map.get(int(autonomy), "medium")
                persona.risk_tolerance = risk_tolerance
                persona.verbosity = verbosity

        # Find or create primary Shogun agent
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        agent = result.scalars().first()

        if agent:
            agent.name = name
            agent.persona_id = persona_id
            agent.status = "active"
        else:
            agent = Agent(
                id=uuid.uuid4(),
                agent_type="shogun",
                name=name,
                slug="primary-shogun",
                status="active",
                persona_id=persona_id,
                is_primary=True,
                memory_scope={"episodic": True, "semantic": True, "procedural": True, "persona": True, "skills": True},
                spawn_policy="manual",
                tags=[],
                created_by="operator",
                updated_by="operator",
            )
            session.add(agent)

        await session.commit()
        return f"✅ Shogun '{name}' saved successfully."


# ═══════════════════════════════════════════════════════════════
#  SAMURAI MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def list_samurai() -> list[list[str]]:
    """Return all Samurai agents as rows for a Gradio DataFrame."""
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "samurai",
                Agent.is_deleted == False,
            )
        )
        agents = result.scalars().all()
        return [[a.name, a.slug, a.status, str(a.id)] for a in agents]


async def create_samurai(
    name: str, role: str, persona: str, security_tier: str, spawn_rule: str
) -> str:
    """Create a new Samurai agent."""
    from shogun.db.models.agent import Agent
    from shogun.db.models.samurai_profile import SamuraiProfile
    from sqlalchemy import select

    if not name or not name.strip():
        return "⚠️ Name is required."

    slug = name.lower().replace(" ", "-").replace("_", "-")

    async with async_session_factory() as session:
        # Check for duplicate slug
        existing = await session.execute(
            select(Agent).where(Agent.slug == slug)
        )
        if existing.scalars().first():
            return f"⚠️ An agent with slug '{slug}' already exists."

        agent = Agent(
            id=uuid.uuid4(),
            agent_type="samurai",
            name=name.strip(),
            slug=slug,
            status="active",
            spawn_policy=spawn_rule or "manual",
            is_primary=False,
            memory_scope={"episodic": True, "semantic": True, "procedural": True, "persona": True, "skills": True},
            tags=[],
            created_by="operator",
            updated_by="operator",
        )
        session.add(agent)
        await session.flush()

        profile = SamuraiProfile(
            id=uuid.uuid4(),
            agent_id=agent.id,
            role=role or "research",
            specializations=[],
            allowed_task_types=[],
            blocked_task_types=[],
            max_parallel_jobs=2,
            auto_spawnable=spawn_rule == "auto",
            created_by="operator",
            updated_by="operator",
        )
        session.add(profile)
        await session.commit()

        return f"✅ Samurai '{name}' created successfully."


async def delete_samurai(agent_id_str: str) -> str:
    """Soft-delete a Samurai agent."""
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    if not agent_id_str:
        return "⚠️ No Samurai selected."

    async with async_session_factory() as session:
        result = await session.execute(
            select(Agent).where(Agent.id == uuid.UUID(agent_id_str))
        )
        agent = result.scalars().first()
        if not agent:
            return "⚠️ Samurai not found."

        agent.is_deleted = True
        agent.deleted_at = datetime.now(timezone.utc)
        await session.commit()
        return f"✅ Samurai '{agent.name}' deleted."


async def suspend_samurai(agent_id_str: str) -> str:
    """Suspend/resume a Samurai agent."""
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    if not agent_id_str:
        return "⚠️ No Samurai selected."

    async with async_session_factory() as session:
        result = await session.execute(
            select(Agent).where(Agent.id == uuid.UUID(agent_id_str))
        )
        agent = result.scalars().first()
        if not agent:
            return "⚠️ Samurai not found."

        if agent.status == "suspended":
            agent.status = "active"
            msg = f"✅ Samurai '{agent.name}' resumed."
        else:
            agent.status = "suspended"
            msg = f"⏸ Samurai '{agent.name}' suspended."

        await session.commit()
        return msg


# ═══════════════════════════════════════════════════════════════
#  OVERVIEW — LIVE DATA
# ═══════════════════════════════════════════════════════════════

async def load_overview() -> dict[str, Any]:
    """Load system health and active agent data."""
    from shogun.db.models.agent import Agent
    from sqlalchemy import select, func

    async with async_session_factory() as session:
        # Count samurai
        agent_count = await session.execute(
            select(func.count()).select_from(Agent).where(
                Agent.is_deleted == False, Agent.agent_type == "samurai"
            )
        )
        samurai_count = agent_count.scalar() or 0

        # Active samurai list
        samurai_result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "samurai",
                Agent.is_deleted == False,
            )
        )
        samurai_list = samurai_result.scalars().all()
        samurai_rows = [
            [a.name, a.slug, a.status, "—", str(a.last_heartbeat_at or "—")]
            for a in samurai_list
        ]

        # Shogun profile
        shogun_result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        shogun = shogun_result.scalars().first()

        shogun_profile = [
            ["Persona", shogun.name if shogun else "Not configured"],
            ["Status", shogun.status if shogun else "Not configured"],
            ["Spawn Policy", shogun.spawn_policy if shogun else "—"],
            ["Autonomy", "—"],
        ]

        health = [
            ["Runtime", "🟢 Online"],
            ["Database", "🟢 Healthy"],
            ["Qdrant", "🟡 Pending"],
            ["Telegram", "⚪ Not Configured"],
        ]

        security = [
            ["Tier", "Guarded"],
            ["File Access", "Scoped"],
            ["Network", "Allowlist"],
            ["Shell", "Disabled"],
        ]

        return {
            "samurai_count": samurai_count,
            "samurai_rows": samurai_rows,
            "health": health,
            "shogun_profile": shogun_profile,
            "security": security,
        }


# ═══════════════════════════════════════════════════════════════
#  SECURITY (TORII)
# ═══════════════════════════════════════════════════════════════

async def load_security_policies() -> list[list[str]]:
    """Load all security policies for the Torii page."""
    from shogun.db.models.security_policy import SecurityPolicy
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(SecurityPolicy))
        policies = result.scalars().all()
        rows = []
        for p in policies:
            perms = p.permissions or {}
            rows.append([
                p.name,
                p.tier,
                perms.get("filesystem", "—"),
                perms.get("network", "—"),
                perms.get("shell", "—"),
            ])
        return rows


# ═══════════════════════════════════════════════════════════════
#  KATANA — PROVIDERS
# ═══════════════════════════════════════════════════════════════

async def list_providers() -> list[list[str]]:
    """List all model providers."""
    from shogun.db.models.model_provider import ModelProvider
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(ModelProvider))
        providers = result.scalars().all()
        return [[p.name, p.provider_type, p.status, "—", "—"] for p in providers]
