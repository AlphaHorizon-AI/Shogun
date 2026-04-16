"""Kaizen API — Constitution and Mandate governance endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shogun.config import settings
from shogun.db.engine import async_session_factory
from shogun.db.models.kaizen_revision import KaizenRevision
from shogun.schemas.common import ApiResponse
from sqlalchemy import select, func, desc

router = APIRouter(prefix="/kaizen", tags=["Kaizen"])

# ── File paths ─────────────────────────────────────────────────
CONSTITUTION_PATH = Path(settings.config_path) / "constitution.yaml"
MANDATE_PATH = Path(settings.config_path) / "mandate.md"

# ── Default content ───────────────────────────────────────────

DEFAULT_CONSTITUTION = """\
# SHOGUN SYSTEM CONSTITUTION
# --- Global Behavioral Principles ---

core_directives:
  - id: zero_harm
    rule: "Operations must not compromise host system integrity."
    severity: CRITICAL

  - id: transparency
    rule: "All autonomous spawns must be logged to the Torii registry."
    severity: HIGH

  - id: human_oversight
    rule: "No irreversible actions without human approval."
    severity: BALANCED

autonomy_limits:
  max_recursion_depth: 3
  prohibited_tools:
    - shell_rm_root
    - network_sniffing
  approval_required: true

data_sovereignty:
  retention_policy: episodic_decay
  privacy_tier: maximal
"""

DEFAULT_MANDATE = """\
# The Mandate

## Title
**Shogun — Primary Orchestrator**

## Assigned To
**Shogun**

## Mandate Statement

You are the primary orchestrating AI of the Shogun platform.

Your responsibility is to ensure that all operations, agents, and workflows are coordinated, efficient, and aligned with the operator's objectives.

---

## Core Objective

Maintain operational excellence across the Samurai network. Ensure that sub-agents are effectively deployed, monitored, and guided toward their assigned tasks.

---

## Areas of Responsibility

### 1. Agent Coordination
- Monitor Samurai agent health and performance
- Recommend task assignments based on agent capabilities
- Flag underperforming or idle agents for review

### 2. Quality Assurance
- Ensure task outputs meet quality standards
- Identify and escalate issues proactively
- Maintain consistency across agent behaviors

### 3. Operational Integrity
- Follow the constitutional directives at all times
- Respect security policies and approval gates
- Log all significant decisions and actions

---

## Operating Principles

### Relevance over volume
Focus on meaningful work, not busy work.

### Clarity over complexity
Communicate clearly and concisely.

### Stewardship over passivity
Proactively maintain the system, don't merely observe.

### Trust over hype
Reliability and consistency build trust.

---

## Success Conditions

You succeed when:
- The Samurai network operates smoothly and efficiently
- Tasks are completed to standard and on time
- Issues are identified before they become problems
- The operator has confidence in the system's reliability
"""


# ── Helpers ────────────────────────────────────────────────────

def _ensure_file(path: Path, default_content: str) -> str:
    """Read file content, creating with defaults if missing."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(default_content, encoding="utf-8")
        return default_content
    return path.read_text(encoding="utf-8")


def _validate_yaml(content: str) -> tuple[bool, str | None]:
    """Validate YAML syntax. Returns (is_valid, error_message)."""
    try:
        yaml.safe_load(content)
        return True, None
    except yaml.YAMLError as exc:
        return False, str(exc)


def _extract_key_rules(content: str) -> list[dict]:
    """Extract core_directives from constitution YAML for system prompt injection."""
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return []
        directives = data.get("core_directives", [])
        if not isinstance(directives, list):
            return []
        return [
            {"id": d.get("id", "unknown"), "rule": d.get("rule", ""), "severity": d.get("severity", "MEDIUM")}
            for d in directives
            if isinstance(d, dict)
        ]
    except Exception:
        return []


def _extract_mandate_summary(content: str, max_lines: int = 30) -> str:
    """Extract the first N meaningful lines of the mandate for prompt injection."""
    lines = content.strip().splitlines()
    # Take the mandate statement and core objective sections
    summary_lines = []
    for line in lines[:80]:
        summary_lines.append(line)
        if len(summary_lines) >= max_lines:
            break
    return "\n".join(summary_lines)


# ── Public helper for chat prompt injection ────────────────────

def get_governance_context() -> dict:
    """Return key rules and mandate summary for system prompt injection.
    
    Called by the Shogun chat handler to inject governance context.
    """
    constitution_content = _ensure_file(CONSTITUTION_PATH, DEFAULT_CONSTITUTION)
    mandate_content = _ensure_file(MANDATE_PATH, DEFAULT_MANDATE)

    key_rules = _extract_key_rules(constitution_content)
    mandate_summary = _extract_mandate_summary(mandate_content)

    rules_text = "\n".join(
        f"  - [{r['severity']}] {r['rule']}" for r in key_rules
    ) if key_rules else "  (no directives defined)"

    return {
        "rules_text": rules_text,
        "mandate_summary": mandate_summary,
    }


