"""Backup management API endpoints for portfolio-ai.

This module provides endpoints for:
- Viewing backup status and history
- Triggering on-demand backups
- Monitoring backup job progress
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])

# Configuration
PROJECT_DIR = Path.home() / "portfolio-ai"
BACKUP_INDEX_PATH = PROJECT_DIR / "backup-index.json"
BACKUP_SCRIPT = PROJECT_DIR / "scripts" / "backup.sh"

# In-memory job tracking (simple approach for single-instance)
_running_jobs: dict[str, dict[str, Any]] = {}


# Response Models
class TreeEntry(BaseModel):
    """File count for a directory/file in the backup."""

    count: int


class BackupVerification(BaseModel):
    """Verification results for a backup."""

    verified: bool
    verified_at: str
    errors: list[str]
    tree: dict[str, TreeEntry]
    total_files: int
    checksum: str


class BackupEntry(BaseModel):
    """Individual backup entry."""

    name: str
    timestamp: str
    size_bytes: int
    db_size_bytes: int
    status: Literal["ok", "failed", "in_progress"]
    verification: BackupVerification | None = None


class BackupIndexResponse(BaseModel):
    """Backup index response."""

    version: int
    retention: int
    destination: str
    backups: list[BackupEntry]
    last_updated: str | None


class BackupStatusResponse(BaseModel):
    """Backup status summary response."""

    status: Literal["healthy", "stale", "no_backups", "error"]
    latest_backup: BackupEntry | None
    backup_count: int
    destination: str
    last_updated: str | None
    message: str


class TriggerBackupResponse(BaseModel):
    """Response when triggering a backup."""

    job_id: str
    status: Literal["started", "already_running"]
    message: str


class BackupJobStatus(BaseModel):
    """Status of a running or completed backup job."""

    job_id: str
    status: Literal["running", "completed", "failed", "not_found"]
    started_at: str | None
    completed_at: str | None
    output: str | None = Field(None, description="Command output (truncated)")
    error: str | None


def _read_backup_index() -> dict[str, Any]:
    """Read and parse the backup index file."""
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
        raise HTTPException(status_code=500, detail=f"Failed to read backup index: {e}") from e


def _determine_backup_health(index: dict[str, Any]) -> tuple[str, str]:
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


def _run_backup_in_background(job_id: str, quick_mode: bool = False) -> None:
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

        _running_jobs[job_id]["completed_at"] = datetime.now().isoformat()
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
        _running_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        logger.error("backup_job_timeout", job_id=job_id)

    except Exception as e:
        _running_jobs[job_id]["status"] = "failed"
        _running_jobs[job_id]["error"] = str(e)
        _running_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        logger.error("backup_job_exception", job_id=job_id, error=str(e))


@router.get("/status", response_model=BackupStatusResponse)
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup status summary.

    Returns backup health, latest backup info, and count.
    Use this for dashboard widgets and quick status checks.
    """
    index = _read_backup_index()
    backups = index.get("backups", [])

    status, message = _determine_backup_health(index)

    latest = None
    if backups:
        latest = BackupEntry(**backups[0])

    logger.info(
        "backup_status_checked",
        status=status,
        backup_count=len(backups),
        latest=backups[0].get("name") if backups else None,
    )

    return BackupStatusResponse(
        status=status,  # type: ignore[arg-type]
        latest_backup=latest,
        backup_count=len(backups),
        destination=index.get("destination", "unknown"),
        last_updated=index.get("last_updated"),
        message=message,
    )


@router.get("/latest", response_model=BackupEntry | None)
async def get_latest_backup() -> BackupEntry | None:
    """Get the most recent backup entry.

    Returns None if no backups exist.
    """
    index = _read_backup_index()
    backups = index.get("backups", [])

    if not backups:
        return None

    return BackupEntry(**backups[0])


@router.get("/history", response_model=BackupIndexResponse)
async def get_backup_history() -> BackupIndexResponse:
    """Get full backup history.

    Returns all backups in the index file (most recent first).
    """
    index = _read_backup_index()

    return BackupIndexResponse(
        version=index.get("version", 1),
        retention=index.get("retention", 30),
        destination=index.get("destination", "unknown"),
        backups=[BackupEntry(**b) for b in index.get("backups", [])],
        last_updated=index.get("last_updated"),
    )


@router.post("/trigger", response_model=TriggerBackupResponse)
async def trigger_backup(
    background_tasks: BackgroundTasks,
    quick: bool = False,
) -> TriggerBackupResponse:
    """Trigger an on-demand backup.

    Args:
        quick: If true, skip fresh DB dump and use existing daily backup.

    Returns:
        Job ID that can be used to check status.
    """
    # Check if a backup is already running
    for job_id, job in _running_jobs.items():
        if job.get("status") == "running":
            logger.info("backup_already_running", existing_job_id=job_id)
            return TriggerBackupResponse(
                job_id=job_id,
                status="already_running",
                message=f"A backup is already running (job {job_id})",
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
        "started_at": datetime.now().isoformat(),
        "completed_at": None,
        "output": None,
        "error": None,
        "quick_mode": quick,
    }

    # Start backup in background
    background_tasks.add_task(_run_backup_in_background, job_id, quick)

    logger.info("backup_triggered", job_id=job_id, quick_mode=quick)

    return TriggerBackupResponse(
        job_id=job_id,
        status="started",
        message=f"Backup started (job {job_id}). Use GET /api/backup/job/{job_id} to check status.",
    )


@router.get("/job/{job_id}", response_model=BackupJobStatus)
async def get_backup_job_status(job_id: str) -> BackupJobStatus:
    """Get status of a backup job.

    Args:
        job_id: The job ID returned from POST /trigger

    Returns:
        Job status including output if completed.
    """
    if job_id not in _running_jobs:
        return BackupJobStatus(
            job_id=job_id,
            status="not_found",
            started_at=None,
            completed_at=None,
            output=None,
            error="Job not found. It may have expired or never existed.",
        )

    job = _running_jobs[job_id]
    job_status = job.get("status", "not_found")
    # Validate status is one of the allowed values
    valid_statuses = {"running", "completed", "failed", "not_found"}
    if job_status not in valid_statuses:
        job_status = "not_found"

    return BackupJobStatus(
        job_id=job_id,
        status=job_status,
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        output=job.get("output"),
        error=job.get("error"),
    )
