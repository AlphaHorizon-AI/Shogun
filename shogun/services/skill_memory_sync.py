"""Synchronize installed Dojo skills into the canonical Archives Skills layer."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation

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


async def sync_skills_to_memory(session: AsyncSession, agent_id: str | uuid.UUID) -> dict[str, int]:
    """Upsert every installed skill as one pinned Archives ``skills`` record.

    Existing records written with the legacy singular ``skill`` type are
    migrated in place, so installations repair themselves without a database
    migration or duplicate cards.
    """
    agent_uuid = agent_id if isinstance(agent_id, uuid.UUID) else uuid.UUID(str(agent_id))
    skills = await _installed_skills(session)
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
    result = {"added": added, "updated": updated, "archived": archived, "errors": errors, "total": len(skills)}
    log.info("Skill memory sync complete: %s", result)
    return result


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
