"""Team-mode member persistence, channel identity resolution, and memory seeding."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.operator import Operator


def _username(name: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "member"
    return f"team-{index + 1}-{slug}"[:100]


def configured_telegram_member_ids(bushido_settings: dict[str, Any]) -> list[str]:
    """Do not extend Telegram access from legacy Team-mode records."""
    return []


async def configure_team_members(
    session: AsyncSession,
    *,
    installation_mode: str,
    admin_name: str,
    members: list[dict[str, Any]],
    agent_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Upsert setup-managed operators and create pinned identity memories."""
    normalized = members if installation_mode == "team" else []
    if not normalized:
        normalized = [{"display_name": admin_name, "is_primary": True, "channel": "web"}]

    primary = next((item for item in normalized if item.get("is_primary")), normalized[0])
    ordered = [primary, *(item for item in normalized if item is not primary)]
    persisted: list[dict[str, Any]] = []
    existing = list((await session.scalars(select(Operator))).all())
    by_username = {item.username: item for item in existing}
    managed_ids: set[uuid.UUID] = set()

    for index, member in enumerate(ordered):
        is_primary = index == 0
        username = "admin" if is_primary else _username(str(member["display_name"]), index)
        operator = by_username.get(username)
        preferences = {
            "setup_managed": True,
            "installation_mode": installation_mode,
            "is_primary": is_primary,
            "active": True,
            "channel": "web" if is_primary else member.get("channel", "telegram"),
            "telegram_user_id": str(member.get("telegram_user_id") or "").strip() or None,
            "teams_aad_object_id": str(member.get("teams_aad_object_id") or "").strip() or None,
            "teams_user_principal_name": str(member.get("teams_user_principal_name") or "").strip() or None,
        }
        if operator:
            operator.display_name = str(member["display_name"]).strip()
            operator.email = str(member.get("email") or "").strip() or None
            operator.role = "owner" if is_primary else "member"
            operator.preferences = {**dict(operator.preferences or {}), **preferences}
        else:
            operator = Operator(
                username=username,
                display_name=str(member["display_name"]).strip(),
                email=str(member.get("email") or "").strip() or None,
                role="owner" if is_primary else "member",
                preferences=preferences,
            )
            session.add(operator)
        await session.flush()
        managed_ids.add(operator.id)

        member_data = {
            "id": str(operator.id),
            "display_name": operator.display_name,
            "role": "admin" if is_primary else "member",
            **preferences,
        }
        persisted.append(member_data)
        await _seed_member_memory(session, agent_id=agent_id, operator=operator, member=member_data)

    for operator in existing:
        if operator.id not in managed_ids and (operator.preferences or {}).get("setup_managed"):
            operator.preferences = {**dict(operator.preferences or {}), "active": False}

    return persisted


def serialize_team_member(operator: Operator) -> dict[str, Any]:
    """Return the safe, editable member fields used by setup and Katana."""
    prefs = dict(operator.preferences or {})
    is_primary = operator.role == "owner" or bool(prefs.get("is_primary"))
    return {
        "id": str(operator.id),
        "display_name": operator.display_name,
        "email": operator.email,
        "role": "admin" if is_primary else "member",
        "is_primary": is_primary,
        "active": bool(prefs.get("active", True)),
        "channel": "web" if is_primary else prefs.get("channel", "telegram"),
        "telegram_user_id": prefs.get("telegram_user_id"),
        "teams_aad_object_id": prefs.get("teams_aad_object_id"),
        "teams_user_principal_name": prefs.get("teams_user_principal_name"),
    }


async def get_team_state(session: AsyncSession) -> dict[str, Any]:
    """Return the current operating mode and non-deleted setup-managed roster."""
    from shogun.db.models.agent import Agent

    agent = await session.scalar(select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)))
    operators = list((await session.scalars(select(Operator).order_by(Operator.created_at))).all())
    managed = [
        item for item in operators
        if (item.preferences or {}).get("setup_managed")
        and not (item.preferences or {}).get("team_deleted", False)
    ]
    return {
        "mode": str((agent.bushido_settings or {}).get("installation_mode", "single")) if agent else "single",
        "members": [serialize_team_member(item) for item in managed],
    }


