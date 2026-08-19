"""Skill Rollback Service — Order 15.

Handles rollback to previous skill versions, deprecation, and archiving.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillVersion
from shogun.services.enterprise_transformation_skill import (
    ProtectedSkillMutationError,
    assert_skill_mutable,
)

logger = logging.getLogger(__name__)


class SkillRollbackService:
    """Rollback, deprecation, and archival of skills."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def rollback(
        self,
        skill_id: uuid.UUID,
        target_version_id: uuid.UUID | None = None,
    ) -> dict:
        """Rollback a skill to a previous version.

        If target_version_id is None, rolls back to the previous version
        (the parent of the current active version).
        """
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        try:
            assert_skill_mutable(skill, "roll back")
        except ProtectedSkillMutationError as exc:
            return {
                "status": "error",
                "code": "protected_builtin_skill",
                "message": str(exc),
            }

        if target_version_id:
            target = await self.session.get(SkillVersion, target_version_id)
        else:
            # Find the parent of the current active version
            if not skill.active_version_id:
                return {"status": "error", "message": "Skill has no active version to roll back from."}
            current = await self.session.get(SkillVersion, skill.active_version_id)
            if not current or not current.parent_version_id:
                return {"status": "error", "message": "No previous version available for rollback."}
            target = await self.session.get(SkillVersion, current.parent_version_id)

        if not target:
            return {"status": "error", "message": "Target version not found."}

        # Deactivate current version
        if skill.active_version_id:
            old = await self.session.get(SkillVersion, skill.active_version_id)
            if old:
                old.status = "deprecated"

        # Activate target version
        target.status = "active"
        skill.active_version_id = target.id
        skill.lifecycle_state = "active"

        # Update skill body from the rolled-back version's file
        try:
            with open(target.content_path, "r", encoding="utf-8") as f:
                skill.body_text = f.read()
        except (FileNotFoundError, OSError):
            logger.warning("Could not read rolled-back content from %s", target.content_path)

        await self.session.flush()

        # Audit
        try:
            from shogun.services.event_logger import EventLogger
            await EventLogger.emit(
                "skill.rollback_completed",
                f"Rolled back {skill.name!r} to version {target.version_number}",
                severity="warning",
                detail={"skill_id": str(skill_id), "target_version_id": str(target.id)},
            )
        except Exception:
            pass

        return {
            "status": "success",
            "message": f"Rolled back to version {target.version_number}.",
            "active_version_id": str(target.id),
            "version_number": target.version_number,
        }

    async def deprecate(self, skill_id: uuid.UUID) -> dict:
        """Mark a skill as deprecated (no longer used by default)."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        try:
            assert_skill_mutable(skill, "deprecate")
        except ProtectedSkillMutationError as exc:
            return {
                "status": "error",
                "code": "protected_builtin_skill",
                "message": str(exc),
            }

        skill.lifecycle_state = "deprecated"
        await self.session.flush()

        try:
            from shogun.services.event_logger import EventLogger
            await EventLogger.emit(
                "skill.deprecated",
                f"Skill {skill.name!r} deprecated",
                severity="info",
            )
        except Exception:
            pass

        return {"status": "success", "message": f"Skill {skill.name!r} deprecated."}

    async def archive(self, skill_id: uuid.UUID) -> dict:
        """Archive a skill — retained for history but removed from active use."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        try:
            assert_skill_mutable(skill, "archive")
        except ProtectedSkillMutationError as exc:
            return {
                "status": "error",
                "code": "protected_builtin_skill",
                "message": str(exc),
            }

        skill.lifecycle_state = "archived"
        skill.archived_at = datetime.now(timezone.utc)
        skill.status = "archived"
        await self.session.flush()

        try:
            from shogun.services.event_logger import EventLogger
            await EventLogger.emit(
                "skill.archived",
                f"Skill {skill.name!r} archived",
                severity="info",
            )
        except Exception:
            pass

        return {"status": "success", "message": f"Skill {skill.name!r} archived."}

    async def get_versions(self, skill_id: uuid.UUID) -> list[dict]:
        """List all versions for a skill, most recent first."""
        stmt = (
            select(SkillVersion)
            .where(SkillVersion.skill_id == skill_id)
            .order_by(SkillVersion.version_number.desc())
        )
        result = await self.session.execute(stmt)
        return [
            {
                "id": str(v.id),
                "version_number": v.version_number,
                "status": v.status,
                "content_hash": v.content_hash,
                "created_by": v.created_by,
                "validation_score": v.validation_score,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in result.scalars().all()
        ]
