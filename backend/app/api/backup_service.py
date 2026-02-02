"""Business logic for backup operations."""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..logging_config import get_logger

logger = get_logger(__name__)

# Configuration
PROJECT_DIR = Path.home() / "portfolio-ai"
BACKUP_INDEX_PATH = PROJECT_DIR / "backup-index.json"
BACKUP_SCRIPT = PROJECT_DIR / "scripts" / "backup.sh"

# In-memory job tracking (simple approach for single-instance)
_running_jobs: dict[str, dict[str, Any]] = {}

# Track last sync time to avoid excessive SMB calls
_last_sync_time: datetime | None = None
_SYNC_INTERVAL_SECONDS = 300  # Sync at most every 5 minutes


def sync_backup_index() -> bool:
    """Sync backup index with SMB - self-healing on mismatch."""
    sync_script = PROJECT_DIR / "scripts" / "lib" / "backup-utils.sh"
    if not sync_script.exists():
        logger.warning("sync_script_not_found", path=str(sync_script))
        return False

    try:
        # Use --verify-missing to auto-verify backups lacking verification data
        result = subprocess.run(
            ["bash", "-c", f"source {sync_script} && sync_index_from_smb --verify-missing"],
            check=False,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min - verification downloads backups
            cwd=str(PROJECT_DIR),
        )
        if result.returncode == 0:
            logger.info("backup_index_synced")
            return True
        logger.warning(
            "backup_index_sync_failed", stderr=result.stderr[:200] if result.stderr else None
        )
        return False
    except Exception as e:
        logger.warning("backup_index_sync_error", error=str(e))
        return False


def read_backup_index(force_sync: bool = False) -> dict[str, Any]:
    """Read and parse the backup index file.

    Auto-syncs with SMB if:
    - force_sync is True
    - More than 5 minutes since last sync
    - Index file doesn't exist
    """
    global _last_sync_time  # noqa: PLW0603

    # Determine if we should sync
    should_sync = force_sync or not BACKUP_INDEX_PATH.exists()
    if not should_sync and _last_sync_time:
        time_since_sync = (datetime.now(UTC) - _last_sync_time).total_seconds()
        should_sync = time_since_sync > _SYNC_INTERVAL_SECONDS
    elif not _last_sync_time:
        should_sync = True  # First call, sync to ensure consistency

    if should_sync:
        sync_backup_index()
        _last_sync_time = datetime.now(UTC)

    if not BACKUP_INDEX_PATH.exists():
        return {
            "version": 1,
            "retention": 30,
            "destination": "//192.168.8.128/davion-gem/project-backups/portfolio-ai",
            "backups": [],
            "last_updated": None,
        }

    try:
        with BACKUP_INDEX_PATH.open() as f:
            data: dict[str, Any] = json.load(f)
            return data
    except Exception as e:
        logger.error("read_backup_index_failed", error=str(e))
        raise RuntimeError(f"Failed to read backup index: {e}") from e


def determine_backup_health(index: dict[str, Any]) -> tuple[str, str]:
    """Determine backup health status and message."""
    backups = index.get("backups", [])

    if not backups:
        return "no_backups", "No backups have been created yet"

    latest = backups[0]
    latest_ts = latest.get("timestamp")

    if not latest_ts:
        return "error", "Latest backup has no timestamp"

    try:
        # Parse timestamp
        backup_time = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
        age_hours = (datetime.now(backup_time.tzinfo or None) - backup_time).total_seconds() / 3600

        if age_hours < 24:
            return "healthy", f"Last backup {age_hours:.1f} hours ago"
        if age_hours < 48:
            return "stale", f"Last backup {age_hours:.1f} hours ago (>24h)"
        return "stale", f"Last backup {age_hours:.1f} hours ago (stale)"
    except Exception as e:
        logger.warning("backup_age_calculation_failed", error=str(e))
        return "healthy", f"Latest backup: {latest.get('name', 'unknown')}"


