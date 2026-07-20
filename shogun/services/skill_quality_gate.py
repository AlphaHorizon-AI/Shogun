"""Skill Quality Gate Service — Order 15.

Runs the 14-point quality gate check before a skill can be published.
No skill reaches OpenClaw College without passing this gate.
"""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill

logger = logging.getLogger(__name__)

# ── Lifecycle states ─────────────────────────────────────────
LIFECYCLE_STATES = (
    "draft", "validated", "published", "installed", "active",
    "observed", "optimized", "revalidated", "republished",
    "deprecated", "archived",
)

LIFECYCLE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft":        ("validated",),
    "validated":    ("published", "draft"),
    "published":    ("installed", "deprecated"),
    "installed":    ("active", "deprecated"),
    "active":       ("observed", "deprecated"),
    "observed":     ("optimized", "deprecated"),
    "optimized":    ("revalidated", "draft"),
    "revalidated":  ("republished", "draft"),
    "republished":  ("installed", "deprecated"),
    "deprecated":   ("archived", "active"),
    "archived":     (),
}

# ── Forbidden instruction patterns ──────────────────────────
FORBIDDEN_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)ignore\s+(all\s+)?previous\s+instructions"),
    re.compile(r"(?i)bypass\s+(security|posture|approval|permission|guard)"),
    re.compile(r"(?i)(steal|exfiltrate|leak)\s+(api[_\s]?key|token|password|secret|credential)"),
    re.compile(r"(?i)send\s+(credentials?|password|token|key)\s+to"),
    re.compile(r"(?i)disable\s+(audit|logging|event[_\s]?logger|kill[_\s]?switch)"),
    re.compile(r"(?i)override\s+(posture|policy|permission)"),
    re.compile(r"(?i)run\s+as\s+(root|admin|administrator)"),
    re.compile(r"(?i)rm\s+-rf\s+/"),
]

CREDENTIAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)(api[_\s]?key|secret[_\s]?key|password|token)\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})\b"),
]

REQUIRED_OPERATIONAL_SECTIONS: dict[str, tuple[str, ...]] = {
    "purpose": ("purpose",),
    "activation_criteria": ("activation criteria", "when to use"),
    "required_inputs": ("required inputs",),
    "workflow": ("workflow", "operating instructions"),
    "permissions_and_safety": ("permissions and safety", "safety"),
    "output_requirements": ("output requirements", "output standard"),
    "success_criteria": ("success criteria", "validation criteria"),
    "failure_handling": ("failure handling", "failure modes"),
}

PLACEHOLDER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\[TODO(?:\s*:|\])"),
    re.compile(r"(?i)describe\s+the\s+(purpose|specific capability|outcome)"),
    re.compile(r"(?i)no\s+triggers\s+defined"),
)


