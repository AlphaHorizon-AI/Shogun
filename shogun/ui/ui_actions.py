"""UI Actions — bridge between Gradio event handlers and the service layer.

When Gradio is mounted on FastAPI via mount_gradio_app(), event handlers
run in worker threads.  We use asyncio.run() in each sync handler to
create a fresh event loop per call.  This is reliable across all Gradio
deployment modes.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from shogun.db.engine import async_session_factory


def _run(coro):
    """Run an async coroutine in a new event loop (safe for threaded Gradio)."""
    return asyncio.run(coro)


# ═══════════════════════════════════════════════════════════════
#  SHOGUN CONFIG
# ═══════════════════════════════════════════════════════════════

async def _load_shogun_config() -> dict[str, Any]:
    from shogun.db.models.agent import Agent
    from shogun.db.models.persona import Persona
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        agent = result.scalars().first()

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


def load_shogun_config() -> dict[str, Any]:
    return _run(_load_shogun_config())


async def _save_shogun_config(
    name: str, persona_name: str, tone: str,
    autonomy: int, risk_tolerance: str, verbosity: str,
) -> str:
    from shogun.db.models.agent import Agent
    from shogun.db.models.persona import Persona
    from sqlalchemy import select

    async with async_session_factory() as session:
        persona_id = None
        if persona_name:
            p_result = await session.execute(
                select(Persona).where(Persona.name == persona_name)
            )
            persona = p_result.scalars().first()
            if persona:
                persona_id = persona.id
                persona.tone = tone
                level_map = {0: "low", 10: "low", 20: "low", 30: "low",
                             40: "medium", 50: "medium", 60: "medium",
                             70: "high", 80: "high", 90: "high", 100: "high"}
                persona.autonomy = level_map.get(int(autonomy), "medium")
                persona.risk_tolerance = risk_tolerance
                persona.verbosity = verbosity

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
                id=uuid.uuid4(), agent_type="shogun", name=name,
                slug="primary-shogun", status="active", persona_id=persona_id,
                is_primary=True,
                memory_scope={"episodic": True, "semantic": True, "procedural": True, "persona": True, "skills": True},
                spawn_policy="manual", tags=[],
                created_by="operator", updated_by="operator",
            )
            session.add(agent)

        await session.commit()
        return f"✅ Shogun '{name}' saved successfully."


def save_shogun_config(name, persona_name, tone, autonomy, risk_tolerance, verbosity) -> str:
    return _run(_save_shogun_config(name, persona_name, tone, autonomy, risk_tolerance, verbosity))


# ═══════════════════════════════════════════════════════════════
#  SAMURAI MANAGEMENT
# ═══════════════════════════════════════════════════════════════

async def _list_samurai() -> list[list[str]]:
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


def list_samurai() -> list[list[str]]:
    return _run(_list_samurai())


async def _create_samurai(
    name: str, role: str, persona: str, security_tier: str, spawn_rule: str
) -> str:
    from shogun.db.models.agent import Agent
    from shogun.db.models.samurai_profile import SamuraiProfile
    from sqlalchemy import select

    if not name or not name.strip():
        return "⚠️ Name is required."

    slug = name.lower().replace(" ", "-").replace("_", "-")

    async with async_session_factory() as session:
        existing = await session.execute(
            select(Agent).where(Agent.slug == slug)
        )
        if existing.scalars().first():
            return f"⚠️ An agent with slug '{slug}' already exists."

        agent = Agent(
            id=uuid.uuid4(), agent_type="samurai", name=name.strip(),
            slug=slug, status="active", spawn_policy=spawn_rule or "manual",
            is_primary=False,
            memory_scope={"episodic": True, "semantic": True, "procedural": True, "persona": True, "skills": True},
            tags=[], created_by="operator", updated_by="operator",
        )
        session.add(agent)
        await session.flush()

        profile = SamuraiProfile(
            id=uuid.uuid4(), agent_id=agent.id,
            role=role or "research", specializations=[],
            allowed_task_types=[], blocked_task_types=[],
            max_parallel_jobs=2, auto_spawnable=spawn_rule == "auto",
            created_by="operator", updated_by="operator",
        )
        session.add(profile)
        await session.commit()

        return f"✅ Samurai '{name}' created successfully."


def create_samurai(name, role, persona, security_tier, spawn_rule) -> str:
    return _run(_create_samurai(name, role, persona, security_tier, spawn_rule))


async def _delete_samurai(agent_id_str: str) -> str:
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


def delete_samurai(agent_id_str: str) -> str:
    return _run(_delete_samurai(agent_id_str))


async def _suspend_samurai(agent_id_str: str) -> str:
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


def suspend_samurai(agent_id_str: str) -> str:
    return _run(_suspend_samurai(agent_id_str))


# ═══════════════════════════════════════════════════════════════
#  OVERVIEW — LIVE DATA
# ═══════════════════════════════════════════════════════════════

async def _load_overview() -> dict[str, Any]:
    from shogun.db.models.agent import Agent
    from sqlalchemy import select, func

    async with async_session_factory() as session:
        agent_count = await session.execute(
            select(func.count()).select_from(Agent).where(
                Agent.is_deleted == False, Agent.agent_type == "samurai"
            )
        )
        samurai_count = agent_count.scalar() or 0

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

        shogun_result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        shogun = shogun_result.scalars().first()

        return {
            "samurai_count": samurai_count,
            "samurai_rows": samurai_rows,
            "health": [
                ["Runtime", "🟢 Online"],
                ["Database", "🟢 Healthy"],
                ["Qdrant", "🟡 Pending"],
                ["Telegram", "⚪ Not Configured"],
            ],
            "shogun_profile": [
                ["Persona", shogun.name if shogun else "Not configured"],
                ["Status", shogun.status if shogun else "Not configured"],
                ["Spawn Policy", shogun.spawn_policy if shogun else "—"],
                ["Autonomy", "—"],
            ],
            "security": [
                ["Tier", "Guarded"],
                ["File Access", "Scoped"],
                ["Network", "Allowlist"],
                ["Shell", "Disabled"],
            ],
        }


def load_overview() -> dict[str, Any]:
    return _run(_load_overview())


# ═══════════════════════════════════════════════════════════════
#  SECURITY (TORII)
# ═══════════════════════════════════════════════════════════════

async def _load_security_policies() -> list[list[str]]:
    from shogun.db.models.security_policy import SecurityPolicy
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(SecurityPolicy))
        policies = result.scalars().all()
        rows = []
        for p in policies:
            perms = p.permissions or {}
            rows.append([
                p.name, p.tier,
                perms.get("filesystem", "—"),
                perms.get("network", "—"),
                perms.get("shell", "—"),
            ])
        return rows


def load_security_policies() -> list[list[str]]:
    return _run(_load_security_policies())


# ═══════════════════════════════════════════════════════════════
#  KATANA — PROVIDERS
# ═══════════════════════════════════════════════════════════════

async def _list_providers() -> list[list[str]]:
    from shogun.db.models.model_provider import ModelProvider
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(ModelProvider))
        providers = result.scalars().all()
        return [[p.name, p.provider_type, p.status, "—", "—"] for p in providers]


def list_providers() -> list[list[str]]:
    return _run(_list_providers())
