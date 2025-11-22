"""Script-based maintenance operations router.

This module provides REST API endpoints for triggering maintenance scripts
(cleanup_old_news.py, vacuum_database.py, validate_data_integrity.py).
"""

from __future__ import annotations

from fastapi import APIRouter

from ...logging_config import get_logger
from .models import (
    CleanupNewsRequest,
    MaintenanceResult,
    VacuumDatabaseRequest,
    ValidateIntegrityRequest,
)
from .utils import run_maintenance_script

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.post("/cleanup-news", response_model=MaintenanceResult)
async def cleanup_news(request: CleanupNewsRequest) -> MaintenanceResult:
    """Trigger cleanup of old news articles.

    Args:
        request: Cleanup configuration (days, dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If cleanup fails
    """
    args = ["--days", str(request.days)]

    if request.dry_run:
        args.append("--dry-run")

    return await run_maintenance_script(
        script_name="cleanup_old_news.py",
        args=args,
        task_name="cleanup_news",
        dry_run=request.dry_run,
    )


@router.post("/vacuum-database", response_model=MaintenanceResult)
async def vacuum_database(request: VacuumDatabaseRequest) -> MaintenanceResult:
    """Trigger database vacuum operation.

    Args:
        request: Vacuum configuration (tables, dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If vacuum fails
    """
    args = []

    if request.dry_run:
        args.append("--dry-run")

    if request.tables:
        args.append("--tables")
        args.extend(request.tables)

    return await run_maintenance_script(
        script_name="vacuum_database.py",
        args=args,
        task_name="vacuum_database",
        dry_run=request.dry_run,
    )


@router.post("/validate-integrity", response_model=MaintenanceResult)
async def validate_integrity(request: ValidateIntegrityRequest) -> MaintenanceResult:
    """Trigger data integrity validation.

    Args:
        request: Validation configuration (dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If validation fails
    """
    args = []

    if request.dry_run:
        args.append("--dry-run")
    else:
        args.append("--fix")

    return await run_maintenance_script(
        script_name="validate_data_integrity.py",
        args=args,
        task_name="validate_integrity",
        dry_run=request.dry_run,
    )
