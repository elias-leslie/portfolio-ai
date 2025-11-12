"""Status and monitoring endpoints for real-time service information."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from collections import deque
from datetime import UTC, datetime, timedelta
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
    level_counts: dict[str, int] = Field(
        description="Count of each log level in unfiltered data (for dropdown display)"
    )
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

    Fetches a large sample from journald (10,000 entries) to ensure fair representation
    of all services, then filters and returns the requested number of entries.

    Args:
        lines: Maximum number of log entries to return (default 500, max 5000)
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

    valid_levels = {"CRITICAL", "ERROR", "WARN", "INFO", "DEBUG"}
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
        # Fetch more logs than requested to ensure fair representation across all services
        # (e.g., if backend has 10k logs but celery has 100, we want to see both)
        fetch_limit = 10000  # Fetch up to 10k logs from journald
        cmd = ["journalctl", "--no-pager", "-o", "json", "--since", since, "-n", str(fetch_limit)]

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
                # MESSAGE can be a string or list (for binary data)
                message_raw = entry.get("MESSAGE", "")
                if isinstance(message_raw, list):
                    # Binary message - convert bytes to string
                    try:
                        message = "".join(
                            chr(b) if isinstance(b, int) else str(b) for b in message_raw
                        )
                    except (ValueError, TypeError):
                        continue  # Skip if we can't decode
                else:
                    message = str(message_raw)

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

                # Use journald's native PRIORITY field (syslog levels)
                # With SyslogPrefixFormatter, Python logs now have correct priority prefixes
                # that systemd parses into the PRIORITY field
                # 0=emerg, 1=alert, 2=crit, 3=err, 4=warning, 5=notice, 6=info, 7=debug
                priority = int(entry.get("PRIORITY", 6))  # Default to info (6)

                if priority <= 2:  # Emergency, Alert, Critical
                    log_level = "CRITICAL"
                elif priority == 3:  # Error
                    log_level = "ERROR"
                elif priority == 4:  # Warning
                    log_level = "WARN"
                elif priority in {5, 6}:  # Notice, Informational
                    log_level = "INFO"
                elif priority == 7:  # Debug
                    log_level = "DEBUG"
                else:
                    log_level = "UNKNOWN"

                # Collect all logs (don't filter yet - we need counts of all levels)
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

        # Calculate level counts from ALL logs (before filtering)
        level_counts: dict[str, int] = {
            "CRITICAL": 0,
            "ERROR": 0,
            "WARN": 0,
            "INFO": 0,
            "DEBUG": 0,
            "UNKNOWN": 0,
        }
        for log in logs:
            level_counts[log.level] = level_counts.get(log.level, 0) + 1

        # Apply level filter if specified (exact match)
        if level:
            # Exact match: only show logs at the specified level
            filtered_logs = [log for log in logs if log.level == level]
        else:
            filtered_logs = logs

        # Merge consecutive entries with same timestamp and service (handles multi-line PostgreSQL logs)
        merged_logs: list[UnifiedLogEntry] = []
        for log in filtered_logs:
            if (
                merged_logs
                and merged_logs[-1].timestamp == log.timestamp
                and merged_logs[-1].service == log.service
            ):
                # Same timestamp and service - merge messages
                merged_logs[-1].message += "\n" + log.message
                # Upgrade level if new entry has higher severity
                level_priority_merge = {
                    "CRITICAL": 5,
                    "ERROR": 4,
                    "WARN": 3,
                    "INFO": 2,
                    "DEBUG": 1,
                    "UNKNOWN": 0,
                }
                if level_priority_merge.get(log.level, 0) > level_priority_merge.get(
                    merged_logs[-1].level, 0
                ):
                    merged_logs[-1].level = log.level
            else:
                # Different timestamp or service - add as new entry
                merged_logs.append(log)

        # Limit to requested number of entries (take most recent)
        # We fetched a large sample (10k) to ensure all services are represented,
        # now return only what the user requested
        limited_logs = merged_logs[-lines:] if len(merged_logs) > lines else merged_logs

        return UnifiedLogsResponse(
            logs=limited_logs,
            total_entries=len(limited_logs),
            level_counts=level_counts,
        )

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


class LogLevelConfigResponse(BaseModel):
    """Log level configuration information."""

    current_level: str = Field(description="Current log level (INFO, DEBUG, WARN, ERROR)")
    available_levels: list[str] = Field(description="Available log levels")
    configuration_method: str = Field(description="How to change the log level")
    restart_required: bool = Field(description="Whether restart is required after change")


@router.get("/log-level", response_model=LogLevelConfigResponse)
def get_log_level_config() -> LogLevelConfigResponse:
    """Get current log level configuration.

    Returns:
        LogLevelConfigResponse: Current log level and configuration info
    """
    current_level = os.getenv("LOG_LEVEL", "INFO")

    return LogLevelConfigResponse(
        current_level=current_level,
        available_levels=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
        configuration_method="API endpoint: POST /api/status/log-level",
        restart_required=True,
    )


class SetLogLevelRequest(BaseModel):
    """Request to set log level."""

    level: str = Field(description="Log level to set (DEBUG, INFO, WARN, ERROR, CRITICAL)")


class SetLogLevelResponse(BaseModel):
    """Response from setting log level."""

    success: bool = Field(description="Whether the operation succeeded")
    level: str = Field(description="Log level that was set")
    message: str = Field(description="Status message")
    restart_required: bool = Field(description="Whether services need restart")


@router.post("/log-level", response_model=SetLogLevelResponse)
async def set_log_level(request: SetLogLevelRequest) -> SetLogLevelResponse:
    """Set global log level for all services.

    This updates systemd configuration and restarts services automatically.

    Args:
        request: SetLogLevelRequest with desired level

    Returns:
        SetLogLevelResponse: Status of the operation

    Raises:
        HTTPException: 400 if invalid level, 500 if operation fails
    """
    level = request.level.upper()

    # Validate level
    valid_levels = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR", "CRITICAL"}
    if level not in valid_levels:
        raise HTTPException(
            status_code=400,
            detail="Invalid log level. Must be one of: DEBUG, INFO, WARN, ERROR, CRITICAL",
        )

    # Normalize WARNING to WARN
    if level == "WARNING":
        level = "WARN"

    try:
        # Run script to update systemd configs
        # Script uses sudo internally for tee and systemctl
        # Requires sudoers rule for passwordless execution
        script_path = "/home/kasadis/portfolio-ai/scripts/set-log-level.sh"
        result = subprocess.run(
            ["bash", script_path, level],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            logger.error("set_log_level_failed", stderr=result.stderr, returncode=result.returncode)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to set log level: {result.stderr or 'Unknown error'}",
            )

        logger.info("log_level_changed", level=level)

        return SetLogLevelResponse(
            success=True,
            level=level,
            message=f"Log level set to {level}. Restart services to apply changes.",
            restart_required=True,
        )

    except subprocess.TimeoutExpired as e:
        logger.error("set_log_level_timeout", error=str(e))
        raise HTTPException(status_code=504, detail="Operation timed out") from e

    except Exception as e:
        logger.error("set_log_level_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error setting log level: {e!s}") from e


class RestartServicesResponse(BaseModel):
    """Response from restarting services."""

    success: bool = Field(description="Whether the operation succeeded")
    message: str = Field(description="Status message")


@router.post("/restart-services", response_model=RestartServicesResponse)
async def restart_services() -> RestartServicesResponse:
    """Restart all Portfolio AI services.

    Uses nohup to run restart script in background to avoid killing itself.
    The backend will restart itself as part of this operation.

    Returns:
        RestartServicesResponse: Status of the operation

    Raises:
        HTTPException: 500 if operation fails
    """
    try:
        restart_script = "/home/kasadis/portfolio-ai/scripts/restart.sh"
        logger.info("restart_services_start", script=restart_script)

        # Run restart in background with nohup to avoid killing the process that's running it
        # The script will restart the backend, which would kill this request otherwise
        subprocess.Popen(
            ["nohup", "bash", restart_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Give a moment for the script to start
        await asyncio.sleep(0.5)

        logger.info("restart_services_triggered")

        return RestartServicesResponse(
            success=True,
            message="Services are restarting. This will take about 10 seconds. Refresh the page after.",
        )

    except Exception as e:
        logger.error("restart_services_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error triggering restart: {e!s}") from e


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


class TestLoggingResponse(BaseModel):
    """Response from test logging endpoint."""

    success: bool
    message: str
    levels_tested: list[str]


@router.post("/test-logging", response_model=TestLoggingResponse)
def test_logging() -> TestLoggingResponse:
    """Generate test logs at all levels to verify logging configuration.

    This endpoint generates one log entry at each level (DEBUG, INFO, WARN, ERROR, CRITICAL)
    to test that log levels are properly configured and appear in journald with correct PRIORITY.

    Returns:
        TestLoggingResponse: Confirmation that test logs were generated
    """
    # Get both structured and standard Python logger
    test_logger = logging.getLogger("app.api.status.test_logging")

    # Test all log levels
    test_logger.debug("DEBUG test log from backend")
    test_logger.info("INFO test log from backend")
    test_logger.warning("WARNING test log from backend")
    test_logger.error("ERROR test log from backend")
    test_logger.critical("CRITICAL test log from backend")

    # Also test with structured logger
    logger.debug("test_debug_log", component="backend", test_type="structured")
    logger.info("test_info_log", component="backend", test_type="structured")
    logger.warning("test_warning_log", component="backend", test_type="structured")
    logger.error("test_error_log", component="backend", test_type="structured")
    # Note: structlog doesn't have critical(), it maps to error()

    return TestLoggingResponse(
        success=True,
        message="Generated test logs at all levels (DEBUG, INFO, WARN, ERROR, CRITICAL)",
        levels_tested=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
    )


class MLModelMetrics(BaseModel):
    """ML model training metrics."""

    model_name: str
    model_version: str
    trained_at: str
    training_samples: int
    test_samples: int
    accuracy: float
    precision_score: float
    recall_score: float
    f1_score: float
    useful_count: int
    not_useful_count: int


class MLModelStatusResponse(BaseModel):
    """ML model status for status page."""

    current_model: MLModelMetrics | None
    previous_model: MLModelMetrics | None
    total_training_samples: int
    models_trained: int
    next_training: str  # Estimated next training time


@router.get("/ml-model-metrics", response_model=MLModelStatusResponse)
async def get_ml_model_metrics() -> MLModelStatusResponse:
    """
    Get ML model training metrics for status page.

    Returns current and previous model metrics, total samples, and next training time.
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Get latest 2 models
            conn.execute(
                """
                SELECT
                    model_name, model_version, trained_at,
                    training_samples, test_samples,
                    accuracy, precision_score, recall_score, f1_score,
                    useful_count, not_useful_count
                FROM ml_model_metrics
                WHERE model_name = %s
                ORDER BY trained_at DESC
                LIMIT 2
            """,
                ["article_quality"],
            )

            models = conn.fetchall()

            current_model = None
            previous_model = None

            if len(models) >= 1:
                row = models[0]
                current_model = MLModelMetrics(
                    model_name=row[0],
                    model_version=row[1],
                    trained_at=row[2].isoformat(),
                    training_samples=row[3],
                    test_samples=row[4],
                    accuracy=row[5],
                    precision_score=row[6],
                    recall_score=row[7],
                    f1_score=row[8],
                    useful_count=row[9],
                    not_useful_count=row[10],
                )

            if len(models) >= 2:
                row = models[1]
                previous_model = MLModelMetrics(
                    model_name=row[0],
                    model_version=row[1],
                    trained_at=row[2].isoformat(),
                    training_samples=row[3],
                    test_samples=row[4],
                    accuracy=row[5],
                    precision_score=row[6],
                    recall_score=row[7],
                    f1_score=row[8],
                    useful_count=row[9],
                    not_useful_count=row[10],
                )

            # Count total models trained
            conn.execute(
                "SELECT COUNT(*) FROM ml_model_metrics WHERE model_name = %s",
                ["article_quality"],
            )
            count_row = conn.fetchone()
            models_trained = count_row[0] if count_row else 0

            # Total training samples (from current model)
            total_samples = (
                current_model.training_samples + current_model.test_samples if current_model else 0
            )

            # Next training: Daily at ~02:00 UTC (after OHLCV refresh)
            now = datetime.now(UTC)
            tomorrow_2am = (now + timedelta(days=1)).replace(
                hour=2, minute=0, second=0, microsecond=0
            )
            next_training = tomorrow_2am.isoformat()

            return MLModelStatusResponse(
                current_model=current_model,
                previous_model=previous_model,
                total_training_samples=total_samples,
                models_trained=models_trained,
                next_training=next_training,
            )

    except Exception as e:
        logger.error("failed_to_fetch_ml_metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch ML model metrics: {e}") from e


