"""Skill Publishing Service — Order 15.

Abstracts skill publishing behind a provider interface.
Ships with LocalFolderProvider (always available) and a stub
OpenClawCollegeProvider that packages for future API integration.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.skill import Skill
from shogun.db.models.skill_publication import SkillPublication
from shogun.db.models.skill_test import SkillTest
from shogun.services.skill_quality_gate import SkillQualityGateService

logger = logging.getLogger(__name__)


# ── Provider abstraction ─────────────────────────────────────

class PublishResult:
    """Result of a publish operation."""

    def __init__(
        self,
        *,
        success: bool,
        provider: str,
        published_url: str | None = None,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self.success = success
        self.provider = provider
        self.published_url = published_url
        self.message = message
        self.metadata = metadata or {}


class SkillPublishingProvider(ABC):
    """Abstract base for skill publishing destinations."""

    name: str = "base"

    @abstractmethod
    async def publish(self, package_path: Path, manifest: dict[str, Any]) -> PublishResult:
        """Publish a packaged skill to this provider."""
        ...


class LocalFolderProvider(SkillPublishingProvider):
    """Publishes skills to a local folder under data/skills/published/."""

    name = "local"

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or (settings.vault_path / "skills" / "published")

    async def publish(self, package_path: Path, manifest: dict[str, Any]) -> PublishResult:
        """Copy packaged skill to the local published directory."""
        skill_id = manifest.get("skill_id", "unknown")
        version = manifest.get("version", "0.0.0")
        dest = self.base_dir / skill_id / version

        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(package_path, dest)

            published_url = f"file://{dest.as_posix()}"
            logger.info("Published %s v%s to %s", skill_id, version, dest)
            return PublishResult(
                success=True,
                provider=self.name,
                published_url=published_url,
                message=f"Published to local folder: {dest}",
                metadata={"destination": str(dest)},
            )
        except Exception as exc:
            logger.error("Local publish failed: %s", exc)
            return PublishResult(
                success=False,
                provider=self.name,
                message=f"Local publish failed: {exc}",
            )


class OpenClawCollegeProvider(SkillPublishingProvider):
    """Publishes skills to OpenClaw College.

    Currently packages the skill locally and logs the publish intent.
    Will be wired to the real OpenClaw College publish API when available.
    """

    name = "openclaw_college"

    def __init__(self):
        self._local = LocalFolderProvider()

    async def publish(self, package_path: Path, manifest: dict[str, Any]) -> PublishResult:
        """Publish to OpenClaw College (currently falls back to local)."""
        # TODO: Wire to real OpenClaw College publish API when endpoint is available
        # For now, publish locally and mark as openclaw_college provider
        result = await self._local.publish(package_path, manifest)
        result.provider = self.name
        if result.success:
            result.message = (
                f"Packaged for OpenClaw College (stored locally pending API). "
                f"URL: {result.published_url}"
            )
        return result


# ── Provider registry ────────────────────────────────────────

PROVIDERS: dict[str, type[SkillPublishingProvider]] = {
    "local": LocalFolderProvider,
    "openclaw_college": OpenClawCollegeProvider,
}


def get_provider(name: str = "local") -> SkillPublishingProvider:
    """Get a publishing provider by name."""
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown publishing provider: {name!r}. Available: {list(PROVIDERS)}")
    return cls()


# ── Publishing Service ───────────────────────────────────────

class SkillPublishingService:
    """Orchestrates skill packaging, quality gate, and publishing."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def package_skill(self, skill_id: uuid.UUID) -> Path:
        """Package a skill into the standard folder structure for publishing.

        Returns the path to the package directory.
        """
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            raise ValueError("Skill not found")

        package_dir = settings.vault_path / "skills" / "packages" / skill.slug / skill.version
        os.makedirs(package_dir, exist_ok=True)

        # 1. Write the portable skill entrypoint.
        skill_md_path = package_dir / "SKILL.md"
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(skill.body_text or "")

        # 2. Write manifest.json
        manifest_path = package_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(skill.manifest or {}, f, indent=2, default=str)

        # 3. Write tests
        tests_dir = package_dir / "tests"
        os.makedirs(tests_dir, exist_ok=True)
        test_results = await self.session.execute(
            select(SkillTest).where(SkillTest.skill_id == skill_id)
        )
        for i, test in enumerate(test_results.scalars().all()):
            test_path = tests_dir / f"test_{i+1:03d}.json"
            with open(test_path, "w", encoding="utf-8") as f:
                json.dump(test.test_definition_json, f, indent=2, default=str)

        # 4. Write changelog (from authored dir if available)
        authored_changelog = settings.vault_path / "skills" / "authored" / skill.slug / "changelog.md"
        changelog_path = package_dir / "changelog.md"
        if authored_changelog.exists():
            shutil.copy2(authored_changelog, changelog_path)
        elif not changelog_path.exists():
            with open(changelog_path, "w", encoding="utf-8") as f:
                f.write(f"# Changelog — {skill.name}\n\n## {skill.version}\n\n- Packaged for publishing.\n")

        # 5. Write metrics.json
        metrics_path = package_dir / "metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump({
                "skill_id": str(skill.id),
                "version": skill.version,
                "usage_count": skill.usage_count,
                "success_count": skill.success_count,
                "failure_count": skill.failure_count,
            }, f, indent=2)

        logger.info("Packaged skill %s v%s at %s", skill.slug, skill.version, package_dir)
        return package_dir

    async def publish(
        self,
        skill_id: uuid.UUID,
        *,
        provider_name: str = "local",
        skip_quality_gate: bool = False,
    ) -> dict[str, Any]:
        """Run quality gate (unless skipped), package, and publish a skill."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        # Run quality gate
        if not skip_quality_gate:
            gate = SkillQualityGateService(self.session)
            gate_result = await gate.run_quality_gate(skill_id)
            if gate_result["status"] != "passed":
                skill.lifecycle_state = "draft"
                await self.session.flush()
                return {
                    "status": "quality_gate_failed",
                    "message": "Skill did not pass quality gate.",
                    "quality_gate": gate_result,
                }

        # Package
        package_dir = await self.package_skill(skill_id)

        # Publish
        provider = get_provider(provider_name)
        result = await provider.publish(package_dir, skill.manifest or {})

        # Record publication
        now = datetime.now(timezone.utc)
        publication = SkillPublication(
            id=uuid.uuid4(),
            skill_id=skill_id,
            version=skill.version,
            provider=provider_name,
            published_url=result.published_url,
            publication_status="published" if result.success else "failed",
            published_at=now if result.success else None,
            response_json=result.metadata,
        )
        self.session.add(publication)

        # Update skill state
        if result.success:
            skill.publication_status = "published"
            skill.published_at = now
            if skill.lifecycle_state in ("draft", "validated", "revalidated"):
                skill.lifecycle_state = "published"

        await self.session.flush()

        # Emit audit event
        try:
            from shogun.services.event_logger import EventLogger
            event_name = "skill.published" if result.success else "skill.publish_failed"
            await EventLogger.emit(
                event_name,
                f"Skill {skill.name!r} v{skill.version} → {provider_name}: {result.message}",
                severity="info" if result.success else "warning",
                detail={
                    "skill_id": str(skill_id),
                    "provider": provider_name,
                    "published_url": result.published_url,
                },
            )
        except Exception:
            pass

        return {
            "status": "published" if result.success else "failed",
            "message": result.message,
            "provider": provider_name,
            "published_url": result.published_url,
            "publication_id": str(publication.id),
        }

    async def republish(
        self,
        skill_id: uuid.UUID,
        *,
        provider_name: str = "local",
    ) -> dict[str, Any]:
        """Republish an optimized/revalidated skill as a new version."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        if skill.lifecycle_state not in ("revalidated", "optimized", "validated", "published"):
            return {
                "status": "error",
                "message": f"Cannot republish from state {skill.lifecycle_state!r}. "
                           "Must be revalidated, optimized, or validated.",
            }

        result = await self.publish(skill_id, provider_name=provider_name)
        if result.get("status") == "published":
            skill.lifecycle_state = "republished"
            await self.session.flush()

            try:
                from shogun.services.event_logger import EventLogger
                await EventLogger.emit(
                    "skill.republished",
                    f"Skill {skill.name!r} v{skill.version} republished to {provider_name}",
                    severity="info",
                )
            except Exception:
                pass

        return result
