"""Log viewing and management endpoints."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..constants.services import SERVICE_UNIT_MAPPING, USER_MODE_SERVICES
from ..logging_config import get_logger
from .status_logs_core.constants import (
    JOURNAL_FETCH_LIMIT,
    LOG_LEVEL_PRIORITY,
    SCRIPT_EXECUTION_TIMEOUT_SECONDS,
    VALID_LEVELS,
)
from .status_logs_core.journal_parser import (
    count_log_levels,
    fetch_journal_logs,
    merge_consecutive_logs,
)
from .status_logs_core.models import (
    LogLevelConfigResponse,
    SetLogLevelRequest,
    SetLogLevelResponse,
    TestLoggingResponse,
    UnifiedLogEntry,
    UnifiedLogsResponse,
)
from .status_logs_core.validators import normalize_log_level, validate_log_params

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "logs"])


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
        unit = service_units.get(service, "")
        if service in USER_MODE_SERVICES:
            return [], [unit]
        return [unit], []

    system_units = []
    user_units = []
    for svc, unit in service_units.items():
        if svc in USER_MODE_SERVICES:
            user_units.append(unit)
        else:
            system_units.append(unit)
    return system_units, user_units


def _get_sorted_levels(reverse: bool = False) -> list[str]:
    """Get sorted list of valid log levels (excluding WARNING alias).

    Args:
        reverse: If True, sort from highest to lowest priority (default: False)

    Returns:
        List of valid log levels sorted by priority
    """
    return sorted(
        (level for level in VALID_LEVELS if level != "WARNING"),
        key=lambda lvl: LOG_LEVEL_PRIORITY.get(lvl, 0),
        reverse=reverse,
    )


def _fetch_all_logs(
    service: str | None, since: str
) -> list[UnifiedLogEntry]:
    """Fetch and combine logs from both system and user journald units.

    Args:
        service: Optional service filter
        since: Time range string

    Returns:
        Combined list of log entries from system and user units
    """
    system_units, user_units = _categorize_units(SERVICE_UNIT_MAPPING, service)
    fetch_limit = JOURNAL_FETCH_LIMIT

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
    return logs


def _process_logs(
    logs: list[UnifiedLogEntry],
    level: str | None,
    lines: int,
) -> tuple[list[UnifiedLogEntry], dict[str, int]]:
    """Sort, count, filter, merge, and limit log entries.

    Args:
        logs: Raw log entries to process
        level: Optional level filter
        lines: Maximum number of entries to return

    Returns:
        Tuple of (processed_logs, level_counts)
    """
    logs.sort(key=lambda x: x.timestamp)
    level_counts = count_log_levels(logs)

    filtered = [log for log in logs if log.level == level] if level else logs
    merged = merge_consecutive_logs(filtered)
    limited = merged[-lines:] if len(merged) > lines else merged
    return limited, level_counts


def _run_set_log_level_script(level: str) -> None:
    """Execute the set-log-level.sh script with the given level.

    Args:
        level: Validated log level string

    Raises:
        HTTPException: 500 if the script fails, 504 if it times out
    """
    script_path = Path(__file__).parent.parent.parent / "scripts" / "set-log-level.sh"
    result = subprocess.run(
        ["bash", str(script_path), level],
        capture_output=True,
        text=True,
        timeout=SCRIPT_EXECUTION_TIMEOUT_SECONDS,
        check=False,
    )

    if result.returncode != 0:
        logger.error("set_log_level_failed", stderr=result.stderr, returncode=result.returncode)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set log level: {result.stderr or 'Unknown error'}",
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
        lines: Maximum number of log entries to return (default 500, max MAX_LOG_LINES)
        service: Filter by service name (backend, hatchet_worker, frontend, redis, postgresql)
        level: Filter by log level (ERROR, WARN, INFO, DEBUG)
        since: Time range (e.g., "5 minutes ago", "1 hour ago", "today")

    Returns:
        UnifiedLogsResponse: Chronologically sorted log entries from all services

    Raises:
        HTTPException: 400 if parameters invalid, 500 if journalctl fails
    """
    validate_log_params(lines, service, level)

    try:
        logs = _fetch_all_logs(service, since)
        limited_logs, level_counts = _process_logs(logs, level, lines)
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


@router.get("/log-level", response_model=LogLevelConfigResponse)
def get_log_level_config() -> LogLevelConfigResponse:
    """Get current log level configuration.

    Returns:
        LogLevelConfigResponse: Current log level and configuration info
    """
    current_level = os.getenv("LOG_LEVEL", "INFO")
    available_levels = _get_sorted_levels(reverse=True)
    return LogLevelConfigResponse(
        current_level=current_level,
        available_levels=available_levels,
        configuration_method="API endpoint: POST /api/status/log-level",
        restart_required=True,
    )


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

    if level not in VALID_LEVELS:
        raise HTTPException(
            status_code=400,
            detail="Invalid log level. Must be one of: DEBUG, INFO, WARN, ERROR, CRITICAL",
        )

    level = normalize_log_level(level)

    try:
        _run_set_log_level_script(level)
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


@router.post("/test-logging", response_model=TestLoggingResponse)
def test_logging() -> TestLoggingResponse:
    """Generate test logs at all levels to verify logging configuration.

    This endpoint generates one log entry at each level (DEBUG, INFO, WARN, ERROR, CRITICAL)
    to test that log levels are properly configured and appear in journald with correct PRIORITY.

    Returns:
        TestLoggingResponse: Confirmation that test logs were generated
    """
    test_logger = logging.getLogger("app.api.status.test_logging")

    test_logger.debug("DEBUG test log from backend")
    test_logger.info("INFO test log from backend")
    test_logger.warning("WARNING test log from backend")
    test_logger.error("ERROR test log from backend")
    test_logger.critical("CRITICAL test log from backend")

    logger.debug("test_debug_log", component="backend", test_type="structured")
    logger.info("test_info_log", component="backend", test_type="structured")
    logger.warning("test_warning_log", component="backend", test_type="structured")
    logger.error("test_error_log", component="backend", test_type="structured")
    # Note: structlog doesn't have critical(), it maps to error()

    levels_list = _get_sorted_levels()
    return TestLoggingResponse(
        success=True,
        message=f"Generated test logs at all levels ({', '.join(levels_list)})",
        levels_tested=levels_list,
    )
