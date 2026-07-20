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
        use_when: list[str] | None = None,
        avoid_when: list[str] | None = None,
        required_inputs: list[str] | None = None,
        workflow_steps: list[str] | None = None,
        decision_rules: list[str] | None = None,
        output_requirements: list[str] | None = None,
        success_criteria: list[str] | None = None,
        failure_handling: list[str] | None = None,
        example_input: str = "",
        example_output: str = "",
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
            select(Skill).where(Skill.slug == slug, Skill.is_deleted.is_(False))
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
            "triggers": triggers or [],
            "use_when": use_when or [],
            "avoid_when": avoid_when or [],
            "required_inputs": required_inputs or [],
            "workflow_steps": workflow_steps or [],
            "decision_rules": decision_rules or [],
            "output_requirements": output_requirements or [],
            "success_criteria": success_criteria or [],
            "failure_handling": failure_handling or [],
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
                use_when=use_when or [],
                avoid_when=avoid_when or [],
                required_inputs=required_inputs or [],
                workflow_steps=workflow_steps or [],
                decision_rules=decision_rules or [],
                output_requirements=output_requirements or [],
                success_criteria=success_criteria or [],
                failure_handling=failure_handling or [],
                example_input=example_input,
                example_output=example_output,
                risk_tier=risk_tier,
                requires_tools=requires_tools or [],
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
            use_when=use_when or [],
            avoid_when=avoid_when or [],
            requires_tools=requires_tools or [],
            tags=tags or [],
            body_text=body_text,
            verification_checklist=success_criteria or [],
            lifecycle_state="draft",
            publication_status="unpublished",
        )
        self.session.add(skill)
        await self.session.flush()
        await self.session.refresh(skill)

        # Save the portable skill entrypoint to disk.
        skill_dir = settings.vault_path / "skills" / "authored" / slug
        os.makedirs(skill_dir, exist_ok=True)

        skill_md_path = str(skill_dir / "SKILL.md")
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
                    "must_not_include": [],
                },
                "scoring": {
                    "pass_threshold": 0.70,
                    "criteria": {
                        "workflow_adherence": 0.35,
                        "success_criteria_verification": 0.35,
                        "safety": 0.20,
                        "output_format": 0.10,
                    },
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

        existing_manifest = skill.manifest or {}
        manifest = {
            "skill_id": f"{skill.slug}_v{skill.version.replace('.', '_')}",
            "name": skill.name,
            "version": skill.version,
            "description": existing_manifest.get("description") or skill.brief_text or "",
            "category": skill.skill_type,
            "author": existing_manifest.get("author", "operator"),
            "source": existing_manifest.get("source", "shogun_authored"),
            "created_at": skill.created_at.isoformat() if skill.created_at else None,
            "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
            "minimum_shogun_version": "0.0.0",
            "risk_tier": skill.risk_tier,
            "required_tools": skill.requires_tools or [],
            "activation_triggers": skill.triggers or [],
            "triggers": skill.triggers or [],
            "use_when": skill.use_when or [],
            "avoid_when": skill.avoid_when or [],
            "required_inputs": existing_manifest.get("required_inputs", []),
            "workflow_steps": existing_manifest.get("workflow_steps", []),
            "decision_rules": existing_manifest.get("decision_rules", []),
            "output_requirements": existing_manifest.get("output_requirements", []),
            "success_criteria": skill.verification_checklist or existing_manifest.get("success_criteria", []),
            "failure_handling": existing_manifest.get("failure_handling", []),
            "tags": skill.tags or [],
            "validation_status": skill.lifecycle_state,
            "publication_status": skill.publication_status,
            "license": "OpenClaw College Skill License",
        }
        skill.manifest = manifest
        await self.session.flush()
        return manifest

    def _generate_default_body(
        self,
        *,
        name: str,
        description: str,
        triggers: list[str],
        use_when: list[str],
        avoid_when: list[str],
        required_inputs: list[str],
        workflow_steps: list[str],
        decision_rules: list[str],
        output_requirements: list[str],
        success_criteria: list[str],
        failure_handling: list[str],
        example_input: str,
        example_output: str,
        risk_tier: str,
        requires_tools: list[str],
    ) -> str:
        """Generate an operational skill draft with explicit authoring gaps."""

        def bullets(items: list[str], placeholder: str) -> str:
            values = [item.strip() for item in items if item and item.strip()]
            if not values:
                return f"- [TODO: {placeholder}]"
            return "\n".join(f"- {item}" for item in values)

        def numbered(items: list[str], placeholder: str) -> str:
            values = [item.strip() for item in items if item and item.strip()]
            if not values:
                return f"1. [TODO: {placeholder}]"
            return "\n".join(f"{index}. {item}" for index, item in enumerate(values, 1))

        activation = use_when or triggers
        safe_name = json.dumps(name, ensure_ascii=False)
        activation_summary = "; ".join(item.strip() for item in activation if item.strip())
        portable_description = description.strip()
        if portable_description and activation_summary:
            portable_description = f"{portable_description} Use when: {activation_summary}"
        safe_description = json.dumps(
            portable_description or f"[TODO: Describe the outcome and activation context for {name}.]",
            ensure_ascii=False,
        )
        tool_section = ""
        if requires_tools:
            tool_instructions = [
                f"Use `{tool}` only for the operation it is registered to perform."
                for tool in requires_tools
            ]
            tool_section = f"""
## Tool and resource usage

{bullets(tool_instructions, 'Identify required tools or remove this section.')}

Resolve relative resource paths from the directory containing this `SKILL.md`.
"""
        return f"""---
name: {safe_name}
description: {safe_description}
---

# {name}

## Purpose

{description.strip() or f'[TODO: Describe the specific capability and outcome produced by {name}.]'}

## Activation criteria

Use this skill when:

{bullets(activation, 'List concrete requests, inputs, or conditions that activate this skill.')}

Do not use this skill when:

{bullets(avoid_when, 'List adjacent tasks that belong elsewhere or conditions that make this skill unsuitable.')}

## Required inputs

Identify and validate:

{bullets(
    required_inputs,
    'List the files, records, parameters, constraints, approvals, and desired output format required for execution.',
)}

Apply a safe default when a missing detail does not materially affect the result. Ask the user only when the
missing information changes the outcome or introduces unacceptable risk.

## Workflow

{numbered(workflow_steps, 'Write the domain-specific execution sequence, including inspection and verification.')}

## Decision rules

{bullets(
    decision_rules,
    'Document the choices, thresholds, precedence rules, and safe defaults that materially affect execution.',
)}
{tool_section}
## Permissions and safety

- Treat this as a `{risk_tier}`-risk skill.
- Do not expand the requested scope or treat this skill as granting tools or permissions.
- Preserve existing user content unless modification is required by the requested outcome.
- Require explicit authorization before external communication or destructive, irreversible action.
- Never expose credentials or secrets in output or logs.
- Respect the active Shogun posture and all tool-risk controls.

## Output requirements

{bullets(output_requirements, 'Specify the required artifact, format, location, schema, tone, and completion summary.')}

## Success criteria

The task is complete only when:

{bullets(success_criteria, 'Define observable checks that prove the requested outcome is complete and correct.')}

## Failure handling

{bullets(
    failure_handling,
    'Describe safe recovery, retry limits, state preservation, and what to report when completion is blocked.',
)}

## Example

Input:

{example_input.strip() or '[TODO: Add a representative user request.]'}

Expected behaviour:

- Follow the workflow and decision rules above.
- Verify the result against every success criterion.

Expected output:

{example_output.strip() or '[TODO: Add a representative final result or artifact description.]'}
"""