async def _sync_team_settings(session: AsyncSession, *, mode: str | None = None) -> dict[str, Any]:
    """Synchronize Operator identities back into the primary Shogun settings."""
    from shogun.db.models.agent import Agent

    agent = await session.scalar(select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)))
    if not agent:
        raise ValueError("Primary Shogun agent not found.")
    state = await get_team_state(session)
    selected_mode = mode or state["mode"]
    agent.bushido_settings = {
        **dict(agent.bushido_settings or {}),
        "installation_mode": selected_mode,
        "team_members": state["members"],
    }
    state["mode"] = selected_mode
    return state


async def set_team_mode(session: AsyncSession, mode: str) -> dict[str, Any]:
    """Switch modes while retaining the saved roster and revoking channel access in Single mode."""
    if mode not in {"single", "team"}:
        raise ValueError("mode must be 'single' or 'team'.")
    operators = list((await session.scalars(select(Operator))).all())
    for operator in operators:
        prefs = dict(operator.preferences or {})
        if not prefs.get("setup_managed") or prefs.get("team_deleted", False):
            continue
        is_primary = operator.role == "owner" or bool(prefs.get("is_primary"))
        prefs["active"] = bool(is_primary or mode == "team")
        prefs["installation_mode"] = mode
        operator.preferences = prefs
    state = await _sync_team_settings(session, mode=mode)
    await session.commit()
    return state


def _validate_member_identity(member: dict[str, Any]) -> None:
    channel = str(member.get("channel") or "telegram")
    if channel == "telegram" and not str(member.get("telegram_user_id") or "").strip():
        raise ValueError("Telegram user ID is required.")
    if channel == "microsoft_teams" and not (
        str(member.get("teams_aad_object_id") or "").strip()
        or str(member.get("teams_user_principal_name") or "").strip()
    ):
        raise ValueError("Teams Entra Object ID or sign-in email is required.")


async def add_team_member(
    session: AsyncSession,
    *,
    member: dict[str, Any],
) -> dict[str, Any]:
    """Add a channel identity and seed its isolated member-memory profile."""
    from shogun.db.models.agent import Agent

    state = await get_team_state(session)
    if state["mode"] != "team":
        raise ValueError("Switch to Team mode before adding Team Members.")
    _validate_member_identity(member)
    channel = str(member.get("channel") or "telegram")
    identity = str(
        member.get("telegram_user_id")
        or member.get("teams_aad_object_id")
        or member.get("teams_user_principal_name")
        or ""
    ).strip().casefold()
    operators = list((await session.scalars(select(Operator))).all())
    for existing in operators:
        prefs = existing.preferences or {}
        if prefs.get("team_deleted", False) or prefs.get("is_primary"):
            continue
        existing_identity = str(
            prefs.get("telegram_user_id")
            or prefs.get("teams_aad_object_id")
            or prefs.get("teams_user_principal_name")
            or ""
        ).strip().casefold()
        if prefs.get("channel") == channel and existing_identity == identity:
            raise ValueError("That Telegram or Teams identity already belongs to a Team Member.")

    operator = Operator(
        username=f"team-{uuid.uuid4().hex[:12]}",
        display_name=str(member.get("display_name") or "").strip(),
        email=str(member.get("email") or "").strip() or None,
        role="member",
        preferences={
            "setup_managed": True,
            "installation_mode": "team",
            "is_primary": False,
            "active": True,
            "team_deleted": False,
            "channel": channel,
            "telegram_user_id": str(member.get("telegram_user_id") or "").strip() or None,
            "teams_aad_object_id": str(member.get("teams_aad_object_id") or "").strip() or None,
            "teams_user_principal_name": str(member.get("teams_user_principal_name") or "").strip() or None,
        },
    )
    if not operator.display_name:
        raise ValueError("Display name is required.")
    session.add(operator)
    await session.flush()
    agent = await session.scalar(select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)))
    if not agent:
        raise ValueError("Primary Shogun agent not found.")
    member_data = serialize_team_member(operator)
    await _seed_member_memory(session, agent_id=agent.id, operator=operator, member=member_data)
    await _sync_team_settings(session, mode="team")
    await session.commit()
    return serialize_team_member(operator)


