"""Tasks for artifact lifecycle management.

DEPRECATED: These tasks will be removed when SummitFlow has task infrastructure.
Evidence/artifacts are now managed by SummitFlow (port 8001).

Tasks:
- refresh_expired_artifacts: DISABLED (SummitFlow manages evidence)
- cleanup_old_versions: DISABLED (SummitFlow manages evidence)
- cleanup_debug_captures: Still active (local filesystem cleanup)
"""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..config import settings
from ..logging_config import get_logger
from .maintenance_logging import log_maintenance_complete, log_maintenance_start

logger = get_logger(__name__)

# Constants
_SUMMITFLOW_SKIP_REASON = "Evidence now managed by SummitFlow"
_TASK_NAME = "cleanup_debug_captures"
_ARTIFACTS_DIR = settings.artifacts_dir
_DBG_PATTERN = re.compile(r"^DBG-(\d{4})-(\d{4,6})$")


def refresh_expired_artifacts() -> dict[str, int | str]:
    """DISABLED: Evidence is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own task infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add task infrastructure)
    """
    logger.info(
        "refresh_expired_artifacts_skipped",
        reason="Migrated to SummitFlow - awaiting task integration",
    )
    return {"status": "skipped", "reason": _SUMMITFLOW_SKIP_REASON}


def cleanup_old_versions(
    max_versions: int = 5, dry_run: bool = False
) -> dict[str, int | str | bool]:
    """DISABLED: Evidence is now managed by SummitFlow.

    This task is a no-op until SummitFlow has its own task infrastructure.
    See: portfolio-ai-4tg (SummitFlow: Add task infrastructure)
    """
    logger.info(
        "cleanup_old_versions_skipped",
        reason="Migrated to SummitFlow - awaiting task integration",
    )
    return {"status": "skipped", "reason": _SUMMITFLOW_SKIP_REASON, "dry_run": dry_run}


def _parse_dbg_capture_date(entry: Path) -> datetime | None:
    """Parse the capture date from a DBG-MMDD-HHMMSS directory name."""
    match = _DBG_PATTERN.match(entry.name)
    if not match:
        return None
    mmdd = match.group(1)
    year = datetime.now(UTC).year
    month = int(mmdd[:2])
    day = int(mmdd[2:4])
    capture_date = datetime(year, month, day, tzinfo=UTC)
    if capture_date > datetime.now(UTC):
        capture_date = datetime(year - 1, month, day, tzinfo=UTC)
    return capture_date


def _process_debug_entry(
    entry: Path,
    cutoff_date: datetime,
    dry_run: bool,
) -> tuple[int, int]:
    """Process one DBG directory; return (count, size) acted on (0,0 if skipped)."""
    if not entry.is_dir():
        return (0, 0)
    capture_date = _parse_dbg_capture_date(entry)
    if capture_date is None or capture_date >= cutoff_date:
        return (0, 0)
    dir_size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
    if dry_run:
        logger.info("would_delete_debug_capture", path=str(entry),
                    size_bytes=dir_size, capture_date=capture_date.isoformat())
    else:
        shutil.rmtree(entry)
        logger.info("deleted_debug_capture", path=str(entry),
                    size_bytes=dir_size, capture_date=capture_date.isoformat())
    return (1, dir_size)


def cleanup_debug_captures(max_age_days: int = 7, dry_run: bool = False) -> dict[str, object]:
    """Delete old debug capture directories (DBG-* pattern).

    Args:
        max_age_days: Delete captures older than N days (default: 7)
        dry_run: If True, only report what would be deleted

    Returns:
        Summary dict with deleted count and size
    """
    task_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    log_id = log_maintenance_start(_TASK_NAME, dry_run)
    logger.info(
        "cleanup_debug_captures_started",
        task_id=task_id,
        max_age_days=max_age_days,
        dry_run=dry_run,
    )

    try:
        if not _ARTIFACTS_DIR.exists():
            result_dict: dict[str, object] = {
                "task_id": task_id,
                "deleted_count": 0,
                "deleted_size_bytes": 0,
                "dry_run": dry_run,
                "success": True,
                "message": f"Artifacts directory not found: {_ARTIFACTS_DIR}",
                "duration_seconds": round((datetime.now(UTC) - started_at).total_seconds(), 2),
            }
            logger.warning(
                "cleanup_debug_captures_directory_missing",
                task_id=task_id,
                artifacts_dir=str(_ARTIFACTS_DIR),
            )
            log_maintenance_complete(log_id, _TASK_NAME, True, result_dict)
            return result_dict

        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)
        deleted_count = 0
        deleted_size = 0
        errors: list[dict[str, str]] = []

        for entry in _ARTIFACTS_DIR.iterdir():
            try:
                cnt, sz = _process_debug_entry(entry, cutoff_date, dry_run)
                deleted_count += cnt
                deleted_size += sz
            except (ValueError, OSError) as e:
                errors.append({"path": str(entry), "error": str(e)})
                logger.error("cleanup_debug_capture_error", path=str(entry), error=str(e))

        duration_seconds = round((datetime.now(UTC) - started_at).total_seconds(), 2)
        logger.info(
            "cleanup_debug_captures_completed",
            task_id=task_id,
            deleted_count=deleted_count,
            deleted_size_bytes=deleted_size,
            dry_run=dry_run,
            error_count=len(errors),
            duration_seconds=duration_seconds,
        )
        result_dict: dict[str, object] = {
            "task_id": task_id,
            "deleted_count": deleted_count,
            "deleted_size_bytes": deleted_size,
            "dry_run": dry_run,
            "errors": errors,
            "success": True,
            "duration_seconds": duration_seconds,
        }
        log_maintenance_complete(log_id, _TASK_NAME, True, result_dict)
        return result_dict

    except Exception as e:
        duration_seconds = round((datetime.now(UTC) - started_at).total_seconds(), 2)
        logger.error(
            "cleanup_debug_captures_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=duration_seconds,
        )
        error_result: dict[str, object] = {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "dry_run": dry_run,
            "duration_seconds": duration_seconds,
        }
        log_maintenance_complete(log_id, _TASK_NAME, False, error_result, str(e))
        return error_result
