"""
Shogun Backup Scheduler — integrates with APScheduler to run backups on a cron.
"""

import logging
from shogun.services.backup_service import load_settings, create_backup

logger = logging.getLogger("shogun.backups.scheduler")

BACKUP_JOB_ID = "shogun_auto_backup"


async def run_scheduled_backup():
    """Execute a scheduled backup (called by APScheduler)."""
    settings = load_settings()
    if not settings.get("enabled", False):
        return

    logger.info("Running scheduled backup...")
    result = create_backup(label="auto")

    if result.get("success"):
        logger.info("Scheduled backup completed: %s (%s)",
                     result["filename"], result.get("compressed_size", "?"))
    else:
        logger.error("Scheduled backup failed: %s", result.get("error"))


async def sync_backup_schedule():
    """Sync the backup schedule with current settings. Call after settings change."""
    try:
        from shogun.scheduler import scheduler
    except ImportError:
        logger.debug("Scheduler not available, skipping backup schedule sync")
        return

    if scheduler is None:
        return

    settings = load_settings()

    # Remove existing job
    try:
        scheduler.remove_job(BACKUP_JOB_ID)
    except Exception:
        pass  # Job didn't exist

    if settings.get("enabled", False):
        interval_hours = settings.get("interval_hours", 24)
        scheduler.add_job(
            run_scheduled_backup,
            trigger="interval",
            hours=interval_hours,
            id=BACKUP_JOB_ID,
            name="Shogun Auto-Backup",
            replace_existing=True,
        )
        logger.info("Backup schedule set: every %d hours", interval_hours)
    else:
        logger.info("Backup schedule disabled")
