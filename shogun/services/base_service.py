"""Base service with common CRUD patterns."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar, Type, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseService(Generic[ModelT]):
    """Generic async CRUD service for any SQLAlchemy model."""

    def __init__(self, model: Type[ModelT], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, record_id: uuid.UUID) -> ModelT | None:
        """Fetch a single record by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == record_id)
        )
        return result.scalars().first()

    async def get_all(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        filters: list[Any] | None = None,
    ) -> tuple[Sequence[ModelT], int]:
        """Fetch paginated records with optional filters. Returns (records, total_count)."""
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        if filters:
            for f in filters:
                query = query.where(f)
                count_query = count_query.where(f)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        records = result.scalars().all()

        return records, total

    async def create(self, **kwargs: Any) -> ModelT:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, record_id: uuid.UUID, **kwargs: Any) -> ModelT | None:
        """Update an existing record by ID."""
        instance = await self.get_by_id(record_id)
        if instance is None:
            return None

        for key, value in kwargs.items():
            if value is not None:
                setattr(instance, key, value)

        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, record_id: uuid.UUID) -> bool:
        """Delete a record by ID. Uses soft-delete if available."""
        instance = await self.get_by_id(record_id)
        if instance is None:
            return False

        if hasattr(instance, "is_deleted"):
            instance.is_deleted = True
            from datetime import datetime, timezone
            instance.deleted_at = datetime.now(timezone.utc)
        else:
            await self.session.delete(instance)

        await self.session.flush()
        return True