# ── Constitution endpoints ─────────────────────────────────────

class ConstitutionBody(BaseModel):
    content: str
    change_summary: str = "Updated constitution"


@router.get("/constitution", response_model=ApiResponse)
async def get_constitution():
    """Load constitution.yaml from disk."""
    content = _ensure_file(CONSTITUTION_PATH, DEFAULT_CONSTITUTION)
    is_valid, error = _validate_yaml(content)
    return ApiResponse(data={
        "content": content,
        "valid": is_valid,
        "error": error,
        "path": str(CONSTITUTION_PATH),
    })


@router.put("/constitution", response_model=ApiResponse)
async def save_constitution(body: ConstitutionBody):
    """Save constitution.yaml to disk and create a revision."""
    is_valid, error = _validate_yaml(body.content)
    if not is_valid:
        raise HTTPException(status_code=422, detail=f"Invalid YAML: {error}")

    # Write to disk
    CONSTITUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONSTITUTION_PATH.write_text(body.content, encoding="utf-8")

    # Create revision record
    async with async_session_factory() as session:
        # Get next version
        result = await session.execute(
            select(func.max(KaizenRevision.version))
            .where(KaizenRevision.document_type == "constitution")
        )
        max_ver = result.scalar() or 0
        
        revision = KaizenRevision(
            document_type="constitution",
            version=max_ver + 1,
            change_summary=body.change_summary,
            content_snapshot=body.content,
        )
        session.add(revision)
        await session.commit()

    return ApiResponse(data={
        "content": body.content,
        "valid": True,
        "version": max_ver + 1,
        "message": "Constitutional rules synchronized across the network.",
    })


# ── Mandate endpoints ──────────────────────────────────────────

class MandateBody(BaseModel):
    content: str
    change_summary: str = "Updated mandate"


@router.get("/mandate", response_model=ApiResponse)
async def get_mandate():
    """Load mandate.md from disk."""
    content = _ensure_file(MANDATE_PATH, DEFAULT_MANDATE)
    return ApiResponse(data={
        "content": content,
        "path": str(MANDATE_PATH),
    })


@router.put("/mandate", response_model=ApiResponse)
async def save_mandate(body: MandateBody):
    """Save mandate.md to disk and create a revision."""
    MANDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANDATE_PATH.write_text(body.content, encoding="utf-8")

    # Create revision record
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.max(KaizenRevision.version))
            .where(KaizenRevision.document_type == "mandate")
        )
        max_ver = result.scalar() or 0

        revision = KaizenRevision(
            document_type="mandate",
            version=max_ver + 1,
            change_summary=body.change_summary,
            content_snapshot=body.content,
        )
        session.add(revision)
        await session.commit()

    return ApiResponse(data={
        "content": body.content,
        "version": max_ver + 1,
        "message": "The Mandate has been updated and sealed.",
    })


# ── Revisions endpoint ────────────────────────────────────────

@router.get("/revisions", response_model=ApiResponse)
async def list_revisions(document_type: str | None = None):
    """List revision history, optionally filtered by document type."""
    async with async_session_factory() as session:
        stmt = select(KaizenRevision).order_by(desc(KaizenRevision.created_at))
        if document_type:
            stmt = stmt.where(KaizenRevision.document_type == document_type)
        stmt = stmt.limit(50)
        
        result = await session.execute(stmt)
        revisions = result.scalars().all()

    return ApiResponse(
        data=[
            {
                "id": str(r.id),
                "document_type": r.document_type,
                "version": r.version,
                "change_summary": r.change_summary,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in revisions
        ],
        meta={"total": len(revisions)},
    )


# ── Audit log endpoint ────────────────────────────────────────

@router.get("/audit-log")
async def download_audit_log():
    """Export full audit log as downloadable JSON."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(KaizenRevision).order_by(desc(KaizenRevision.created_at)).limit(200)
        )
        revisions = result.scalars().all()

    log_entries = [
        {
            "id": str(r.id),
            "document_type": r.document_type,
            "version": r.version,
            "change_summary": r.change_summary,
            "content_snapshot": r.content_snapshot,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in revisions
    ]

    return JSONResponse(
        content={
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(log_entries),
            "entries": log_entries,
        },
        headers={
            "Content-Disposition": "attachment; filename=kaizen_audit_log.json",
        },
    )
