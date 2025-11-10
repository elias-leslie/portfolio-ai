"""Status and monitoring endpoints for real-time service information."""

from __future__ import annotations

import re
import subprocess
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..celery_app import celery_app
from ..logging_config import get_logger
from ..services.resource_monitor import (
    get_cpu_usage,
    get_db_pool_stats,
    get_disk_usage,
    get_memory_usage,
)
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])

# Log file paths for each service
# Service names match health endpoint (underscore format)
LOG_PATHS: dict[str, str] = {
    "backend": "/var/log/portfolio-ai/backend.log",
    "backend_error": "/var/log/portfolio-ai/backend-error.log",
    "celery_worker": "/var/log/portfolio-ai/celery-worker.log",
    "celery_worker_error": "/var/log/portfolio-ai/celery-worker-error.log",
    "celery_beat": "/var/log/portfolio-ai/celery-beat.log",
    "celery_beat_error": "/var/log/portfolio-ai/celery-beat-error.log",
    "frontend": "/var/log/portfolio-ai/frontend.log",
    "frontend_error": "/var/log/portfolio-ai/frontend-error.log",
    "redis": "/var/log/redis/redis-server.log",  # System redis log
    "postgresql": "/var/log/postgresql/postgresql-16-main.log",  # PostgreSQL log
    # Aliases for backward compatibility (hyphen format)
    "celery-worker": "/var/log/portfolio-ai/celery-worker.log",
    "celery-beat": "/var/log/portfolio-ai/celery-beat.log",
}

# ANSI escape code pattern for stripping colors
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class LogResponse(BaseModel):
    """Response model for log endpoint."""

    service: str = Field(description="Service name")
    log_file: str = Field(description="Log file path")
    lines: list[str] = Field(description="Log lines (last N lines)")
    total_lines: int = Field(description="Total number of lines returned")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


