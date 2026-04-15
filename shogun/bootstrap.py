"""Bootstrap script — creates database tables + seeds default data.

Run once after install: python -m shogun.bootstrap
"""

import asyncio
import uuid
from datetime import datetime, timezone

from shogun.config import settings
from shogun.db.base import Base
from shogun.db.engine import engine, async_session_factory

# Import all models so they register with Base.metadata
import shogun.db.models  # noqa: F401


async def bootstrap():
    settings.ensure_directories()

    # ── Create tables ─────────────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("OK: Database tables created successfully.")
    print(f"   Database: {settings.database_url}")

    # List tables
    from sqlalchemy import inspect

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        print(f"   Tables: {len(tables)}")
        for t in sorted(tables):
            print(f"     • {t}")

    # ── Seed default data ─────────────────────────────────────
    await _seed_defaults()

    await engine.dispose()
    print("\nOK: Shogun is ready. Run: python main.py")


async def _seed_defaults():
    """Insert default seed records (idempotent)."""
    from shogun.db.models.skill_source import SkillSource
    from shogun.db.models.security_policy import SecurityPolicy
    from shogun.db.models.persona import Persona
    from shogun.db.models.model_routing import ModelRoutingProfile
    from shogun.db.models.samurai_role import SamuraiRole
    from sqlalchemy import select

    async with async_session_factory() as session:
        # ── OpenClaw College as default skill source ──────────
        result = await session.execute(
            select(SkillSource).where(SkillSource.slug == "openclaw-college")
        )
        if not result.scalars().first():
            source = SkillSource(
                id=uuid.uuid4(),
                name="OpenClaw College",
                slug="openclaw-college",
                source_type="openclaw_api",
                base_url="https://www.openclawcollege.com/api",
                default_enabled=True,
                trust_level="trusted",
                sync_policy="on_demand",
                status="active",
                created_by="bootstrap",
                updated_by="bootstrap",
            )
            session.add(source)
            print("   OK: Seeded: OpenClaw College skill source")
        else:
            print("   INFO: OpenClaw College source already exists")

        # ── Default security policies ─────────────────────────
        for slug, name, tier in [
            ("shrine", "Shrine — Locked Down", "shrine"),
            ("guarded", "Guarded — Default", "guarded"),
            ("tactical", "Tactical — Expanded", "tactical"),
            ("campaign", "Campaign — Full", "campaign"),
            ("ronin", "Ronin — Open", "ronin"),
        ]:
            result = await session.execute(
                select(SecurityPolicy).where(SecurityPolicy.name == name)
            )
            if not result.scalars().first():
                policy = SecurityPolicy(
                    id=uuid.uuid4(),
                    name=name,
                    tier=tier,
                    description=f"Built-in {tier} security policy",
                    permissions={
                        "filesystem": {"mode": "scoped" if tier in ("shrine", "guarded") else "full"},
                        "network": {"mode": "disabled" if tier == "shrine" else "allowlist" if tier == "guarded" else "full"},
                        "shell": {"enabled": tier not in ("shrine", "guarded", "tactical")},
                        "skills": {"require_approval": tier in ("shrine", "guarded")},
                        "subagents": {"allow_spawn": tier != "shrine"},
                    },
                    kill_switch_enabled=tier != "ronin",
                    dry_run_supported=True,
                    is_builtin=True,
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                session.add(policy)

        # ── Default personas ──────────────────────────────────
        persona_defs = [
            {
                "slug": "shogun-prime",
                "name": "The Shogun",
                "description": "Supreme orchestrator. Commands the Samurai lattice with strategic precision, balancing long-term planning with decisive real-time action. Prioritizes system integrity and mission continuity above all.",
                "tone": "strategic",
                "autonomy": "high",
                "risk_tolerance": "medium",
                "verbosity": "medium",
                "planning_depth": "high",
                "tool_usage_style": "balanced",
                "security_bias": "strict",
                "memory_style": "focused",
            },
            {
                "slug": "stealth-operative",
                "name": "Stealth Operative",
                "description": "Silent executor. Operates with minimal footprint, preferring covert data gathering and surgical task completion. Avoids unnecessary tool invocations and keeps communication terse.",
                "tone": "analytical",
                "autonomy": "medium",
                "risk_tolerance": "low",
                "verbosity": "low",
                "planning_depth": "high",
                "tool_usage_style": "conservative",
                "security_bias": "strict",
                "memory_style": "conservative",
            },
            {
                "slug": "audit-master",
                "name": "Audit Master",
                "description": "Relentless inspector. Methodically reviews every output, cross-references facts, and flags inconsistencies. Ideal for compliance workflows and quality assurance missions.",
                "tone": "analytical",
                "autonomy": "medium",
                "risk_tolerance": "low",
                "verbosity": "high",
                "planning_depth": "high",
                "tool_usage_style": "balanced",
                "security_bias": "strict",
                "memory_style": "focused",
            },
            {
                "slug": "diplomat",
                "name": "The Diplomat",
                "description": "Empathetic communicator. Excels at nuanced conversation, stakeholder management, and producing human-friendly reports. Balances warmth with professionalism across all interactions.",
                "tone": "supportive",
                "autonomy": "medium",
                "risk_tolerance": "medium",
                "verbosity": "high",
                "planning_depth": "medium",
                "tool_usage_style": "conservative",
                "security_bias": "balanced",
                "memory_style": "expansive",
            },
            {
                "slug": "field-commander",
                "name": "Field Commander",
                "description": "Aggressive executor. Moves fast, delegates ruthlessly, and prioritizes mission velocity over caution. Spawns sub-agents freely and chains tools without hesitation.",
                "tone": "direct",
                "autonomy": "high",
                "risk_tolerance": "high",
                "verbosity": "low",
                "planning_depth": "medium",
                "tool_usage_style": "aggressive",
                "security_bias": "open",
                "memory_style": "conservative",
            },
            {
                "slug": "research-analyst",
                "name": "Research Analyst",
                "description": "Deep thinker. Gathers exhaustive context before acting, cross-references multiple sources, and produces thorough analytical reports with full citation chains.",
                "tone": "analytical",
                "autonomy": "low",
                "risk_tolerance": "low",
                "verbosity": "high",
                "planning_depth": "high",
                "tool_usage_style": "balanced",
                "security_bias": "balanced",
                "memory_style": "expansive",
            },
            {
                "slug": "watchdog",
                "name": "The Watchdog",
                "description": "Paranoid guardian. Treats every input as potentially hostile, validates all tool outputs, enforces strict sandboxing, and escalates any anomaly. Built for high-security environments.",
                "tone": "direct",
                "autonomy": "low",
                "risk_tolerance": "low",
                "verbosity": "medium",
                "planning_depth": "high",
                "tool_usage_style": "conservative",
                "security_bias": "strict",
                "memory_style": "focused",
            },
        ]

        for pdef in persona_defs:
            result = await session.execute(
                select(Persona).where(Persona.slug == pdef["slug"])
            )
            existing = result.scalars().first()
            if not existing:
                persona = Persona(
                    id=uuid.uuid4(),
                    slug=pdef["slug"],
                    name=pdef["name"],
                    description=pdef["description"],
                    tone=pdef["tone"],
                    risk_tolerance=pdef["risk_tolerance"],
                    autonomy=pdef["autonomy"],
                    verbosity=pdef["verbosity"],
                    planning_depth=pdef["planning_depth"],
                    tool_usage_style=pdef["tool_usage_style"],
                    security_bias=pdef["security_bias"],
                    memory_style=pdef["memory_style"],
                    is_builtin=True,
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                session.add(persona)
            elif not existing.description or existing.description.startswith("Built-in"):
                # Update generic descriptions on existing personas
                existing.description = pdef["description"]

        # ── Default model routing profiles ───────────────────
        for name in ["Balanced (Default)", "Quality First", "Cost Optimized"]:
            result = await session.execute(
                select(ModelRoutingProfile).where(ModelRoutingProfile.name == name)
            )
            if not result.scalars().first():
                profile = ModelRoutingProfile(
                    id=uuid.uuid4(),
                    name=name,
                    description=f"Built-in {name} routing strategy",
                    rules=[
                        {"task_type": "*", "primary_model_id": "00000000-0000-0000-0000-000000000000", "fallback_model_ids": []}
                    ],
                    is_default=(name == "Balanced (Default)"),
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                session.add(profile)

        # ── Default Samurai Roles ───────────────────────────
        samurai_role_defs = [
            {"slug": "research-scout", "name": "Research Scout", "purpose": "Finds and gathers relevant information quickly.", "description": "A reconnaissance sub-agent specialized in collecting external or internal data, identifying useful sources, and surfacing the most relevant facts for deeper analysis."},
            {"slug": "source-verifier", "name": "Source Verifier", "purpose": "Checks credibility and factual consistency.", "description": "Validates claims, compares sources, flags weak evidence, and ensures that downstream outputs are grounded in trustworthy information."},
            {"slug": "summarization-clerk", "name": "Summarization Clerk", "purpose": "Compresses large volumes of information into digestible form.", "description": "Converts long documents, logs, reports, or threads into concise, structured summaries while preserving key meaning and priority items."},
            {"slug": "task-decomposer", "name": "Task Decomposer", "purpose": "Breaks complex work into executable parts.", "description": "Translates broad objectives into ordered subtasks, dependencies, milestones, and next actions so execution becomes manageable and trackable."},
            {"slug": "workflow-coordinator", "name": "Workflow Coordinator", "purpose": "Organizes multi-step execution across agents or tools.", "description": "Routes tasks, manages sequencing, monitors state transitions, and ensures that work moves cleanly between planning, execution, and review."},
            {"slug": "memory-keeper", "name": "Memory Keeper", "purpose": "Maintains relevant context over time.", "description": "Tracks persistent facts, stores reusable context, retrieves prior decisions, and helps the wider agent system stay coherent across longer workflows."},
            {"slug": "knowledge-librarian", "name": "Knowledge Librarian", "purpose": "Structures and classifies knowledge assets.", "description": "Organizes documents, notes, references, and outputs into searchable and reusable knowledge structures for future retrieval and reasoning."},
            {"slug": "risk-assessor", "name": "Risk Assessor", "purpose": "Identifies downside exposure and fragility.", "description": "Examines proposed actions for operational, strategic, reputational, legal, or technical risks and highlights likely failure points before execution."},
            {"slug": "compliance-checker", "name": "Compliance Checker", "purpose": "Enforces rules, policies, and boundaries.", "description": "Reviews actions and outputs against internal policies, governance requirements, and external constraints to reduce avoidable violations."},
            {"slug": "quality-reviewer", "name": "Quality Reviewer", "purpose": "Reviews outputs before they are finalized.", "description": "Performs structured quality control on content, decisions, plans, and deliverables by checking for completeness, clarity, consistency, and defects."},
            {"slug": "logic-auditor", "name": "Logic Auditor", "purpose": "Tests reasoning quality.", "description": "Examines chains of reasoning for contradictions, missing assumptions, weak inferences, and faulty conclusions before outputs are approved."},
            {"slug": "code-implementer", "name": "Code Implementer", "purpose": "Handles technical build tasks.", "description": "Writes, edits, or refactors code in line with scoped requirements, with a focus on functionality, maintainability, and implementation discipline."},
            {"slug": "debug-specialist", "name": "Debug Specialist", "purpose": "Finds and isolates technical failures.", "description": "Investigates errors, traces root causes, tests hypotheses, and proposes targeted fixes for broken code, workflows, or system behavior."},
            {"slug": "data-analyst", "name": "Data Analyst", "purpose": "Interprets structured data.", "description": "Review datasets, detects patterns, calculates metrics, and turns raw numerical information into actionable analytical findings."},
            {"slug": "simulation-operator", "name": "Simulation Operator", "purpose": "Runs modeled scenarios and comparative tests.", "description": "Executes scenario logic, parameter sweeps, what-if analyses, and behavioral simulations to evaluate likely outcomes under different conditions."},
            {"slug": "strategy-mapper", "name": "Strategy Mapper", "purpose": "Connects actions to larger objectives.", "description": "Aligns recommendations and tasks with strategic goals, priorities, trade-offs, and business intent so local execution supports global outcomes."},
            {"slug": "creative-generator", "name": "Creative Generator", "purpose": "Produces novel options and concept variations.", "description": "Generates ideas, narratives, names, framing angles, and alternative concepts when originality, divergence, or imaginative thinking is needed."},
            {"slug": "communication-drafter", "name": "Communication Drafter", "purpose": "Converts intent into clear messaging.", "description": "Drafts emails, reports, updates, summaries, prompts, and stakeholder-facing communication adapted to audience, tone, and objective."},
            {"slug": "negotiation-support", "name": "Negotiation Support", "purpose": "Helps manage stakeholder tension and alignment.", "description": "Prepares talking points, identifies compromise paths, anticipates objections, and supports interactions where persuasion or diplomacy is required."},
            {"slug": "execution-monitor", "name": "Execution Monitor", "purpose": "Tracks progress and completion.", "description": "Watches running tasks, checks status against plan, flags delays or drift, and helps ensure that planned work actually gets finished correctly."},
        ]

        for rdef in samurai_role_defs:
            result = await session.execute(
                select(SamuraiRole).where(SamuraiRole.slug == rdef["slug"])
            )
            if not result.scalars().first():
                role = SamuraiRole(
                    id=uuid.uuid4(),
                    slug=rdef["slug"],
                    name=rdef["name"],
                    purpose=rdef["purpose"],
                    description=rdef["description"],
                    is_builtin=True,
                    is_active=True,
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                session.add(role)

        await session.commit()
        print("   OK: Seeded: 5 security policies")
        print("   OK: Seeded: 20 Samurai Roles")


if __name__ == "__main__":
    asyncio.run(bootstrap())
