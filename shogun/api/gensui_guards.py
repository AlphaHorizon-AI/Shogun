"""Gensui Guard Endpoints — CAPABILITY_UNAVAILABLE stubs.

Returns 403 for all enterprise/Gensui skill management endpoints
that are permanently disabled in the Yellow Label edition (§26).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/gensui", tags=["gensui-guards"])

_CAPABILITY_RESPONSE = {
    "error": "CAPABILITY_UNAVAILABLE",
    "edition": "yellow_label",
    "message": (
        "This endpoint requires the Gensui Enterprise edition. "
        "The Yellow Label edition provides local-only skill management "
        "through the SkillOpt Lab."
    ),
}


def _deny() -> None:
    """Raise a 403 with the standard CAPABILITY_UNAVAILABLE body."""
    raise HTTPException(status_code=403, detail=_CAPABILITY_RESPONSE)


@router.post("/skills/publish")
async def gensui_publish():
    """Enterprise skill publication — disabled in Yellow Label."""
    _deny()


@router.get("/skills/manifest")
async def gensui_manifest():
    """Enterprise skill manifest — disabled in Yellow Label."""
    _deny()


@router.post("/skills/{skill_id}/approve")
async def gensui_approve(skill_id: uuid.UUID):
    """Enterprise skill approval — disabled in Yellow Label."""
    _deny()


@router.post("/skills/{skill_id}/distribute")
async def gensui_distribute(skill_id: uuid.UUID):
    """Enterprise skill distribution — disabled in Yellow Label."""
    _deny()


@router.get("/competence")
async def gensui_competence():
    """Enterprise competence registry — disabled in Yellow Label."""
    _deny()
