"""Log viewing and management endpoints."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "logs"])

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

# Log level priority mapping for merging/comparison (higher = more severe)
LOG_LEVEL_PRIORITY: dict[str, int] = {
    "CRITICAL": 5,
    "ERROR": 4,
    "WARN": 3,
    "INFO": 2,
    "DEBUG": 1,
    "UNKNOWN": 0,
}

# Syslog priority to log level mapping (journald PRIORITY field)
SYSLOG_PRIORITY_TO_LEVEL: dict[int, str] = {
    0: "CRITICAL",  # Emergency
    1: "CRITICAL",  # Alert
    2: "CRITICAL",  # Critical
    3: "ERROR",  # Error
    4: "WARN",  # Warning
    5: "INFO",  # Notice
    6: "INFO",  # Informational
    7: "DEBUG",  # Debug
}

# Fetch limits
MAX_LOG_LINES = 5000
JOURNAL_FETCH_LIMIT = 10000


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


def parse_journal_output(output: str, service_units: dict[str, str]) -> list[UnifiedLogEntry]:
    """Parse JSON output from journalctl into UnifiedLogEntry objects.

    Args:
        output: Raw stdout from journalctl -o json
        service_units: Mapping of service names to unit names

    Returns:
        List of parsed log entries
    """
    logs: list[UnifiedLogEntry] = []
    for line in output.strip().split("\n"):
        if not line:
            continue

        try:
            entry = json.loads(line)

            # Extract timestamp (microsecond precision from journald)
            timestamp_us = int(entry.get("__REALTIME_TIMESTAMP", 0))
            timestamp = datetime.fromtimestamp(timestamp_us / 1000000, tz=UTC)

            # Extract service name from systemd unit
            # System services use _SYSTEMD_UNIT, user services might use _SYSTEMD_USER_UNIT?
            # Actually journalctl -o json output keys are standard.
            unit = entry.get("_SYSTEMD_UNIT", "") or entry.get("UNIT", "")

            # Map unit name back to service name
            service_name = "unknown"
            for svc, unit_name in service_units.items():
                # Check if unit name matches (relaxed matching for templated units like postgresql@)
                if unit_name in unit:
                    service_name = svc
                    break

            # If unknown, try to guess from SYSLOG_IDENTIFIER
            if service_name == "unknown":
                identifier = entry.get("SYSLOG_IDENTIFIER", "")
                if "portfolio" in identifier or "celery" in identifier:
                    # Keep it but mark as unknown service
                    pass
                else:
                    # Might be noise if we didn't filter by unit
                    pass

            # Extract log message (keep newlines for multi-line messages)
            # MESSAGE can be a string or list (for binary data)
            message_raw = entry.get("MESSAGE", "")
            if isinstance(message_raw, list):
                # Binary message - convert bytes to string
                try:
                    message = "".join(chr(b) if isinstance(b, int) else str(b) for b in message_raw)
                except (ValueError, TypeError):
                    continue  # Skip if we can't decode
            else:
                message = str(message_raw)

            # Skip empty messages
            if not message.strip():
                continue

            # Skip systemd control messages (service start/stop notifications)
            if (
                message.startswith("Starting ")
                or message.startswith("Started ")
                or message.startswith("Stopping ")
                or message.startswith("Stopped ")
            ):
                continue

            # Use journald's native PRIORITY field (syslog levels)
            priority = int(entry.get("PRIORITY", 6))  # Default to info (6)
            log_level = SYSLOG_PRIORITY_TO_LEVEL.get(priority, "UNKNOWN")

            # Collect log
            logs.append(
                UnifiedLogEntry(
                    timestamp=timestamp,
                    service=service_name,
                    level=log_level,
                    message=message,
                )
            )

        except (json.JSONDecodeError, KeyError, ValueError):
            continue

    return logs


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
        lines: Maximum number of log entries to return (default 500, max MAX_LOG_LINES)
        service: Filter by service name (backend, celery_worker, celery_beat, frontend, redis, postgresql)
        level: Filter by log level (ERROR, WARN, INFO, DEBUG)
        since: Time range (e.g., "5 minutes ago", "1 hour ago", "today")

    Returns:
        UnifiedLogsResponse: Chronologically sorted log entries from all services

    Raises:
        HTTPException: 400 if parameters invalid, 500 if journalctl fails
    """
    # Validate parameters
    if lines < 1 or lines > MAX_LOG_LINES:
        raise HTTPException(status_code=400, detail=f"Lines must be between 1 and {MAX_LOG_LINES}")

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

        # Build journalctl command for system units
        # Fetch more logs than requested to ensure fair representation across all services
        fetch_limit = JOURNAL_FETCH_LIMIT  # Fetch up to 10k logs from journald

        system_units = []
        user_units = []

        for svc, unit in service_units.items():
            if svc in ["celery_worker", "celery_beat"]:
                user_units.append(unit)
            else:
                system_units.append(unit)

        # Filter if specific service requested
        if service:
            if service in ["celery_worker", "celery_beat"]:
                system_units = []
                user_units = [service_units[service]]
            else:
                user_units = []
                system_units = [service_units[service]]

        logs: list[UnifiedLogEntry] = []

        # 1. Fetch System Logs
        if system_units:
            cmd_system = [
                "journalctl",
                "--no-pager",
                "-o",
                "json",
                "--since",
                since,
                "-n",
                str(fetch_limit),
            ]
            for unit in system_units:
                cmd_system.extend(["-u", unit])

            try:
                result_system = subprocess.run(
                    cmd_system, capture_output=True, text=True, timeout=15, check=False
                )
                if result_system.returncode == 0:
                    logs.extend(parse_journal_output(result_system.stdout, service_units))
            except Exception as e:
                logger.warning("system_journal_fetch_failed", error=str(e))

        # 2. Fetch User Logs
        if user_units:
            cmd_user = [
                "journalctl",
                "--user",
                "--no-pager",
                "-o",
                "json",
                "--since",
                since,
                "-n",
                str(fetch_limit),
            ]
            for unit in user_units:
                cmd_user.extend(["-u", unit])

            try:
                result_user = subprocess.run(
                    cmd_user, capture_output=True, text=True, timeout=15, check=False
                )
                if result_user.returncode == 0:
                    logs.extend(parse_journal_output(result_user.stdout, service_units))
            except Exception as e:
                logger.warning("user_journal_fetch_failed", error=str(e))

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
                if LOG_LEVEL_PRIORITY.get(log.level, 0) > LOG_LEVEL_PRIORITY.get(
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
        script_path = Path(__file__).parent.parent.parent / "scripts" / "set-log-level.sh"
        result = subprocess.run(
            ["bash", str(script_path), level],
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