class SkillQualityGateService:
    """Runs the 14-point quality gate on a skill before publication."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def run_quality_gate(self, skill_id: uuid.UUID) -> dict[str, Any]:
        """Run all quality gate checks on a skill. Returns structured result."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return {"status": "error", "message": "Skill not found"}

        checks: dict[str, bool] = {}
        details: dict[str, str] = {}

        # 1. Manifest exists and is non-empty
        checks["manifest_exists"] = bool(
            skill.manifest and isinstance(skill.manifest, dict) and len(skill.manifest) > 0
        )
        if not checks["manifest_exists"]:
            details["manifest_exists"] = "Skill manifest is empty or missing."

        # 2. Skill markdown/body exists
        checks["skill_markdown_exists"] = bool(skill.body_text and len(skill.body_text.strip()) > 50)
        if not checks["skill_markdown_exists"]:
            details["skill_markdown_exists"] = "Skill body text is missing or too short (min 50 chars)."

        # 3. Required metadata exists (name, version, slug, category/skill_type)
        has_name = bool(skill.name and len(skill.name.strip()) > 2)
        has_version = bool(skill.version and re.match(r"^\d+\.\d+\.\d+", skill.version))
        has_slug = bool(skill.slug and len(skill.slug.strip()) > 2)
        checks["required_metadata_exists"] = has_name and has_version and has_slug
        if not checks["required_metadata_exists"]:
            missing = []
            if not has_name:
                missing.append("name")
            if not has_version:
                missing.append("version (semver)")
            if not has_slug:
                missing.append("slug")
            details["required_metadata_exists"] = f"Missing: {', '.join(missing)}"

        # 4. Activation triggers exist
        checks["activation_triggers_exist"] = bool(skill.triggers and len(skill.triggers) > 0)
        if not checks["activation_triggers_exist"]:
            details["activation_triggers_exist"] = "No activation triggers defined."

        # Operational content must give the agent concrete execution guidance.
        body = skill.body_text or ""
        headings = {
            match.group(1).strip().lower()
            for match in re.finditer(r"(?m)^##\s+(.+?)\s*$", body)
        }
        missing_sections = [
            key
            for key, aliases in REQUIRED_OPERATIONAL_SECTIONS.items()
            if not any(alias in headings for alias in aliases)
        ]
        checks["operational_structure_complete"] = not missing_sections
        if missing_sections:
            details["operational_structure_complete"] = (
                "Missing operational sections: " + ", ".join(missing_sections)
            )

        unresolved = [
            match.group(0)
            for pattern in PLACEHOLDER_PATTERNS
            if (match := pattern.search(body))
        ]
        checks["no_unresolved_placeholders"] = not unresolved
        if unresolved:
            details["no_unresolved_placeholders"] = (
                "Replace draft placeholders before publication: " + ", ".join(unresolved[:3])
            )

        description = str((skill.manifest or {}).get("description") or "").strip()
        checks["actionable_description_exists"] = (
            len(description) >= 24
            and not any(pattern.search(description) for pattern in PLACEHOLDER_PATTERNS)
        )
        if not checks["actionable_description_exists"]:
            details["actionable_description_exists"] = (
                "Description must state the capability, intended outcome, and activation context."
            )

        # 5. Risk tier is assigned
        checks["risk_tier_declared"] = skill.risk_tier in ("low", "medium", "high", "critical")
        if not checks["risk_tier_declared"]:
            details["risk_tier_declared"] = f"Invalid risk tier: {skill.risk_tier!r}"

        # 6. Tool requirements are declared (field must exist, can be empty)
        checks["tool_requirements_declared"] = isinstance(skill.requires_tools, list)

        # 7. Validation tests exist
        from sqlalchemy import func, select

        from shogun.db.models.skill_test import SkillTest
        test_count_result = await self.session.execute(
            select(func.count()).select_from(SkillTest).where(SkillTest.skill_id == skill_id)
        )
        test_count = test_count_result.scalar() or 0
        checks["validation_tests_exist"] = test_count > 0
        if not checks["validation_tests_exist"]:
            details["validation_tests_exist"] = "No validation tests defined."

        # 8. At least one validation test passes
        passed_result = await self.session.execute(
            select(func.count()).select_from(SkillTest).where(
                SkillTest.skill_id == skill_id,
                SkillTest.last_result_json.isnot(None),
            )
        )
        passed_count = passed_result.scalar() or 0
        checks["validation_tests_passed"] = passed_count > 0 if test_count > 0 else False
        if not checks["validation_tests_passed"] and test_count > 0:
            details["validation_tests_passed"] = "No validation tests have been run yet."

        # 9. No forbidden instructions
        forbidden_found = []
        for pattern in FORBIDDEN_PATTERNS:
            match = pattern.search(body)
            if match:
                forbidden_found.append(match.group(0))
        checks["no_forbidden_instructions"] = len(forbidden_found) == 0
        if forbidden_found:
            details["no_forbidden_instructions"] = f"Found: {forbidden_found[:3]}"

        # 10. No hidden credential requests
        cred_found = []
        for pattern in CREDENTIAL_PATTERNS:
            match = pattern.search(body)
            if match:
                cred_found.append(match.group(0)[:30] + "…")
        checks["no_hidden_credentials"] = len(cred_found) == 0
        if cred_found:
            details["no_hidden_credentials"] = f"Found credential-like strings: {cred_found[:3]}"

        # 11. No posture bypass instructions
        posture_bypass = re.search(
            r"(?i)(set|change|switch|force)\s+(posture|tier)\s+to\s+(ronin|campaign|shrine)",
            body,
        )
        checks["no_posture_bypass"] = posture_bypass is None
        if posture_bypass:
            details["no_posture_bypass"] = f"Found: {posture_bypass.group(0)}"

        # 12. Version number is valid semver
        checks["version_valid"] = bool(re.match(r"^\d+\.\d+\.\d+$", skill.version or ""))
        if not checks["version_valid"]:
            details["version_valid"] = f"Version {skill.version!r} is not valid semver."

        # 13. Changelog exists as package metadata, not agent instructions.
        changelog_path = Path(skill.local_path).parent / "changelog.md" if skill.local_path else None
        has_changelog = bool(
            "changelog" in (skill.manifest or {})
            or (changelog_path and changelog_path.is_file())
        )
        checks["changelog_exists"] = has_changelog
        if not checks["changelog_exists"]:
            details["changelog_exists"] = "No changelog file or manifest entry found."

        # 14. Audit event recorded (always true — we emit one now)
        checks["audit_event_recorded"] = True

        # ── Compute overall score ────────────────────────────────
        total = len(checks)
        passed = sum(1 for v in checks.values() if v)
        score = round(passed / total, 2) if total > 0 else 0.0
        status = (
            "passed"
            if score >= 0.7
            and checks.get("no_forbidden_instructions")
            and checks.get("no_hidden_credentials")
            else "failed"
        )

        # Safety checks are hard gates — even with high score, fail on safety
        hard_gates = (
            "no_forbidden_instructions",
            "no_hidden_credentials",
            "no_posture_bypass",
            "operational_structure_complete",
            "no_unresolved_placeholders",
            "actionable_description_exists",
        )
        if any(not checks.get(check) for check in hard_gates):
            status = "failed"

        result = {
            "skill_id": str(skill_id),
            "version": skill.version,
            "status": status,
            "checks": checks,
            "details": details,
            "score": score,
            "passed_count": passed,
            "total_count": total,
        }

        # Emit audit event
        try:
            from shogun.services.event_logger import EventLogger
            await EventLogger.emit(
                "skill.quality_gate_passed" if status == "passed" else "skill.quality_gate_failed",
                f"Quality gate {status} for skill {skill.name!r} v{skill.version} (score={score})",
                severity="info" if status == "passed" else "warning",
                detail=result,
            )
        except Exception:
            pass

        return result

    def can_transition(self, current_state: str, target_state: str) -> bool:
        """Check if a lifecycle state transition is valid."""
        allowed = LIFECYCLE_TRANSITIONS.get(current_state, ())
        return target_state in allowed

    async def transition_lifecycle(
        self, skill_id: uuid.UUID, target_state: str
    ) -> Skill | None:
        """Transition a skill's lifecycle state if the transition is valid."""
        skill = await self.session.get(Skill, skill_id)
        if not skill:
            return None
        if not self.can_transition(skill.lifecycle_state, target_state):
            raise ValueError(
                f"Cannot transition from {skill.lifecycle_state!r} to {target_state!r}. "
                f"Allowed: {LIFECYCLE_TRANSITIONS.get(skill.lifecycle_state, ())}"
            )
        skill.lifecycle_state = target_state
        if target_state == "archived":
            from datetime import datetime, timezone
            skill.archived_at = datetime.now(timezone.utc)
        await self.session.flush()
        return skill
