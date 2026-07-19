"""Skill Usage Tracking Service."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skillopt import SkillUsageEvent
from shogun.services.base_service import BaseService


class SkillUsageTrackingService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillUsageEvent, db_session)
        self.db = db_session

    async def log_usage(
        self,
        skill_id: uuid.UUID,
        skill_version_id: uuid.UUID,
        run_id: Optional[str] = None,
        stack_run_id: Optional[uuid.UUID] = None,
        agent_id: Optional[str] = None,
        model_used: Optional[str] = None,
        posture: Optional[str] = None,
        task_type: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        outcome: Optional[str] = None,
        score: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SkillUsageEvent:
        """Log an execution that used a specific skill version."""
        event = SkillUsageEvent(
            id=uuid.uuid4(),
            skill_id=skill_id,
            skill_version_id=skill_version_id,
            run_id=run_id,
            stack_run_id=stack_run_id,
            agent_id=agent_id,
            model_used=model_used,
            posture=posture,
            task_type=task_type,
            started_at=started_at or datetime.utcnow(),
            completed_at=completed_at,
            outcome=outcome,
            score=score,
            metadata_json=metadata or {},
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def get_usage_for_skill(self, skill_id: uuid.UUID, limit: int = 100) -> list[SkillUsageEvent]:
        """Get recent usage events for a skill."""
        stmt = select(SkillUsageEvent).where(SkillUsageEvent.skill_id == skill_id).order_by(SkillUsageEvent.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
