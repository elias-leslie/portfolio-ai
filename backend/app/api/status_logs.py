"""Log viewing and management endpoints."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..constants.services import SERVICE_UNIT_MAPPING, USER_MODE_SERVICES, VALID_SERVICES
from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "logs"])

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


class UnifiedLogEntry(BaseModel):
    """Single log entry from unified journald stream."""

    model_config = ConfigDict(validate_assignment=True)

    timestamp: datetime = Field(description="Log entry timestamp (unified from journald)")
    service: str = Field(description="Service name (backend, celery_worker, postgresql, etc.)")
    level: str = Field(description="Log level (ERROR, WARN, INFO, DEBUG, UNKNOWN)")
    message: str = Field(description="Log message content")


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


def _extract_timestamp(entry: dict) -> datetime:
    """Extract timestamp from journald entry (microsecond precision)."""
    timestamp_us = int(entry.get("__REALTIME_TIMESTAMP", 0))
    return datetime.fromtimestamp(timestamp_us / 1000000, tz=UTC)


def _map_service_name(entry: dict, service_units: dict[str, str]) -> str:
    """Map systemd unit to service name.

    Args:
        entry: Journald entry dict
        service_units: Mapping of service names to unit names

    Returns:
        Service name or "unknown" if no match
    """
    unit = entry.get("_SYSTEMD_UNIT", "") or entry.get("UNIT", "")
    for svc, unit_name in service_units.items():
        if unit_name in unit:
            return svc
    return "unknown"


def _extract_message(entry: dict) -> str | None:
    """Extract and decode message from journald entry.

    Args:
        entry: Journald entry dict

    Returns:
        Decoded message string, or None if extraction fails
    """
    message_raw = entry.get("MESSAGE", "")
    if isinstance(message_raw, list):
        try:
            return "".join(chr(b) if isinstance(b, int) else str(b) for b in message_raw)
        except (ValueError, TypeError):
            return None
    return str(message_raw)


def _determine_log_level(entry: dict) -> str:
    """Determine log level from journald PRIORITY field."""
    priority = int(entry.get("PRIORITY", 6))  # Default to info (6)
    return SYSLOG_PRIORITY_TO_LEVEL.get(priority, "UNKNOWN")


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

            timestamp = _extract_timestamp(entry)
            service_name = _map_service_name(entry, service_units)
            message = _extract_message(entry)

            # Skip if message extraction failed or is empty
            if message is None or not message.strip():
                continue

            # Skip systemd control messages (service start/stop notifications)
            if (
                message.startswith("Starting ")
                or message.startswith("Started ")
                or message.startswith("Stopping ")
                or message.startswith("Stopped ")
            ):
                continue

            log_level = _determine_log_level(entry)

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


def fetch_journal_logs(
    units: list[str],
    is_user_mode: bool,
    fetch_limit: int,
    since: str,
    service_units: dict[str, str],
) -> list[UnifiedLogEntry]:
    """Fetch logs from journald for specified units.

    Args:
        units: List of systemd unit names to fetch
        is_user_mode: Whether to use --user flag for user services
        fetch_limit: Maximum number of log entries to fetch
        since: Time range (e.g., "5 minutes ago")
        service_units: Mapping of service names to unit names (for parsing)

    Returns:
        List of parsed log entries
    """
    if not units:
        return []

    cmd = [
        "journalctl",
        "--no-pager",
        "-o",
        "json",
        "--since",
        since,
        "-n",
        str(fetch_limit),
    ]

    if is_user_mode:
        cmd.insert(1, "--user")

    for unit in units:
        cmd.extend(["-u", unit])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
        if result.returncode == 0:
            return parse_journal_output(result.stdout, service_units)
    except Exception as e:
        mode = "user" if is_user_mode else "system"
        logger.warning(f"{mode}_journal_fetch_failed", error=str(e))

    return []


# Derive VALID_LEVELS from LOG_LEVEL_PRIORITY (excluding UNKNOWN which is internal-only)
# Include "WARNING" as an alias for "WARN" for user convenience
VALID_LEVELS = {level for level in LOG_LEVEL_PRIORITY if level != "UNKNOWN"} | {"WARNING"}


def _validate_log_params(lines: int, service: str | None, level: str | None) -> None:
    """Validate unified log query parameters.

    Args:
        lines: Number of log lines requested
        service: Service filter (or None)
        level: Level filter (or None)

    Raises:
        HTTPException: If any parameter is invalid
    """
    if lines < 1 or lines > MAX_LOG_LINES:
        raise HTTPException(status_code=400, detail=f"Lines must be between 1 and {MAX_LOG_LINES}")

    if service and service not in VALID_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service. Must be one of: {', '.join(VALID_SERVICES)}",
        )

    if level and level not in VALID_LEVELS:
        raise HTTPException(
            status_code=400, detail=f"Invalid level. Must be one of: {', '.join(VALID_LEVELS)}"
        )


def _categorize_units(
    service_units: dict[str, str], service: str | None
) -> tuple[list[str], list[str]]:
    """Categorize service units into system and user units.

    Args:
        service_units: Mapping of service names to unit names
        service: Optional service filter

    Returns:
        Tuple of (system_units, user_units) lists
    """
    if service:
        # Single service filter
        unit = service_units.get(service, "")
        if service in USER_MODE_SERVICES:
            return [], [unit]
        return [unit], []

    # All services
    system_units = []
    user_units = []
    for svc, unit in service_units.items():
        if svc in USER_MODE_SERVICES:
            user_units.append(unit)
        else:
            system_units.append(unit)
    return system_units, user_units


def _count_log_levels(logs: list[UnifiedLogEntry]) -> dict[str, int]:
    """Count occurrences of each log level.

    Args:
        logs: List of log entries

    Returns:
        Dict with counts per level
    """
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
    return level_counts


def _merge_consecutive_logs(logs: list[UnifiedLogEntry]) -> list[UnifiedLogEntry]:
    """Merge consecutive logs with same timestamp and service.

    Handles multi-line PostgreSQL logs by combining messages.

    Args:
        logs: List of log entries (already filtered)

    Returns:
        List with consecutive same-timestamp entries merged
    """
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
            if LOG_LEVEL_PRIORITY.get(log.level, 0) > LOG_LEVEL_PRIORITY.get(
                merged_logs[-1].level, 0
            ):
                merged_logs[-1].level = log.level
        else:
            # Different timestamp or service - add as new entry
            merged_logs.append(log)
    return merged_logs


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
    # Validate parameters using helper
    _validate_log_params(lines, service, level)

    try:
        # Categorize units using helper (uses module-level SERVICE_UNIT_MAPPING)
        system_units, user_units = _categorize_units(SERVICE_UNIT_MAPPING, service)
        fetch_limit = JOURNAL_FETCH_LIMIT

        # Fetch logs from both system and user units
        logs: list[UnifiedLogEntry] = []
        logs.extend(
            fetch_journal_logs(
                system_units,
                is_user_mode=False,
                fetch_limit=fetch_limit,
                since=since,
                service_units=SERVICE_UNIT_MAPPING,
            )
        )
        logs.extend(
            fetch_journal_logs(
                user_units,
                is_user_mode=True,
                fetch_limit=fetch_limit,
                since=since,
                service_units=SERVICE_UNIT_MAPPING,
            )
        )

        # Sort by timestamp (chronological order)
        logs.sort(key=lambda x: x.timestamp)

        # Calculate level counts from ALL logs (before filtering) using helper
        level_counts = _count_log_levels(logs)

        # Apply level filter if specified (exact match)
        filtered_logs = [log for log in logs if log.level == level] if level else logs

        # Merge consecutive entries using helper
        merged_logs = _merge_consecutive_logs(filtered_logs)

        # Limit to requested number of entries (take most recent)
        limited_logs = merged_logs[-lines:] if len(merged_logs) > lines else merged_logs

        return UnifiedLogsResponse(
            logs=limited_logs,
            total_entries=len(limited_logs),
            level_counts=level_counts,
        )

    except subprocess.TimeoutExpired as e:
        logger.error("unified_logs_timeout", error=str(e))
        raise HTTPException(
            status_code=504, detail="Journalctl query timed out after 15 seconds"
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

    # Derive available levels from VALID_LEVELS, excluding WARNING alias
    available_levels = sorted(
        (level for level in VALID_LEVELS if level != "WARNING"),
        key=lambda lvl: LOG_LEVEL_PRIORITY.get(lvl, 0),
        reverse=True,
    )
    return LogLevelConfigResponse(
        current_level=current_level,
        available_levels=available_levels,
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
    if level not in VALID_LEVELS:
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

    # Derive levels list from VALID_LEVELS, excluding WARNING alias
    levels_list = sorted(
        (level for level in VALID_LEVELS if level != "WARNING"),
        key=lambda lvl: LOG_LEVEL_PRIORITY.get(lvl, 0),
    )
    return TestLoggingResponse(
        success=True,
        message=f"Generated test logs at all levels ({', '.join(levels_list)})",
        levels_tested=levels_list,
    )
