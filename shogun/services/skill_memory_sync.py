"""Skill Memory Synchronization Service.

Synchronizes all installed skills from the 'skills' table into the 'memory_records'
table so they are permanently available in the agent's memory context.
"""

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import json

from shogun.db.models.skill import Skill
from shogun.db.models.memory_record import MemoryRecord

from shogun.config import settings

log = logging.getLogger("shogun.skills_sync")

async def sync_skills_to_memory(session: AsyncSession, agent_id: str) -> None:
    """Sync all installed skills into pinned memory records for the agent."""
    log.info(f"Starting skill memory sync for agent {agent_id}...")
    
    # Get all installed skills
    result = await session.execute(select(Skill))
    installed_skills: List[Skill] = result.scalars().all()
    
    # Get all existing skill memory records for this agent
    result = await session.execute(
        select(MemoryRecord)
        .where(MemoryRecord.agent_id == agent_id)
        .where(MemoryRecord.memory_type == "skill")
    )
    existing_records: List[MemoryRecord] = result.scalars().all()
    existing_by_slug = {}
    for r in existing_records:
        if r.tags:
            for tag in r.tags:
                if tag.startswith("skill:"):
                    slug = tag.split(":")[1]
                    existing_by_slug[slug] = r
                    break
    
    installed_slugs = set()
    from shogun.engine.vector_store import get_vector_store
    qdrant = get_vector_store()
    
    added = 0
    updated = 0
    errors = 0
    
    for skill in installed_skills:
        slug = skill.slug
        installed_slugs.add(slug)
        
        # Build the brief text
        # If the brief_text is empty, fallback to description.
        content = skill.brief_text if skill.brief_text else skill.description
        if not content:
            continue
            
        exam_status = skill.exam_status or "untested"
        skill_type = skill.skill_type or "unknown"
        
        tags = [f"skill:{slug}", f"exam:{exam_status}", f"type:{skill_type}"]
        
        if slug in existing_by_slug:
            # Update existing record
            record = existing_by_slug[slug]
            needs_update = False
            
            if record.content != content or record.tags != tags:
                record.content = content
                record.tags = tags
                record.title = f"Skill: {skill.name}"
                needs_update = True
                
            if needs_update:
                try:
                    await session.flush()
                    await qdrant.upsert(
                        memory_id=str(record.id),
                        content=record.content,
                        metadata={
                            "memory_type": "skill",
                            "agent_id": agent_id,
                            "tags": tags,
                        }
                    )
                    updated += 1
                except Exception as e:
                    log.error(f"Failed to update Qdrant embedding for skill {slug}: {e}")
                    errors += 1
                    # Do not abort the sync
        else:
            # Create new record
            new_record = MemoryRecord(
                agent_id=agent_id,
                memory_type="skill",
                title=f"Skill: {skill.name}",
                content=content,
                decay_class="pinned",
                is_pinned=True,
                importance_score=0.95,
                relevance_score=0.95,
                tags=tags,
                source_type="system",
            )
            session.add(new_record)
            try:
                await session.flush()
                await qdrant.upsert(
                    memory_id=str(new_record.id),
                    content=new_record.content,
                    metadata={
                        "memory_type": "skill",
                        "agent_id": agent_id,
                        "tags": tags,
                    }
                )
                added += 1
            except Exception as e:
                log.error(f"Failed to create Qdrant embedding for skill {slug}: {e}")
                errors += 1
                # Do not abort the sync
                
    # Archive any skill memories for skills that were uninstalled
    archived = 0
    for slug, record in existing_by_slug.items():
        if slug not in installed_slugs and not record.is_archived:
            record.is_archived = True
            archived += 1
            
    await session.commit()
    log.info(f"Skill memory sync complete: {added} added, {updated} updated, {archived} archived, {errors} errors.")
