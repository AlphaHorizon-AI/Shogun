"""Synchronize installed Dojo skills into the canonical Archives Skills layer."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation
from shogun.db.models.skillopt import SkillVersion

log = logging.getLogger("shogun.skills_sync")

SKILLS_MEMORY_TYPE = "skills"
LEGACY_SKILLS_MEMORY_TYPE = "skill"


async def _installed_skills(session: AsyncSession) -> list[Skill]:
    installed_ids = select(SkillInstallation.skill_id).where(SkillInstallation.status == "installed")
    result = await session.execute(
        select(Skill).where(
            Skill.is_deleted.is_(False),
            or_(
                Skill.id.in_(installed_ids),
                Skill.status == "installed",
                Skill.exam_status == "passed",
            ),
        )
    )
    return list(result.scalars().all())


async def _hydrate_legacy_openclaw_markdown(session: AsyncSession, skills: list[Skill]) -> int:
    """Upgrade summary-only College installs to their real Markdown once."""
    legacy = [
        skill
        for skill in skills
        if (skill.manifest or {}).get("openclaw_id")
        and (skill.manifest or {}).get("canonical_content_source") != "openclaw_college"
        and (skill.manifest or {}).get("optimized_by") != "skillopt"
    ]
    if not legacy:
        return 0

    from shogun.config import settings
    from shogun.integrations.openclaw_client import get_openclaw_client

    hydrated = 0
    try:
        async with get_openclaw_client() as client:
            responses = await asyncio.gather(
                *(client.get_skill_by_id(str(skill.manifest["openclaw_id"])) for skill in legacy),
                return_exceptions=True,
            )
    except Exception as exc:
        log.warning("Could not hydrate legacy OpenClaw skill Markdown: %s", exc)
        return 0

    for skill, college_skill in zip(legacy, responses):
        if isinstance(college_skill, Exception) or not college_skill or not college_skill.description_md.strip():
            log.warning("OpenClaw Markdown unavailable for legacy skill %s", skill.slug)
            continue
        content = college_skill.description_md.strip()
        safe_slug = re.sub(r"[^a-z0-9-]+", "-", skill.slug.lower()).strip("-") or str(skill.id)
        content_path = settings.vault_path / "skills" / "openclaw" / safe_slug / "SKILL.md"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(content + "\n", encoding="utf-8")
        skill.body_text = content
        skill.brief_text = None
        skill.local_path = str(content_path)
        skill.version = college_skill.version or skill.version
        manifest = dict(skill.manifest or {})
        manifest["canonical_content_source"] = "openclaw_college"
        manifest["description"] = college_skill.short_description or skill.name
        skill.manifest = manifest
        if not skill.active_version_id:
            version_result = await session.execute(
                select(SkillVersion)
                .where(SkillVersion.skill_id == skill.id)
                .order_by(SkillVersion.version_number.desc())
                .limit(1)
            )
            version = version_result.scalars().first()
            if version is None:
                version = SkillVersion(
                    skill_id=skill.id,
                    version_number=1,
                    status="active",
                    content_path=str(content_path),
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    created_by="openclaw_college",
                )
                session.add(version)
                await session.flush()
            skill.active_version_id = version.id
        hydrated += 1
    return hydrated


async def sync_skills_to_memory(session: AsyncSession, agent_id: str | uuid.UUID) -> dict[str, int]:
    """Upsert every installed skill as one pinned Archives ``skills`` record.

    Existing records written with the legacy singular ``skill`` type are
    migrated in place, so installations repair themselves without a database
    migration or duplicate cards.
    """
    agent_uuid = agent_id if isinstance(agent_id, uuid.UUID) else uuid.UUID(str(agent_id))
    skills = await _installed_skills(session)
    hydrated = await _hydrate_legacy_openclaw_markdown(session, skills)
    result = await session.execute(
        select(MemoryRecord).where(
            MemoryRecord.agent_id == agent_uuid,
            MemoryRecord.memory_type.in_((SKILLS_MEMORY_TYPE, LEGACY_SKILLS_MEMORY_TYPE)),
        )
    )
    existing_records = list(result.scalars().all())
    existing_by_slug: dict[str, MemoryRecord] = {}
    existing_by_skill_id = {
        str(record.source_ref_id): record for record in existing_records if record.source_ref_id
    }
    for record in existing_records:
        for tag in record.tags or []:
            if str(tag).startswith("skill:"):
                existing_by_slug[str(tag).split(":", 1)[1]] = record
                break

    installed_slugs: set[str] = set()
    added = updated = archived = errors = 0
    from shogun.engine.vector_store import get_vector_store

    try:
        store = get_vector_store()
    except Exception as exc:
        # Archives is backed by SQL; a vector-store outage must not prevent
        # installed skills from becoming visible there.
        log.warning("Vector store unavailable during skill sync: %s", exc)
        store = None
    for skill in skills:
        installed_slugs.add(skill.slug)
        content = skill.body_text or skill.brief_text or skill.description or skill.name
        tags = [
            f"skill:{skill.slug}",
            f"exam:{skill.exam_status or 'untested'}",
            f"type:{skill.skill_type or 'unknown'}",
        ]
        record = existing_by_skill_id.get(str(skill.id)) or existing_by_slug.get(skill.slug)
        changed = False
        if record is None:
            record = MemoryRecord(
                agent_id=agent_uuid,
                memory_type=SKILLS_MEMORY_TYPE,
                source_ref_id=skill.id,
                title=f"Skill: {skill.name}",
                content=content,
                decay_class="pinned",
                is_pinned=True,
                importance_score=0.95,
                relevance_score=0.95,
                confidence_score=0.95,
                tags=tags,
                source_type="dojo_skill",
            )
            session.add(record)
            added += 1
            changed = True
        else:
            expected: dict[str, Any] = {
                "memory_type": SKILLS_MEMORY_TYPE,
                "source_ref_id": skill.id,
                "title": f"Skill: {skill.name}",
                "content": content,
                "tags": tags,
                "is_pinned": True,
                "is_archived": False,
                "decay_class": "pinned",
                "source_type": "dojo_skill",
            }
            for field, value in expected.items():
                if getattr(record, field) != value:
                    setattr(record, field, value)
                    changed = True
            if changed:
                updated += 1

        if changed and store is not None:
            try:
                await session.flush()
                await asyncio.to_thread(
                    store.upsert,
                    memory_id=str(record.id),
                    text=f"{record.title}\n\n{record.content}",
                    payload={
                        "memory_type": SKILLS_MEMORY_TYPE,
                        "agent_id": str(agent_uuid),
                        "skill_id": str(skill.id),
                        "source_ref_id": str(skill.id),
                        "title": record.title,
                        "importance_score": record.importance_score,
                        "decay_class": record.decay_class,
                        "is_pinned": True,
                        "tags": tags,
                    },
                )
                record.qdrant_point_id = str(record.id)
            except Exception as exc:
                log.warning("Skill vector sync failed for %s: %s", skill.slug, exc)
                errors += 1

    for record in existing_records:
        slug = next(
            (str(tag).split(":", 1)[1] for tag in record.tags or [] if str(tag).startswith("skill:")),
            None,
        )
        if slug and slug not in installed_slugs and not record.is_archived:
            record.is_archived = True
            archived += 1

    await session.commit()
    result = {
        "added": added,
        "updated": updated,
        "archived": archived,
        "errors": errors,
        "total": len(skills),
    }
    if hydrated:
        log.info("Hydrated %s legacy OpenClaw skill files before Archives sync", hydrated)
    log.info("Skill memory sync complete: %s", result)
    return result


async def sync_skills_to_all_agent_memories(session: AsyncSession) -> dict[str, int]:
    """Refresh the canonical Skills layer for every active local agent."""
    result = await session.execute(select(Agent.id).where(Agent.is_deleted.is_(False)))
    agent_ids = list(result.scalars().all())
    totals = {"agents": len(agent_ids), "added": 0, "updated": 0, "archived": 0, "errors": 0}
    for agent_id in agent_ids:
        stats = await sync_skills_to_memory(session, agent_id)
        for field in ("added", "updated", "archived", "errors"):
            totals[field] += stats[field]
    if not agent_ids:
        await session.commit()
    return totals


async def mark_skill_achieved_and_sync(
    session: AsyncSession,
    agent_id: str | uuid.UUID,
    openclaw_skill_id: str,
) -> bool:
    """Mark an installed College skill passed and immediately refresh Archives."""
    result = await session.execute(
        select(Skill)
        .join(SkillInstallation, SkillInstallation.skill_id == Skill.id)
        .where(
            SkillInstallation.openclaw_skill_id == openclaw_skill_id,
            SkillInstallation.status == "installed",
        )
    )
    skill = result.scalars().first()
    if not skill:
        return False
    skill.exam_status = "passed"
    await sync_skills_to_memory(session, agent_id)
    return True
