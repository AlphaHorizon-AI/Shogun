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
from sqlalchemy.orm import joinedload

from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation
from shogun.db.models.skillopt import SkillVersion

log = logging.getLogger("shogun.skills_sync")

SKILLS_MEMORY_TYPE = "skills"
LEGACY_SKILLS_MEMORY_TYPE = "skill"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


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
    """Fetch real College Markdown whenever local canonical proof is missing."""
    legacy = [
        skill
        for skill in skills
        if (skill.manifest or {}).get("openclaw_id")
        and (skill.manifest or {}).get("optimized_by") != "skillopt"
        and (
            (skill.manifest or {}).get("canonical_content_source") != "openclaw_college"
            or not (skill.manifest or {}).get("canonical_content_hash")
            or not skill.body_text
            or _content_hash(skill.body_text) != (skill.manifest or {}).get("canonical_content_hash")
        )
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
        manifest["canonical_content_hash"] = _content_hash(content)
        manifest["canonical_content_length"] = len(content)
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
                    content_hash=_content_hash(content),
                    created_by="openclaw_college",
                )
                session.add(version)
                await session.flush()
            skill.active_version_id = version.id
        hydrated += 1
    return hydrated


async def refresh_installed_openclaw_skills(session: AsyncSession) -> dict[str, Any]:
    """Refresh installed College skills from the live canonical Markdown.

    Content hashes, rather than version labels alone, determine whether a new
    local version is required. Skills promoted by SkillOpt are deliberately
    protected from upstream replacement. After refresh, every active agent's
    Archives Skills mirror is repaired from the selected canonical content.
    """
    result = await session.execute(
        select(SkillInstallation)
        .where(SkillInstallation.status == "installed")
        .options(joinedload(SkillInstallation.skill))
    )
    installations = [
        installation
        for installation in result.scalars().unique().all()
        if installation.skill
        and not installation.skill.is_deleted
        and (installation.openclaw_skill_id or (installation.skill.manifest or {}).get("openclaw_id"))
    ]
    report: dict[str, Any] = {
        "total": len(installations),
        "checked": 0,
        "updated": 0,
        "unchanged": 0,
        "protected": 0,
        "missing": 0,
        "errors": 0,
    }
    refreshable: list[tuple[SkillInstallation, Skill, str]] = []
    for installation in installations:
        skill = installation.skill
        if (skill.manifest or {}).get("optimized_by") == "skillopt":
            report["protected"] += 1
            continue
        openclaw_id = str(
            installation.openclaw_skill_id or (skill.manifest or {}).get("openclaw_id")
        )
        refreshable.append((installation, skill, openclaw_id))

    responses: list[Any] = []
    if refreshable:
        from shogun.integrations.openclaw_client import get_openclaw_client

        try:
            async with get_openclaw_client() as client:
                responses = list(
                    await asyncio.gather(
                        *(client.get_skill_by_id(openclaw_id) for _, _, openclaw_id in refreshable),
                        return_exceptions=True,
                    )
                )
        except Exception as exc:
            log.warning("Could not refresh installed OpenClaw skills: %s", exc)
            report["errors"] += len(refreshable)
            responses = []

    from shogun.config import settings

    for (installation, skill, openclaw_id), college_skill in zip(refreshable, responses):
        report["checked"] += 1
        if isinstance(college_skill, Exception):
            log.warning("OpenClaw refresh failed for %s: %s", skill.slug, college_skill)
            report["errors"] += 1
            continue
        if not college_skill or not college_skill.description_md.strip():
            report["missing"] += 1
            continue

        content = college_skill.description_md.strip()
        content_hash = _content_hash(content)
        upstream_version = college_skill.version or installation.installed_version or skill.version
        manifest = dict(skill.manifest or {})
        if (
            skill.body_text == content
            and manifest.get("canonical_content_hash") == content_hash
            and skill.version == upstream_version
        ):
            installation.installed_version = upstream_version
            report["unchanged"] += 1
            continue

        safe_slug = re.sub(r"[^a-z0-9-]+", "-", skill.slug.lower()).strip("-") or str(skill.id)
        content_path = settings.vault_path / "skills" / "openclaw" / safe_slug / "SKILL.md"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        content_path.write_text(content + "\n", encoding="utf-8")

        parent_version_id = skill.active_version_id
        if parent_version_id:
            active_version = await session.get(SkillVersion, parent_version_id)
            if active_version:
                active_version.status = "archived"
        version_result = await session.execute(
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill.id)
            .order_by(SkillVersion.version_number.desc())
            .limit(1)
        )
        latest_version = version_result.scalars().first()
        new_version = SkillVersion(
            skill_id=skill.id,
            version_number=(latest_version.version_number + 1) if latest_version else 1,
            status="active",
            content_path=str(content_path),
            content_hash=content_hash,
            parent_version_id=parent_version_id,
            created_by="openclaw_college_refresh",
            metadata_json={"upstream_version": upstream_version, "openclaw_id": openclaw_id},
        )
        session.add(new_version)
        await session.flush()

        skill.body_text = content
        skill.brief_text = None
        skill.local_path = str(content_path)
        skill.version = upstream_version
        skill.active_version_id = new_version.id
        skill.manifest = {
            **manifest,
            "openclaw_id": openclaw_id,
            "description": college_skill.short_description or skill.name,
            "canonical_content_source": "openclaw_college",
            "canonical_content_hash": content_hash,
            "canonical_content_length": len(content),
            "canonical_upstream_version": upstream_version,
        }
        installation.installed_version = upstream_version
        report["updated"] += 1

    archives_sync = await sync_skills_to_all_agent_memories(session)
    report["archives"] = archives_sync
    log.info("Installed OpenClaw refresh complete: %s", report)
    return report


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
        canonical_hash = _content_hash(content)
        openclaw_id = (skill.manifest or {}).get("openclaw_id")
        tags = [
            f"skill:{skill.slug}",
            f"exam:{skill.exam_status or 'untested'}",
            f"type:{skill.skill_type or 'unknown'}",
            "canonical:skills-archive",
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
                source_system="openclaw_college" if openclaw_id else "shogun",
                source_external_id=str(openclaw_id) if openclaw_id else str(skill.id),
                content_hash=canonical_hash,
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
                "source_system": "openclaw_college" if openclaw_id else "shogun",
                "source_external_id": str(openclaw_id) if openclaw_id else str(skill.id),
                "content_hash": canonical_hash,
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
