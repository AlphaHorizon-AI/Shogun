"""Skill Versioning Service."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptToolSchemaVersion, SkillVersion
from shogun.services.base_service import BaseService
from shogun.services.enterprise_transformation_skill import assert_skill_mutable

logger = logging.getLogger(__name__)


class SkillVersionService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillVersion, db_session)
        self.db = db_session

    async def get_active_version(self, skill_id: uuid.UUID) -> SkillVersion | None:
        """Get the currently active version of a skill."""
        skill = await self.db.get(Skill, skill_id)
        if not skill or not skill.active_version_id:
            return None
        return await self.db.get(SkillVersion, skill.active_version_id)

    async def get_versions(self, skill_id: uuid.UUID) -> list[SkillVersion]:
        """Get all versions of a skill."""
        stmt = (
            select(SkillVersion).where(SkillVersion.skill_id == skill_id).order_by(SkillVersion.version_number.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_initial_version(
        self, skill: Skill, content_path: str, content: str, created_by: str = "system"
    ) -> SkillVersion:
        """Create the v1 version for a skill if none exists."""
        assert_skill_mutable(skill, "create an initial version for")
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Check if any version exists
        existing = await self.get_versions(skill.id)
        if existing:
            return existing[-1]  # Return the oldest (v1)

        version = SkillVersion(
            id=uuid.uuid4(),
            skill_id=skill.id,
            version_number=1,
            status="active",
            content_path=content_path,
            content_hash=content_hash,
            created_by=created_by,
            activated_at=datetime.now(timezone.utc),
        )
        self.db.add(version)
        skill.active_version_id = version.id
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def create_new_version(
        self,
        skill_id: uuid.UUID,
        parent_version_id: uuid.UUID,
        content_path: str,
        content: str,
        status: str = "candidate",
        created_by: str = "skillopt",
    ) -> SkillVersion:
        """Create a new version (e.g. from a candidate)."""
        skill = await self.db.get(Skill, skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        assert_skill_mutable(skill, "create a new version for")

        if parent_version_id:
            parent = await self.db.get(SkillVersion, parent_version_id)
            if parent and parent.skill_id != skill_id:
                raise ValueError(f"Parent version {parent_version_id} does not belong to skill {skill_id}")

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Determine next version number
        versions = await self.get_versions(skill_id)
        next_number = versions[0].version_number + 1 if versions else 1

        version = SkillVersion(
            id=uuid.uuid4(),
            skill_id=skill_id,
            version_number=next_number,
            status=status,
            content_path=content_path,
            content_hash=content_hash,
            parent_version_id=parent_version_id,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def activate_version(self, skill_id: uuid.UUID, version_id: uuid.UUID) -> SkillVersion:
        """Make a specific version the active one."""
        skill = await self.db.get(Skill, skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        assert_skill_mutable(skill, "activate another version of")

        version = await self.db.get(SkillVersion, version_id)
        if not version:
            raise ValueError(f"SkillVersion {version_id} not found")
        if version.skill_id != skill.id:
            raise ValueError(f"Version {version_id} does not belong to skill {skill_id}")
        if version.quarantine_status == "quarantined" or version.status == "quarantined":
            raise ValueError(f"Cannot activate version {version_id} because it is quarantined. Unquarantine first.")
        if skill.status == "quarantined":
            raise ValueError(
                f"Cannot activate version for skill {skill.name} because the skill is quarantined. Unquarantine first."
            )

        now = datetime.now(timezone.utc)

        # Deactivate old active version if any
        if skill.active_version_id:
            old_version = await self.db.get(SkillVersion, skill.active_version_id)
            if old_version:
                old_version.status = "archived"
                old_version.superseded_at = now

        version.status = "active"
        version.activated_at = now
        version.quarantine_status = None
        version.quarantine_reason = None
        skill.active_version_id = version.id
        await self.db.commit()
        await self.db.refresh(version)

        # Immutable audit
        try:
            from shogun.services.immutable_audit import append

            append(
                event_id=str(uuid.uuid4()),
                event_category="skillopt",
                event_type="skillopt.local_candidate.activated",
                action=f"Activated version {version.version_number} for skill {skill.name}",
                severity="info",
                detail={
                    "skill_id": str(skill_id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                },
            )
        except Exception as exc:
            logger.warning("SkillOpt audit event could not be recorded (%s)", type(exc).__name__)

        return version

    async def quarantine_version(
        self,
        skill_id: uuid.UUID,
        reason: str,
        version_id: uuid.UUID | None = None,
    ) -> SkillVersion:
        """Quarantine a version of a skill due to regression or security policy failure."""
        skill = await self.db.get(Skill, skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        assert_skill_mutable(skill, "quarantine")

        if version_id:
            version = await self.db.get(SkillVersion, version_id)
            if not version:
                raise ValueError(f"SkillVersion {version_id} not found")
            if version.skill_id != skill.id:
                raise ValueError(f"Version {version_id} does not belong to skill {skill_id}")
        else:
            version = await self.get_active_version(skill_id)

        if not version:
            raise ValueError(f"No version found to quarantine for skill {skill_id}")

        version_metadata = dict(version.metadata_json or {})
        if version.quarantine_status != "quarantined":
            version_metadata["pre_quarantine_status"] = version.status
        version.metadata_json = version_metadata
        version.quarantine_status = "quarantined"
        version.quarantine_reason = reason
        version.status = "quarantined"

        if skill.active_version_id is None or skill.active_version_id == version.id:
            manifest = dict(skill.manifest or {})
            if skill.status != "quarantined":
                manifest["pre_quarantine_status"] = skill.status
            skill.manifest = manifest
            skill.status = "quarantined"

        await self.db.commit()
        await self.db.refresh(version)
        await self.db.refresh(skill)

        try:
            from shogun.services.immutable_audit import append

            append(
                event_id=str(uuid.uuid4()),
                event_category="skillopt",
                event_type="skillopt.local.quarantined",
                action=f"Skill version {version.version_number} quarantined: {reason}",
                severity="warning",
                detail={
                    "skill_id": str(skill_id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                    "reason": reason,
                },
            )
        except Exception as exc:
            logger.warning("SkillOpt audit event could not be recorded (%s)", type(exc).__name__)

        return version

    async def unquarantine_version(
        self,
        skill_id: uuid.UUID,
        version_id: uuid.UUID | None = None,
    ) -> SkillVersion:
        """Remove quarantine status from a version."""
        skill = await self.db.get(Skill, skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
        assert_skill_mutable(skill, "unquarantine")

        if version_id:
            version = await self.db.get(SkillVersion, version_id)
            if not version:
                raise ValueError(f"SkillVersion {version_id} not found")
            if version.skill_id != skill.id:
                raise ValueError(f"Version {version_id} does not belong to skill {skill_id}")
        else:
            version = await self.get_active_version(skill_id)

        if not version:
            raise ValueError(f"No version found to unquarantine for skill {skill_id}")

        if version.quarantine_status != "quarantined":
            return version

        version_metadata = dict(version.metadata_json or {})
        prior_version_status = version_metadata.pop(
            "pre_quarantine_status",
            "active" if skill.active_version_id == version.id else "archived",
        )
        version.metadata_json = version_metadata
        version.quarantine_status = None
        version.quarantine_reason = None
        version.status = prior_version_status

        if skill.active_version_id is None or skill.active_version_id == version.id:
            manifest = dict(skill.manifest or {})
            restored_status = manifest.pop("pre_quarantine_status", "installed")
            skill.manifest = manifest
            if skill.status == "quarantined":
                skill.status = restored_status or "installed"

        await self.db.commit()
        await self.db.refresh(version)
        await self.db.refresh(skill)

        try:
            from shogun.services.immutable_audit import append

            append(
                event_id=str(uuid.uuid4()),
                event_category="skillopt",
                event_type="skillopt.local.unquarantined",
                action=f"Skill version {version.version_number} unquarantined",
                severity="info",
                detail={
                    "skill_id": str(skill_id),
                    "version_id": str(version.id),
                    "version_number": version.version_number,
                },
            )
        except Exception as exc:
            logger.warning("SkillOpt audit event could not be recorded (%s)", type(exc).__name__)

        return version

    async def rollback_skill(
        self,
        skill_id: uuid.UUID,
        target_version_id: uuid.UUID | None = None,
        actor: str = "local-admin",
    ) -> dict:
        """Rollback skill to previous or target version with immutable audit."""
        from shogun.services.skill_rollback_service import SkillRollbackService

        rollback_svc = SkillRollbackService(self.db)
        result = await rollback_svc.rollback(skill_id, target_version_id=target_version_id)
        if result.get("status") == "success":
            try:
                from shogun.services.immutable_audit import append

                append(
                    event_id=str(uuid.uuid4()),
                    event_category="skillopt",
                    event_type="skillopt.local.rollback",
                    action=f"Rolled back skill {skill_id} to version {result.get('version_number')}",
                    severity="warning",
                    detail={
                        "skill_id": str(skill_id),
                        "target_version_id": str(target_version_id) if target_version_id else None,
                        "actor": actor,
                        "active_version_number": result.get("version_number"),
                    },
                )
            except Exception as exc:
                logger.warning("SkillOpt audit event could not be recorded (%s)", type(exc).__name__)
        return result

    async def get_active_with_staleness_check(
        self,
        skill_id: uuid.UUID,
    ) -> tuple[SkillVersion | None, list[dict]]:
        """Retrieve active version and check tool schema hashes for staleness (§20)."""
        active = await self.get_active_version(skill_id)
        if not active:
            return None, []

        saved_hashes = active.tool_schema_hashes_json or {}
        stale_warnings: list[dict] = []

        if saved_hashes:
            stmt = select(SkillOptToolSchemaVersion).where(
                SkillOptToolSchemaVersion.tool_name.in_(list(saved_hashes.keys()))
            )
            result = await self.db.execute(stmt)
            current_schemas = {ts.tool_name: ts for ts in result.scalars().all()}

            for tool_name, expected_hash in saved_hashes.items():
                current = current_schemas.get(tool_name)
                if current and current.schema_hash != expected_hash:
                    stale_warnings.append(
                        {
                            "tool_name": tool_name,
                            "expected_hash": expected_hash,
                            "current_hash": current.schema_hash,
                            "captured_at": current.captured_at.isoformat() if current.captured_at else None,
                            "warning": f"Tool schema '{tool_name}' has changed since this version was validated.",
                        }
                    )

        return active, stale_warnings
