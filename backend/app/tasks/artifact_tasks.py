"""Celery tasks for artifact lifecycle management.

Tasks:
- refresh_expired_artifacts: Refresh evidence that has expired (>24h old)
- cleanup_old_versions: Delete artifact versions beyond retention limit
"""

from __future__ import annotations

from celery import shared_task

from ..logging_config import get_logger
from ..services import artifact_manager
from .maintenance_logging import log_maintenance_complete, log_maintenance_start

logger = get_logger(__name__)


@shared_task(name="refresh_expired_artifacts")
def refresh_expired_artifacts() -> dict[str, int | str]:
    """Refresh artifacts that have expired and need new evidence capture.

    This task runs daily to keep evidence fresh.
    Expired artifacts are those where expires_at < NOW().

    Returns:
        Summary dict with count of refreshed artifacts
    """
    logger.info("refresh_expired_artifacts_started")

    expired = artifact_manager.get_expired_artifacts()
    refreshed = 0
    failed = 0

    for artifact in expired:
        try:
            # Read evidence to get URL
            evidence = artifact_manager.read_evidence_file(
                artifact["feature_id"],
                artifact["criterion_id"],
                artifact["version"],
            )

            if not evidence or not evidence.get("metadata", {}).get("url"):
                logger.warning(
                    "skip_refresh_no_url",
                    artifact_id=artifact["artifact_id"],
                )
                continue

            url = evidence["metadata"]["url"]

            # Note: This is a sync task, but capture_evidence is async
            # For now, we'll just mark them as needing refresh
            # A future improvement would use asyncio.run() or a separate async worker
            logger.info(
                "artifact_needs_refresh",
                artifact_id=artifact["artifact_id"],
                url=url,
            )

            # Mark as needing refresh by updating quality_status
            artifact_manager.update_ai_review(
                artifact_id=artifact["artifact_id"],
                quality_status="needs_review",
                confidence=0.0,
                ai_evidence="Expired - needs refresh",
                reviewed_by="celery",
            )

            refreshed += 1

        except Exception as e:
            logger.error(
                "refresh_artifact_failed",
                artifact_id=artifact.get("artifact_id"),
                error=str(e),
            )
            failed += 1

    logger.info(
        "refresh_expired_artifacts_completed",
        total=len(expired),
        refreshed=refreshed,
        failed=failed,
    )

    return {
        "total_expired": len(expired),
        "refreshed": refreshed,
        "failed": failed,
    }


@shared_task(name="cleanup_old_versions")
def cleanup_old_versions(
    max_versions: int = 5, dry_run: bool = False
) -> dict[str, int | str | bool]:
    """Delete old artifact versions beyond retention limit.

    This task runs daily to manage storage.
    Keeps only the most recent N versions per feature/criterion.

    Args:
        max_versions: Maximum versions to keep (default: 5)
        dry_run: If True, only report what would be deleted

    Returns:
        Summary dict with deleted count and size
    """
    log_id = log_maintenance_start("cleanup_old_versions", dry_run)

    logger.info(
        "cleanup_old_versions_started",
        max_versions=max_versions,
        dry_run=dry_run,
    )

    try:
        result = artifact_manager.cleanup_old_versions(
            max_versions=max_versions,
            dry_run=dry_run,
        )

        logger.info(
            "cleanup_old_versions_completed",
            deleted_count=result["deleted_count"],
            deleted_size_bytes=result["deleted_size_bytes"],
            dry_run=dry_run,
        )

        log_maintenance_complete(log_id, "cleanup_old_versions", True, dict(result))
        return result

    except Exception as e:
        logger.error(
            "cleanup_old_versions_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        error_result = {"error": str(e), "success": False, "dry_run": dry_run}
        log_maintenance_complete(log_id, "cleanup_old_versions", False, error_result, str(e))
        return error_result


@shared_task(name="cleanup_debug_captures")
def cleanup_debug_captures(
    max_age_days: int = 7, dry_run: bool = False
) -> dict[str, int | str | bool]:
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
    from datetime import datetime, timedelta
    from pathlib import Path

    log_id = log_maintenance_start("cleanup_debug_captures", dry_run)

    logger.info(
        "cleanup_debug_captures_started",
        max_age_days=max_age_days,
        dry_run=dry_run,
    )

    try:
        artifacts_dir = Path("/home/kasadis/portfolio-ai/data/artifacts")
        cutoff_date = datetime.now() - timedelta(days=max_age_days)

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
                year = datetime.now().year
                month = int(mmdd[:2])
                day = int(mmdd[2:4])
                capture_date = datetime(year, month, day)

                # Handle year boundary (December captures in January)
                if capture_date > datetime.now():
                    capture_date = datetime(year - 1, month, day)

                if capture_date < cutoff_date:
                    # Calculate size
                    dir_size = sum(
                        f.stat().st_size for f in entry.rglob("*") if f.is_file()
                    )

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
