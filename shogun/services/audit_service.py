"""Audit service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.execution_event import ExecutionEvent
from shogun.services.base_service import BaseService


class AuditService(BaseService[ExecutionEvent]):
    def __init__(self, session: AsyncSession):
        super().__init__(ExecutionEvent, session)
