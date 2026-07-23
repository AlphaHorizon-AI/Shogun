"""Tool service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.tool_connector import ToolConnector
from shogun.services.base_service import BaseService

DOJO_MCP_SLUG = "openclaw-dojo"
PROTECTED_BUILTIN_TOOL_SLUGS = frozenset({DOJO_MCP_SLUG})
DOJO_MCP_DEFAULTS: dict[str, Any] = {
    "name": "OpenClaw Dojo",
    "connector_type": "mcp",
    "source": "builtin",
    "base_url": None,
    "status": "connected",
    "auth_type": "custom",
    "scope": "dojo openclaw skills badges achievements transcript",
    "risk_level": "medium",
    "config": {
        "command": "shogun-python",
        "args": ["-m", "shogun.mcp.openclaw_dojo"],
        "env": {},
        "transport": "stdio",
        "builtin": True,
    },
}


class ProtectedBuiltinToolError(ValueError):
    """Raised when an immutable built-in connector is modified."""


async def ensure_dojo_mcp_connector(
    session: AsyncSession,
    *,
    actor: str = "startup",
) -> tuple[ToolConnector, str]:
    """Install or repair the standard Dojo MCP connector.

    The lookup deliberately includes soft-deleted records so legacy installs are
    restored without violating the connector slug's unique constraint.
    """

    result = await session.execute(
        select(ToolConnector).where(ToolConnector.slug == DOJO_MCP_SLUG)
    )
    connector = result.scalars().first()
    state = "current"

    if connector is None:
        connector = ToolConnector(
            slug=DOJO_MCP_SLUG,
            health_status="unknown",
            created_by=actor,
            updated_by=actor,
            **DOJO_MCP_DEFAULTS,
        )
        session.add(connector)
        state = "created"
    else:
        needs_repair = connector.is_deleted or connector.deleted_at is not None
        for field, value in DOJO_MCP_DEFAULTS.items():
            if getattr(connector, field) != value:
                setattr(connector, field, value)
                needs_repair = True
        if needs_repair:
            connector.is_deleted = False
            connector.deleted_at = None
            connector.updated_by = actor
            state = "repaired"

    await session.flush()
    return connector, state


class ToolService(BaseService[ToolConnector]):
    def __init__(self, session: AsyncSession):
        super().__init__(ToolConnector, session)

    async def get_by_slug(self, slug: str) -> ToolConnector | None:
        result = await self.session.execute(
            select(ToolConnector).where(
                ToolConnector.slug == slug,
                ToolConnector.is_deleted.is_(False),
            )
        )
        return result.scalars().first()

    async def update(self, record_id: uuid.UUID, **kwargs: Any) -> ToolConnector | None:
        instance = await self.get_by_id(record_id)
        if instance and instance.slug in PROTECTED_BUILTIN_TOOL_SLUGS:
            raise ProtectedBuiltinToolError(
                f"{instance.name} is a standard Shogun connector and cannot be modified."
            )
        return await super().update(record_id, **kwargs)

    async def delete(self, record_id: uuid.UUID) -> bool:
        instance = await self.get_by_id(record_id)
        if instance and instance.slug in PROTECTED_BUILTIN_TOOL_SLUGS:
            raise ProtectedBuiltinToolError(
                f"{instance.name} is a standard Shogun connector and cannot be removed."
            )
        return await super().delete(record_id)
