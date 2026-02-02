"""Backup management API endpoints for portfolio-ai.

This module provides endpoints for:
- Viewing backup status and history
- Triggering on-demand backups
- Monitoring backup job progress
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..logging_config import get_logger
from .backup_models import (
    BackupEntry,
    BackupIndexResponse,
    BackupJobStatus,
    BackupRequirementCheck,
    BackupStatusResponse,
    TriggerBackupResponse,
)
from .backup_service import (
    check_requirements,
    create_backup_job,
    determine_backup_health,
    get_job_status,
    read_backup_index,
    run_backup_in_background,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/status", response_model=BackupStatusResponse)
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup status summary.

    Returns backup health, latest backup info, and count.
    Use this for dashboard widgets and quick status checks.
    """
    try:
        index = read_backup_index()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    backups = index.get("backups", [])
    status, message = determine_backup_health(index)

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
    try:
        index = read_backup_index()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    backups = index.get("backups", [])

    if not backups:
        return None

    return BackupEntry(**backups[0])


@router.get("/history", response_model=BackupIndexResponse)
async def get_backup_history() -> BackupIndexResponse:
    """Get full backup history.

    Returns all backups in the index file (most recent first).
    """
    try:
        index = read_backup_index()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

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
    job_id, status, message = create_backup_job(quick)

    if status == "started":
        # Start backup in background
        background_tasks.add_task(run_backup_in_background, job_id, quick)

    return TriggerBackupResponse(
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        message=message,
    )


@router.get("/job/{job_id}", response_model=BackupJobStatus)
async def get_backup_job_status(job_id: str) -> BackupJobStatus:
    """Get status of a backup job.

    Args:
        job_id: The job ID returned from POST /trigger

    Returns:
        Job status including output if completed.
    """
    job_data = get_job_status(job_id)
    return BackupJobStatus(**job_data)


@router.get("/check-requirements", response_model=BackupRequirementCheck)
async def check_backup_requirements(
    max_age_hours: float = 24.0,
    require_verification: bool = True,
) -> BackupRequirementCheck:
    """Check if backup requirements are met for maintenance operations.

    This endpoint should be called before any destructive maintenance operation
    to ensure a recent, verified backup exists.

    Args:
        max_age_hours: Maximum age of backup in hours (default: 24)
        require_verification: Whether backup must be verified (default: True)

    Returns:
        BackupRequirementCheck with can_proceed flag and details
    """
    try:
        result = check_requirements(max_age_hours, require_verification)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return BackupRequirementCheck(**result)