class TableFreshnessStatus(BaseModel):
    """Freshness status for a single table."""

    table_name: str = Field(description="Table name")
    last_updated: datetime | None = Field(description="Most recent timestamp in table")
    age_hours: float | None = Field(description="Age in hours since last update")
    status: str = Field(description="Status: fresh (within expected interval), stale (overdue)")
    row_count: int | None = Field(description="Total number of rows in table")
    expected_refresh_hours: int = Field(description="Expected refresh interval in hours")
    description: str = Field(description="Table description and update schedule")


class TableFreshnessResponse(BaseModel):
    """Response model for table freshness endpoint."""

    tables: list[TableFreshnessStatus] = Field(description="Freshness status for each table")
    fresh_count: int = Field(description="Number of fresh tables")
    stale_count: int = Field(description="Number of stale tables")
    critical_count: int = Field(description="Number of critical tables")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.get("/table-freshness", response_model=TableFreshnessResponse)
async def get_table_freshness() -> TableFreshnessResponse:
    """Get freshness status for all important tables.

    Returns table-level freshness metrics:
    - fresh: Data updated within last 24 hours
    - stale: Data 24-48 hours old
    - critical: Data >48 hours old

    Tables monitored:
    - day_bars: OHLCV market data
    - fear_greed_inputs: F&G raw inputs
    - fear_greed_daily: F&G calculated scores
    - fear_greed_components: F&G component scores
    - news: News articles
    - watchlist_items: User watchlist entries
    - positions: Portfolio positions
    - accounts: Portfolio accounts
    - price_cache: Real-time price cache
    """
    try:
        conn_mgr = get_connection_manager()

        # Define tables with their timestamp columns and expected refresh intervals (in hours)
        table_configs = [
            ("day_bars", "date", "date", 24, "Daily OHLCV market data"),
            ("fear_greed_inputs", "as_of_date", "date", 24, "Fear & Greed raw inputs"),
            ("fear_greed_daily", "as_of_date", "date", 24, "Fear & Greed calculated scores"),
            ("fear_greed_components", "as_of_date", "date", 24, "Fear & Greed component scores"),
            (
                "technical_indicators",
                "calculated_at",
                "timestamp",
                24,
                "Daily technical indicators (RSI, MACD, etc.)",
            ),
            (
                "news_cache",
                "fetched_at",
                "timestamp",
                2,
                "News articles (refreshes every ~1min, 2h tolerance)",
            ),
            (
                "watchlist_items",
                "updated_at",
                "timestamp",
                2,
                "Watchlist scores (refreshes every ~1min, 2h tolerance)",
            ),
            ("price_cache", "cached_at", "timestamp", 1, "Real-time price cache (on-demand)"),
            ("ml_model_metrics", "trained_at", "timestamp", 24, "ML model training metrics"),
            ("source_metrics", "calculated_at", "timestamp", 12, "News source quality profiling"),
        ]

        tables: list[TableFreshnessStatus] = []
        now = datetime.now(UTC)

        with conn_mgr.connection() as conn:
            for table_name, timestamp_col, col_type, expected_hours, desc in table_configs:
                try:
                    # Get latest timestamp
                    result = conn.execute(f"SELECT MAX({timestamp_col}) FROM {table_name}")
                    row = result.fetchone()
                    last_updated = row[0] if row else None

                    # Get row count
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row = result.fetchone()
                    row_count = row[0] if row else 0

                    # Calculate age and status based on expected refresh interval
                    age_hours = None
                    status = "unknown"

                    if last_updated:
                        # Convert date to datetime for age calculation
                        if col_type == "date":
                            last_updated = datetime.combine(
                                last_updated, datetime.min.time(), tzinfo=UTC
                            )

                        age_delta = now - last_updated
                        age_hours = age_delta.total_seconds() / 3600

                        # Status based on expected interval with 2x tolerance
                        if age_hours <= expected_hours:
                            status = "fresh"
                        elif age_hours <= expected_hours * 2:
                            status = "stale"
                        else:
                            status = "critical"

                    tables.append(
                        TableFreshnessStatus(
                            table_name=table_name,
                            last_updated=last_updated,
                            age_hours=age_hours,
                            status=status,
                            row_count=row_count,
                            expected_refresh_hours=expected_hours,
                            description=desc,
                        )
                    )

                except Exception as e:
                    logger.warning(f"failed_to_check_freshness_{table_name}", error=str(e))
                    # Add table with unknown status
                    tables.append(
                        TableFreshnessStatus(
                            table_name=table_name,
                            last_updated=None,
                            age_hours=None,
                            status="error",
                            row_count=0,
                            expected_refresh_hours=0,
                            description="Error checking table",
                        )
                    )

        # Calculate summary counts
        fresh_count = sum(1 for t in tables if t.status == "fresh")
        stale_count = sum(1 for t in tables if t.status == "stale")
        critical_count = sum(1 for t in tables if t.status == "critical")

        return TableFreshnessResponse(
            tables=tables,
            fresh_count=fresh_count,
            stale_count=stale_count,
            critical_count=critical_count,
        )

    except Exception as e:
        logger.error("failed_to_fetch_table_freshness", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch table freshness: {e}") from e