def run_backup_in_background(job_id: str, quick_mode: bool = False) -> None:
    """Run backup script in background and update job status."""
    _running_jobs[job_id]["status"] = "running"

    try:
        cmd = [str(BACKUP_SCRIPT)]
        if quick_mode:
            cmd.append("--quick")

        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=str(PROJECT_DIR),
        )

        _running_jobs[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        _running_jobs[job_id]["output"] = result.stdout[-2000:] if result.stdout else None
        _running_jobs[job_id]["error"] = result.stderr[-500:] if result.stderr else None

        if result.returncode == 0:
            _running_jobs[job_id]["status"] = "completed"
            logger.info("backup_job_completed", job_id=job_id)
        else:
            _running_jobs[job_id]["status"] = "failed"
            logger.error(
                "backup_job_failed",
                job_id=job_id,
                returncode=result.returncode,
                stderr=result.stderr[:500] if result.stderr else None,
            )

    except subprocess.TimeoutExpired:
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = "Backup timed out after 10 minutes"
        _running_jobs[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        logger.error("backup_job_timeout", job_id=job_id)

    except Exception as e:
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        _running_jobs[job_id]["completed_at"] = datetime.now(UTC).isoformat()
        logger.error("backup_job_exception", job_id=job_id, error=str(e))


def create_backup_job(quick_mode: bool = False) -> tuple[str, str, str]:
    """Create a new backup job.

    Returns:
        Tuple of (job_id, status, message)
        status can be "started" or "already_running"
    """
    # Check if a backup is already running
    for job_id, job in _running_jobs.items():
        if job.get("status") == "running":
            logger.info("backup_already_running", existing_job_id=job_id)
            return (
                job_id,
                "already_running",
                f"A backup is already running (job {job_id})",
            )

    # Clean up old completed jobs (keep last 10)
    completed_jobs = [(jid, j) for jid, j in _running_jobs.items() if j.get("status") != "running"]
    if len(completed_jobs) > 10:
        for jid, _ in completed_jobs[:-10]:
            del _running_jobs[jid]

    # Create new job
    job_id = str(uuid.uuid4())[:8]
    _running_jobs[job_id] = {
        "status": "starting",
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": None,
        "output": None,
        "error": None,
        "quick_mode": quick_mode,
    }

    logger.info("backup_triggered", job_id=job_id, quick_mode=quick_mode)

    return (
        job_id,
        "started",
        f"Backup started (job {job_id}). Use GET /api/backup/job/{job_id} to check status.",
    )


def get_job_status(job_id: str) -> dict[str, Any]:
    """Get status of a backup job.

    Returns:
        Dict with job status fields
    """
    if job_id not in _running_jobs:
        return {
            "job_id": job_id,
            "status": "not_found",
            "started_at": None,
            "completed_at": None,
            "output": None,
            "error": "Job not found. It may have expired or never existed.",
        }

    job = _running_jobs[job_id]
    job_status = job.get("status", "not_found")
    # Validate status is one of the allowed values
    valid_statuses = {"running", "completed", "failed", "not_found"}
    if job_status not in valid_statuses:
        job_status = "not_found"

    return {
        "job_id": job_id,
        "status": job_status,
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "output": job.get("output"),
        "error": job.get("error"),
    }


def calculate_backup_age_hours(timestamp: str) -> float | None:
    """Calculate backup age in hours from timestamp string."""
    try:
        backup_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return (datetime.now(backup_time.tzinfo or None) - backup_time).total_seconds() / 3600
    except Exception:
        return None


def check_requirements(
    max_age_hours: float = 24.0,
    require_verification: bool = True,
) -> dict[str, Any]:
    """Check if backup requirements are met for maintenance operations.

    Args:
        max_age_hours: Maximum age of backup in hours (default: 24)
        require_verification: Whether backup must be verified (default: True)

    Returns:
        Dict with requirement check results
    """
    index = read_backup_index()
    backups = index.get("backups", [])

    # No backups at all
    if not backups:
        return {
            "backup_exists": False,
            "backup_recent": False,
            "backup_verified": False,
            "backup_name": None,
            "backup_age_hours": None,
            "can_proceed": False,
            "blocking_reason": "No backups exist. Create a backup before running maintenance.",
            "warnings": [],
        }

    latest = backups[0]
    backup_name = latest.get("name")
    latest_ts = latest.get("timestamp")
    verification = latest.get("verification", {})
    is_verified = verification.get("verified", False) if verification else False

    # Calculate age
    backup_age_hours: float | None = None
    backup_recent = False
    warnings: list[str] = []

    if latest_ts:
        backup_age_hours = calculate_backup_age_hours(latest_ts)
        if backup_age_hours is not None:
            backup_recent = backup_age_hours <= max_age_hours
            if not backup_recent:
                warnings.append(
                    f"Backup is {backup_age_hours:.1f} hours old (limit: {max_age_hours}h)"
                )
        else:
            warnings.append("Could not parse backup timestamp")

    # Check verification status
    if require_verification and not is_verified:
        warnings.append("Latest backup has not been verified")

    # Determine if we can proceed
    can_proceed = True
    blocking_reason = None

    if not backup_recent:
        can_proceed = False
        blocking_reason = f"No recent backup. Latest backup is {backup_age_hours:.1f}h old (requires <{max_age_hours}h)."

    if require_verification and not is_verified:
        # Verification is a strong requirement - block if missing
        can_proceed = False
        if blocking_reason:
            blocking_reason += " Also, backup is not verified."
        else:
            blocking_reason = "Latest backup has not been verified."

    logger.info(
        "backup_requirements_checked",
        backup_name=backup_name,
        backup_age_hours=backup_age_hours,
        is_verified=is_verified,
        can_proceed=can_proceed,
    )

    return {
        "backup_exists": True,
        "backup_recent": backup_recent,
        "backup_verified": is_verified,
        "backup_name": backup_name,
        "backup_age_hours": backup_age_hours,
        "can_proceed": can_proceed,
        "blocking_reason": blocking_reason,
        "warnings": warnings,
    }
