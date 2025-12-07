"""Celery tasks for artifact lifecycle management.

Tasks:
- refresh_expired_artifacts: Refresh evidence that has expired (>24h old)
- cleanup_old_versions: Delete artifact versions beyond retention limit
"""

from __future__ import annotations

from celery import shared_task

from ..logging_config import get_logger
from ..services import artifact_manager

logger = get_logger(__name__)


@shared_task(name="refresh_expired_artifacts")
def refresh_expired_artifacts() -> dict:
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
def cleanup_old_versions(max_versions: int = 5, dry_run: bool = False) -> dict:
    """Delete old artifact versions beyond retention limit.

    This task runs daily to manage storage.
    Keeps only the most recent N versions per feature/criterion.

    Args:
        max_versions: Maximum versions to keep (default: 5)
        dry_run: If True, only report what would be deleted

    Returns:
        Summary dict with deleted count and size
    """
    logger.info(
        "cleanup_old_versions_started",
        max_versions=max_versions,
        dry_run=dry_run,
    )

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

    return result
