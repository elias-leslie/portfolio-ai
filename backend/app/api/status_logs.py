"""Log viewing and management endpoints."""

from __future__ import annotations

import logging
import os
import subprocess

from fastapi import APIRouter, HTTPException

from ..logging_config import get_logger
from .status_logs_core.constants import VALID_LEVELS
from .status_logs_core.log_helpers import (
    fetch_all_logs,
    get_sorted_levels,
    process_logs,
    run_set_log_level_script,
)
from .status_logs_core.models import (
    LogLevelConfigResponse,
    SetLogLevelRequest,
    SetLogLevelResponse,
    TestLoggingResponse,
    UnifiedLogsResponse,
)
from .status_logs_core.validators import normalize_log_level, validate_log_params

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "logs"])


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
        logs = fetch_all_logs(service, since)
        limited_logs, level_counts = process_logs(logs, level, lines)
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
    available_levels = get_sorted_levels(reverse=True)
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
        run_set_log_level_script(level)
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

    levels_list = get_sorted_levels()
    return TestLoggingResponse(
        success=True,
        message=f"Generated test logs at all levels ({', '.join(levels_list)})",
        levels_tested=levels_list,
    )