async def delete_team_member(session: AsyncSession, member_id: uuid.UUID) -> dict[str, Any]:
    """Revoke a member, remove it from the roster, and archive its private memory slot."""
    from shogun.db.models.agent import Agent

    operator = await session.get(Operator, member_id)
    if not operator or (operator.preferences or {}).get("team_deleted", False):
        raise ValueError("Team Member not found.")
    if operator.role == "owner" or (operator.preferences or {}).get("is_primary"):
        raise ValueError("The Primary Admin cannot be deleted.")
    prefs = dict(operator.preferences or {})
    prefs.update({"active": False, "team_deleted": True})
    operator.preferences = prefs

    agent = await session.scalar(select(Agent).where(Agent.is_primary.is_(True), Agent.is_deleted.is_(False)))
    if not agent:
        raise ValueError("Primary Shogun agent not found.")
    memories = list((await session.scalars(
        select(MemoryRecord).where(MemoryRecord.agent_id == agent.id)
    )).all())
    member_tag = f"member:{operator.id}"
    for memory in memories:
        if memory.source_external_id == f"team-member:{operator.id}" or member_tag in (memory.tags or []):
            memory.is_archived = True
            memory.is_pinned = False
    state = await get_team_state(session)
    await _sync_team_settings(session, mode=state["mode"])
    await session.commit()
    return {"id": str(operator.id), "display_name": operator.display_name, "deleted": True}


async def _seed_member_memory(
    session: AsyncSession,
    *,
    agent_id: uuid.UUID,
    operator: Operator,
    member: dict[str, Any],
) -> None:
    external_id = f"team-member:{operator.id}"
    role = "Primary Admin" if member["is_primary"] else "Team Member"
    channel = member.get("channel") or "web"
    content = (
        f"{operator.display_name} is a {role} in this Shogun installation. "
        f"Their approved communication channel is {channel}. "
        "Maintain a distinct relationship and preference history for this member. "
        "Never treat a non-admin member as the Primary Admin and never disclose another member's private context."
    )
    existing = await session.scalar(
        select(MemoryRecord).where(
            MemoryRecord.agent_id == agent_id,
            MemoryRecord.source_external_id == external_id,
        )
    )
    if existing:
        existing.title = f"Team member — {operator.display_name}"
        existing.content = content
        existing.summary = f"Identity profile for {operator.display_name} ({role})."
        existing.tags = ["team-member", f"member:{operator.id}", f"role:{member['role']}"]
        existing.is_pinned = True
        existing.is_archived = False
        return
    session.add(MemoryRecord(
        memory_type="persona",
        agent_id=agent_id,
        title=f"Team member — {operator.display_name}",
        content=content,
        summary=f"Identity profile for {operator.display_name} ({role}).",
        importance_score=1.0,
        confidence_score=1.0,
        relevance_score=1.0,
        decay_class="pinned",
        is_pinned=True,
        tags=["team-member", f"member:{operator.id}", f"role:{member['role']}"],
        source_type="setup",
        source_system="shogun-setup",
        source_external_id=external_id,
    ))
    await session.flush()


async def resolve_channel_member(
    session: AsyncSession,
    *,
    channel: str,
    external_user_id: str | None = None,
    aad_object_id: str | None = None,
    user_principal_name: str | None = None,
) -> Operator | None:
    """Resolve a channel identity to its setup member without guessing by name."""
    operators = list((await session.scalars(select(Operator))).all())
    for operator in operators:
        if operator.role != "owner":
            continue
        prefs = operator.preferences or {}
        if not prefs.get("active", True):
            continue
        if channel == "telegram" and external_user_id:
            if str(prefs.get("telegram_user_id") or "") == str(external_user_id):
                return operator
        if channel == "microsoft_teams":
            stored_aad_id = str(prefs.get("teams_aad_object_id") or "")
            stored_upn = str(prefs.get("teams_user_principal_name") or "")
            if aad_object_id and stored_aad_id.casefold() == aad_object_id.casefold():
                return operator
            if user_principal_name and stored_upn.casefold() == user_principal_name.casefold():
                return operator
            if external_user_id and str(prefs.get("teams_user_id") or "") == str(external_user_id):
                return operator
    return None


def member_context_text(message: str, member: Operator | None, *, channel: str) -> str:
    """Attach verified speaker identity to an agent prompt."""
    if not member:
        return message
    role = "Primary Admin" if member.role == "owner" else "Team Member"
    return (
        f"{message.rstrip()}\n\nVerified speaker identity:\n"
        f"- Name: {member.display_name}\n- Role: {role}\n- Channel: {channel}\n"
        f"- Member ID: {member.id}\n"
        "Use memories tagged for this member when personalizing the response. "
        "Do not grant Primary Admin authority to a Team Member."
    )
