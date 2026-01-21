"""Celery tasks for artifact lifecycle management.

DEPRECATED: These tasks will be removed when SummitFlow has Celery infrastructure.
Evidence/artifacts are now managed by SummitFlow (port 8001).

Tasks:
- refresh_expired_artifacts: DISABLED (SummitFlow manages evidence)
- cleanup_old_versions: DISABLED (SummitFlow manages evidence)
- cleanup_debug_captures: Still active (local filesystem cleanup)
"""

from __future__ import annotations

from celery import shared_task

from ..logging_config import get_logger
from .maintenance_logging import log_maintenance_complete, log_maintenance_start

logger = get_logger(__name__)


@shared_task(name="refresh_expired_artifacts")
def refresh_expired_artifacts() -> dict[str, int | str]:
    """DISABLED: Evidence is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own Celery infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add Celery task infrastructure)
    """
    logger.info(
        "refresh_expired_artifacts_skipped",
        reason="Migrated to SummitFlow - awaiting Celery integration",
    )
    return {
        "status": "skipped",
        "reason": "Evidence now managed by SummitFlow",
    }


@shared_task(name="cleanup_old_versions")
def cleanup_old_versions(
    max_versions: int = 5, dry_run: bool = False
) -> dict[str, int | str | bool]:
    """DISABLED: Evidence is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own Celery infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add Celery task infrastructure)
    """
    logger.info(
        "cleanup_old_versions_skipped",
        reason="Migrated to SummitFlow - awaiting Celery integration",
    )
    return {
        "status": "skipped",
        "reason": "Evidence now managed by SummitFlow",
        "dry_run": dry_run,
    }


@shared_task(name="cleanup_debug_captures")
def cleanup_debug_captures(max_age_days: int = 7, dry_run: bool = False) -> dict[str, object]:
    """Delete old debug capture directories (DBG-* pattern).

    These are ad-hoc screenshot captures that don't need long retention.

    Args:
        max_age_days: Delete captures older than N days (default: 7)
        dry_run: If True, only report what would be deleted

    Returns:
        Summary dict with deleted count and size
    """
    import re
    import shutil
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    log_id = log_maintenance_start("cleanup_debug_captures", dry_run)

    logger.info(
        "cleanup_debug_captures_started",
        max_age_days=max_age_days,
        dry_run=dry_run,
    )

    try:
        artifacts_dir = Path("/home/kasadis/portfolio-ai/data/artifacts")
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        deleted_count = 0
        deleted_size = 0
        errors = []

        # Match directory names like DBG-1213-222150 (MMDD-HHMMSS format)
        dbg_pattern = re.compile(r"^DBG-(\d{4})-(\d{4,6})$")

        for entry in artifacts_dir.iterdir():
            if not entry.is_dir():
                continue

            match = dbg_pattern.match(entry.name)
            if not match:
                continue

            # Parse date from directory name (format: DBG-MMDD-HHMMSS)
            mmdd = match.group(1)
            try:
                # Assume current year
                year = datetime.now(UTC).year
                month = int(mmdd[:2])
                day = int(mmdd[2:4])
                capture_date = datetime(year, month, day, tzinfo=UTC)

                # Handle year boundary (December captures in January)
                if capture_date > datetime.now(UTC):
                    capture_date = datetime(year - 1, month, day, tzinfo=UTC)

                if capture_date < cutoff_date:
                    # Calculate size
                    dir_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())

                    if dry_run:
                        logger.info(
                            "would_delete_debug_capture",
                            path=str(entry),
                            size_bytes=dir_size,
                            capture_date=capture_date.isoformat(),
                        )
                    else:
                        shutil.rmtree(entry)
                        logger.info(
                            "deleted_debug_capture",
                            path=str(entry),
                            size_bytes=dir_size,
                            capture_date=capture_date.isoformat(),
                        )

                    deleted_count += 1
                    deleted_size += dir_size

            except (ValueError, OSError) as e:
                errors.append({"path": str(entry), "error": str(e)})
                logger.error("cleanup_debug_capture_error", path=str(entry), error=str(e))

        logger.info(
            "cleanup_debug_captures_completed",
            deleted_count=deleted_count,
            deleted_size_bytes=deleted_size,
            dry_run=dry_run,
            error_count=len(errors),
        )

        result = {
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "dry_run": dry_run,
            "errors": errors,
        }
        log_maintenance_complete(log_id, "cleanup_debug_captures", True, result)
        return result

    except Exception as e:
        logger.error(
            "cleanup_debug_captures_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        error_result = {"error": str(e), "success": False, "dry_run": dry_run}
        log_maintenance_complete(log_id, "cleanup_debug_captures", False, error_result, str(e))
        return error_result
