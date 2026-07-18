"""Skill Authoring Service — Order 15.

Supports creating skill drafts, generating manifests, validation tests,
and changelogs. This is the entry point for the content loop.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.skill import Skill
from shogun.db.models.skill_test import SkillTest
from shogun.db.models.skillopt import SkillVersion
from shogun.services.base_service import BaseService

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "_", text)
    return text[:100]


class SkillAuthoringService:
    """Create skill drafts with the full Order 15 package structure."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_skill_draft(
        self,
        *,
        name: str,
        category: str = "general",
        description: str = "",
        body_text: str = "",
        triggers: list[str] | None = None,
        risk_tier: str = "low",
        requires_tools: list[str] | None = None,
        optional_tools: list[str] | None = None,
        tags: list[str] | None = None,
        version: str = "1.0.0",
        author: str = "operator",
    ) -> dict[str, Any]:
        """Create a new skill in draft state with v1 version record."""
        slug = _slugify(name)

        # Check for duplicate
        from sqlalchemy import select
        existing = await self.session.execute(
            select(Skill).where(Skill.slug == slug, Skill.is_deleted == False)
        )
        if existing.scalars().first():
            raise ValueError(f"A skill with slug {slug!r} already exists.")

        # Build manifest
        manifest = {
            "skill_id": f"{slug}_v1",
            "name": name,
            "version": version,
            "description": description,
            "category": category,
            "author": author,
            "source": "shogun_authored",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "minimum_shogun_version": "0.0.0",
            "risk_tier": risk_tier,
            "required_tools": requires_tools or [],
            "optional_tools": optional_tools or [],
            "activation_triggers": triggers or [],
            "tags": tags or [],
            "validation_status": "pending",
            "publication_status": "draft",
        }

        # Build default body_text if not provided
        if not body_text.strip():
            body_text = self._generate_default_body(
                name=name,
                description=description,
                triggers=triggers or [],
                risk_tier=risk_tier,
            )

        # Create skill record
        skill = Skill(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            version=version,
            skill_type="single",
            manifest=manifest,
            status="available",
            risk_tier=risk_tier,
            triggers=triggers or [],
            requires_tools=requires_tools or [],
            tags=tags or [],
            body_text=body_text,
            lifecycle_state="draft",
            publication_status="unpublished",
        )
        self.session.add(skill)
        await self.session.flush()
        await self.session.refresh(skill)

        # Save skill.md to disk
        skill_dir = settings.vault_path / "skills" / "authored" / slug
        os.makedirs(skill_dir, exist_ok=True)

        skill_md_path = str(skill_dir / "skill.md")
        with open(skill_md_path, "w", encoding="utf-8") as f:
            f.write(body_text)
        skill.local_path = skill_md_path

        # Save manifest.json
        manifest_path = str(skill_dir / "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Create initial changelog
        changelog_path = str(skill_dir / "changelog.md")
        with open(changelog_path, "w", encoding="utf-8") as f:
            f.write(f"# Changelog — {name}\n\n")
            f.write(f"## {version} ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})\n\n")
            f.write("- Initial draft created.\n")

        # Create SkillVersion v1
        content_hash = hashlib.sha256(body_text.encode()).hexdigest()
        version_record = SkillVersion(
            id=uuid.uuid4(),
            skill_id=skill.id,
            version_number=1,
            status="active",
            content_path=skill_md_path,
            content_hash=content_hash,
            created_by=author,
        )
        self.session.add(version_record)
        await self.session.flush()

        skill.active_version_id = version_record.id
        await self.session.flush()

        # Emit audit event
        try:
            from shogun.services.event_logger import EventLogger
            await EventLogger.emit(
                "skill.created",
                f"Skill draft created: {name!r} v{version}",
                severity="info",
                detail={"skill_id": str(skill.id), "slug": slug, "version": version},
            )
        except Exception:
            pass

        return {
            "skill_id": str(skill.id),
            "slug": slug,
            "name": name,
            "version": version,
            "lifecycle_state": "draft",
            "version_id": str(version_record.id),
            "local_path": skill_md_path,
        }

    async def generate_validation_tests(
        self, skill_id: uuid.UUID, tests: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """Create SkillTest records for a skill. If no tests provided, generate defaults from verification_checklist."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            raise ValueError("Skill not found")

        test_defs = tests or []

        # Auto-generate from verification_checklist if no tests provided
        if not test_defs and skill.verification_checklist:
            for i, check_item in enumerate(skill.verification_checklist):
                test_defs.append({
                    "id": f"test_{skill.slug}_{i+1:03d}",
                    "skill_id": str(skill_id),
                    "test_type": "checklist",
                    "input": {"check": check_item},
                    "expected": {"passes": True},
                })

        # If still no tests, generate a basic output_quality test
        if not test_defs:
            test_defs.append({
                "id": f"test_{skill.slug}_001",
                "skill_id": str(skill_id),
                "test_type": "output_quality",
                "input": {
                    "user_request": f"Use the {skill.name} skill on a sample task.",
                },
                "expected": {
                    "must_include": [],
                    "must_not_include": ["error", "cannot", "unable"],
                },
                "scoring": {
                    "pass_threshold": 0.70,
                    "criteria": {"relevance": 0.40, "safety": 0.30, "concision": 0.30},
                },
            })

        created = []
        for test_def in test_defs:
            record = SkillTest(
                id=uuid.uuid4(),
                skill_id=skill_id,
                version=skill.version,
                test_type=test_def.get("test_type", "output_quality"),
                test_definition_json=test_def,
            )
            self.session.add(record)
            created.append({
                "test_id": str(record.id),
                "test_type": record.test_type,
                "definition": test_def,
            })

        await self.session.flush()
        return created

    async def generate_manifest(self, skill_id: uuid.UUID) -> dict[str, Any]:
        """Regenerate and return the manifest for a skill."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            raise ValueError("Skill not found")

        manifest = {
            "skill_id": f"{skill.slug}_v{skill.version.replace('.', '_')}",
            "name": skill.name,
            "version": skill.version,
            "description": skill.brief_text or "",
            "category": skill.skill_type,
            "author": (skill.manifest or {}).get("author", "operator"),
            "source": (skill.manifest or {}).get("source", "shogun_authored"),
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
            "minimum_shogun_version": "0.0.0",
            "risk_tier": skill.risk_tier,
            "required_tools": skill.requires_tools or [],
            "activation_triggers": skill.triggers or [],
            "tags": skill.tags or [],
            "validation_status": skill.lifecycle_state,
            "publication_status": skill.publication_status,
            "license": "OpenClaw College Skill License",
        }
        skill.manifest = manifest
        await self.session.flush()
        return manifest

    def _generate_default_body(
        self, *, name: str, description: str, triggers: list[str], risk_tier: str
    ) -> str:
        """Generate a default skill.md body."""
        trigger_lines = "\n".join(f"  - {t}" for t in triggers) if triggers else "  - (no triggers defined)"
        return f"""---
name: {name}
version: 1.0.0
category: general
risk_tier: {risk_tier}
activation_triggers:
{trigger_lines}
required_tools: []
---

# Skill: {name}

## Purpose

{description or 'Describe the purpose of this skill.'}

## When To Use

Use when the user asks to perform tasks related to this skill's domain.

## Operating Instructions

1. Understand the user's request.
2. Apply the skill's domain knowledge.
3. Produce a clear, actionable result.
4. Verify the output meets quality standards.

## Output Standard

The output should be:

- clear
- accurate
- actionable
- concise

## Failure Modes

Avoid:

- inventing unsupported details
- exceeding scope
- sending without approval

## Validation Criteria

The skill passes if the output:

- addresses the user's request
- preserves factual accuracy
- uses appropriate tone
- is concise and usable

## Changelog

## 1.0.0

- Initial draft created.
"""
