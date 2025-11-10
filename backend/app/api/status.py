"""Status and monitoring endpoints for real-time service information."""

from __future__ import annotations

import json
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


class UnifiedLogEntry(BaseModel):
    """Single log entry from unified journald stream."""

    timestamp: datetime = Field(description="Log entry timestamp (unified from journald)")
    service: str = Field(description="Service name (backend, celery_worker, postgresql, etc.)")
    level: str = Field(description="Log level (ERROR, WARN, INFO, DEBUG, UNKNOWN)")
    message: str = Field(description="Log message content")

    class Config:
        """Allow mutation for merging multi-line logs."""

        frozen = False


class UnifiedLogsResponse(BaseModel):
    """Response model for unified logs endpoint."""

    logs: list[UnifiedLogEntry] = Field(description="Chronologically sorted log entries")
    total_entries: int = Field(description="Total number of log entries returned")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.get("/unified-logs", response_model=UnifiedLogsResponse)
async def get_unified_logs(
    lines: int = 500,
    service: str | None = None,
    level: str | None = None,
    since: str = "5 minutes ago",
) -> UnifiedLogsResponse:
    """Get unified chronological logs from all services via journald.

    Args:
        lines: Maximum number of log entries to retrieve (default 500, max 5000)
        service: Filter by service name (backend, celery_worker, celery_beat, frontend, redis, postgresql)
        level: Filter by log level (ERROR, WARN, INFO, DEBUG)
        since: Time range (e.g., "5 minutes ago", "1 hour ago", "today")

    Returns:
        UnifiedLogsResponse: Chronologically sorted log entries from all services

    Raises:
        HTTPException: 400 if parameters invalid, 500 if journalctl fails
    """
    # Validate parameters
    if lines < 1 or lines > 5000:
        raise HTTPException(status_code=400, detail="Lines must be between 1 and 5000")

    valid_services = {"backend", "celery_worker", "celery_beat", "frontend", "redis", "postgresql"}
    if service and service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Must be one of: {', '.join(valid_services)}",
        )

    valid_levels = {"ERROR", "WARN", "INFO", "DEBUG"}
    if level and level not in valid_levels:
        raise HTTPException(
            status_code=400, detail=f"Invalid level. Must be one of: {', '.join(valid_levels)}"
        )

    try:
        # Map service names to systemd unit names
        service_units = {
            "backend": "portfolio-backend",
            "celery_worker": "portfolio-celery",
            "celery_beat": "portfolio-beat",
            "frontend": "portfolio-frontend",
            "redis": "redis-server",
            "postgresql": "postgresql@16-main",
        }

        # Build journalctl command
        cmd = ["journalctl", "--no-pager", "-o", "json", "--since", since, "-n", str(lines)]

        # Add service filter if specified
        if service:
            cmd.extend(["-u", service_units[service]])
        else:
            # Include all portfolio services
            for unit in service_units.values():
                cmd.extend(["-u", unit])

        # Execute journalctl
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        # Parse journald JSON output
        logs: list[UnifiedLogEntry] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            try:
                entry = json.loads(line)

                # Extract timestamp (microsecond precision from journald)
                timestamp_us = int(entry.get("__REALTIME_TIMESTAMP", 0))
                timestamp = datetime.fromtimestamp(timestamp_us / 1000000, tz=UTC)

                # Extract service name from systemd unit
                unit = entry.get("_SYSTEMD_UNIT", "")
                service_name = "unknown"
                for svc, unit_name in service_units.items():
                    if unit_name in unit:
                        service_name = svc
                        break

                # Extract log message (keep newlines for multi-line messages)
                message = entry.get("MESSAGE", "")

                # Skip empty messages
                if not message.strip():
                    continue

                # Skip systemd control messages (service start/stop notifications)
                if (
                    service_name == "unknown"
                    or message.startswith("Starting ")
                    or message.startswith("Started ")
                    or message.startswith("Stopping ")
                    or message.startswith("Stopped ")
                ):
                    continue

                # Detect log level from message content (check first line)
                first_line = message.split("\n")[0] if "\n" in message else message
                msg_upper = first_line.upper()

                # Service-specific level detection
                if service_name == "redis":
                    # Redis uses symbols: # = warning, * = info, . = debug
                    if " # " in first_line:
                        log_level = "WARN"
                    elif " * " in first_line:
                        log_level = "INFO"
                    elif " . " in first_line:
                        log_level = "DEBUG"
                    else:
                        log_level = "INFO"
                elif "ERROR" in msg_upper or "FATAL" in msg_upper or "CRITICAL" in msg_upper:
                    log_level = "ERROR"
                elif "WARN" in msg_upper:
                    log_level = "WARN"
                elif "DEBUG" in msg_upper:
                    log_level = "DEBUG"
                elif "INFO" in msg_upper or "LOG:" in msg_upper:
                    log_level = "INFO"
                else:
                    log_level = "UNKNOWN"

                # Apply level filter if specified
                if level and log_level != level:
                    continue

                logs.append(
                    UnifiedLogEntry(
                        timestamp=timestamp,
                        service=service_name,
                        level=log_level,
                        message=message,
                    )
                )

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning("unified_logs_parse_error", error=str(e), line=line[:100])
                continue

        # Sort by timestamp (chronological order)
        logs.sort(key=lambda x: x.timestamp)

        # Merge consecutive entries with same timestamp and service (handles multi-line PostgreSQL logs)
        merged_logs: list[UnifiedLogEntry] = []
        for log in logs:
            if (
                merged_logs
                and merged_logs[-1].timestamp == log.timestamp
                and merged_logs[-1].service == log.service
            ):
                # Same timestamp and service - merge messages
                merged_logs[-1].message += "\n" + log.message
                # Upgrade level if new entry has higher severity
                level_priority = {"ERROR": 4, "WARN": 3, "INFO": 2, "DEBUG": 1, "UNKNOWN": 0}
                if level_priority.get(log.level, 0) > level_priority.get(merged_logs[-1].level, 0):
                    merged_logs[-1].level = log.level
            else:
                # Different timestamp or service - add as new entry
                merged_logs.append(log)

        return UnifiedLogsResponse(logs=merged_logs, total_entries=len(merged_logs))

    except subprocess.TimeoutExpired as e:
        logger.error("unified_logs_timeout", error=str(e))
        raise HTTPException(
            status_code=504, detail="Journalctl query timed out after 30 seconds"
        ) from e

    except subprocess.CalledProcessError as e:
        logger.error("unified_logs_failed", error=e.stderr)
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve logs: {e.stderr or 'Unknown error'}"
        ) from e

    except Exception as e:
        logger.error("unified_logs_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error retrieving unified logs: {e!s}") from e


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
