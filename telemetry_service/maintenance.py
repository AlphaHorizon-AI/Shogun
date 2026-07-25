"""Retention maintenance entry point."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from telemetry_service.config import settings
from telemetry_service.db import SessionFactory
from telemetry_service.db_models import Event


def purge_expired_events() -> int:
    cutoff = datetime.now(UTC) - timedelta(days=settings.raw_event_retention_days)
    with SessionFactory() as db:
        result = db.execute(delete(Event).where(Event.received_at < cutoff))
        db.commit()
        return int(result.rowcount or 0)


if __name__ == "__main__":
    print(f"Purged {purge_expired_events()} expired raw telemetry events")