def tail_log_file(file_path: str, num_lines: int = 100) -> list[str]:
    """Read last N lines from a log file efficiently using deque.

    Args:
        file_path: Path to log file
        num_lines: Number of lines to read from end (default 100)

    Returns:
        List of log lines (ANSI codes stripped)

    Raises:
        FileNotFoundError: If log file doesn't exist
        PermissionError: If log file can't be read
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {file_path}")

    try:
        with path.open("r") as f:
            # Use deque with maxlen for efficient tail operation
            lines = deque(f, maxlen=num_lines)

            # Strip ANSI escape codes for clean output
            cleaned_lines = [ANSI_ESCAPE.sub("", line.rstrip()) for line in lines]

            return cleaned_lines

    except PermissionError as e:
        raise PermissionError(f"Permission denied reading log file: {file_path}") from e


@router.get("/logs/{service}", response_model=LogResponse)
async def get_service_logs(service: str, lines: int = 100) -> LogResponse:
    """Get recent log lines for a service.

    Args:
        service: Service name (backend, celery-worker, celery-beat, frontend)
        lines: Number of lines to retrieve (default 100, max 1000)

    Returns:
        LogResponse with recent log lines

    Raises:
        HTTPException: 400 if service invalid, 404 if log file not found, 403 if permission denied
    """
    # Validate service name (security: whitelist approach)
    if service not in LOG_PATHS:
        valid_services = ", ".join(LOG_PATHS.keys())
        raise HTTPException(
            status_code=400, detail=f"Invalid service. Must be one of: {valid_services}"
        )

    # Validate line count
    if lines < 1 or lines > 1000:
        raise HTTPException(status_code=400, detail="Lines must be between 1 and 1000")

    log_path = LOG_PATHS[service]

    try:
        log_lines = tail_log_file(log_path, num_lines=lines)

        return LogResponse(
            service=service,
            log_file=log_path,
            lines=log_lines,
            total_lines=len(log_lines),
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"Log file not found for service: {service}"
        ) from e

    except PermissionError as e:
        raise HTTPException(
            status_code=403, detail=f"Permission denied reading logs for service: {service}"
        ) from e

    except Exception as e:
        logger.error("get_service_logs_error", service=service, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error reading logs: {e!s}") from e


class DiskUsageResponse(BaseModel):
    """Disk usage information."""

    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    status: str


class MemoryUsageResponse(BaseModel):
    """Memory usage information."""

    total_gb: float
    used_gb: float
    available_gb: float
    percent_used: float
    status: str


class CpuUsageResponse(BaseModel):
    """CPU usage information."""

    percent_used: float
    cores: int
    status: str


class DatabasePoolResponse(BaseModel):
    """Database connection pool information."""

    pool_size: int
    checked_out: int
    overflow: int
    percent_used: float
    status: str


class ResourcesResponse(BaseModel):
    """System resources response."""

    disk: DiskUsageResponse
    memory: MemoryUsageResponse
    cpu: CpuUsageResponse
    database_pool: DatabasePoolResponse
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.get("/resources", response_model=ResourcesResponse)
def get_system_resources() -> ResourcesResponse:
    """Get current system resource usage (disk, memory, CPU, database pool).

    Returns:
        ResourcesResponse: System resource statistics with thresholds
    """
    logger.info("get_system_resources_request")

    try:
        # Get resource statistics
        disk = get_disk_usage()
        memory = get_memory_usage()
        cpu = get_cpu_usage()

        # Get database pool stats
        mgr = get_connection_manager()
        with mgr.connection() as conn:
            db_pool = get_db_pool_stats(conn)  # type: ignore[arg-type]

        return ResourcesResponse(
            disk=DiskUsageResponse(**disk),
            memory=MemoryUsageResponse(**memory),
            cpu=CpuUsageResponse(**cpu),
            database_pool=DatabasePoolResponse(**db_pool),
        )

    except Exception as e:
        logger.error("get_system_resources_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Error retrieving system resources: {e!s}"
        ) from e


class ServiceRestartResponse(BaseModel):
    """Response for service restart operation."""

    success: bool
    service: str
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


class CacheClearResponse(BaseModel):
    """Response for cache clear operation."""

    success: bool
    rows_deleted: int
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


class WatchlistRefreshResponse(BaseModel):
    """Response for watchlist refresh operation."""

    success: bool
    task_id: str
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.post("/services/{service}/restart", response_model=ServiceRestartResponse)
def restart_service(service: str) -> ServiceRestartResponse:
    """Restart a specific service.

    Args:
        service: Service name (backend, celery_worker, celery_beat, frontend, redis)

    Returns:
        ServiceRestartResponse: Result of restart operation
    """
    # Map service names from health endpoint to restart script names
    service_name_map = {
        "backend": "backend",
        "celery_worker": "celery",
        "celery_beat": "beat",
        "frontend": "frontend",
        "redis": "redis",
    }

    # Accept both underscore and non-underscore versions
    mapped_service = service_name_map.get(service, service)

    # Whitelist of valid mapped service names
    valid_services = ["backend", "celery", "beat", "frontend", "redis"]

    if mapped_service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(service_name_map.keys())}",
        )

    logger.info("restart_service_request", service=service, mapped_service=mapped_service)

    try:
        # Call restart script with mapped service name
        # __file__ is backend/app/api/status.py, go up 4 levels to project root
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "restart-service.sh"
        subprocess.run(
            [str(script_path), mapped_service],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        logger.info("restart_service_success", service=service, mapped_service=mapped_service)
        return ServiceRestartResponse(
            success=True,
            service=service,
            message=f"Service {service} restarted successfully",
        )

    except subprocess.TimeoutExpired as e:
        logger.error("restart_service_timeout", service=service)
        raise HTTPException(
            status_code=504, detail="Service restart timed out after 30 seconds"
        ) from e

    except subprocess.CalledProcessError as e:
        logger.error("restart_service_failed", service=service, error=e.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"Service restart failed: {e.stderr or 'Unknown error'}",
        ) from e

    except Exception as e:
        logger.error("restart_service_error", service=service, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error restarting service: {e!s}") from e


@router.post("/cache/clear", response_model=CacheClearResponse)
def clear_cache() -> CacheClearResponse:
    """Clear price cache table.

    Returns:
        CacheClearResponse: Result of cache clear operation
    """
    logger.info("clear_cache_request")

    try:
        mgr = get_connection_manager()
        with mgr.connection() as conn:
            # Delete all rows from price_cache table
            result = conn.execute("DELETE FROM price_cache")
            rows_deleted = result.rowcount if hasattr(result, "rowcount") else 0

        logger.info("clear_cache_success", rows_deleted=rows_deleted)
        return CacheClearResponse(
            success=True,
            rows_deleted=rows_deleted,
            message=f"Cleared {rows_deleted} cached price entries",
        )

    except Exception as e:
        logger.error("clear_cache_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {e!s}") from e


@router.post("/watchlist/refresh", response_model=WatchlistRefreshResponse)
def refresh_watchlist() -> WatchlistRefreshResponse:
    """Trigger manual watchlist refresh (Celery task).

    Returns:
        WatchlistRefreshResponse: Result with task ID
    """
    logger.info("refresh_watchlist_request")

    try:
        # Trigger the refresh_watchlist Celery task
        task = celery_app.send_task("app.tasks.refresh_watchlist")

        logger.info("refresh_watchlist_triggered", task_id=task.id)
        return WatchlistRefreshResponse(
            success=True,
            task_id=task.id,
            message=f"Watchlist refresh task triggered (ID: {task.id})",
        )

    except Exception as e:
        logger.error("refresh_watchlist_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Error triggering watchlist refresh: {e!s}"
        ) from e
