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

    print("✅ Database tables created successfully.")
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
    print("\n🏯 Shogun is ready. Run: python main.py")


async def _seed_defaults():
    """Insert default seed records (idempotent)."""
    from shogun.db.models.skill_source import SkillSource
    from shogun.db.models.security_policy import SecurityPolicy
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
            print("   ✅ Seeded: OpenClaw College skill source")
        else:
            print("   ⏭  OpenClaw College source already exists")

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
                        "filesystem": "scoped" if tier in ("shrine", "guarded") else "full",
                        "network": "disabled" if tier == "shrine" else "allowlist" if tier == "guarded" else "full",
                        "shell": "disabled" if tier in ("shrine", "guarded", "tactical") else "allowed",
                        "skill_install": "approval_required" if tier in ("shrine", "guarded") else "auto",
                        "subagent_spawn": "disabled" if tier == "shrine" else "allowed",
                    },
                    kill_switch_enabled=tier != "ronin",
                    dry_run_supported=True,
                    is_builtin=True,
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                session.add(policy)

        await session.commit()
        print("   ✅ Seeded: 5 security policies")


if __name__ == "__main__":
    asyncio.run(bootstrap())
