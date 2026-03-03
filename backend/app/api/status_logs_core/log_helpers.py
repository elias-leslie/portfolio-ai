"""Helper functions for log fetching, processing, and script execution."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import HTTPException

from ...constants.services import SERVICE_UNIT_MAPPING, USER_MODE_SERVICES
from ...logging_config import get_logger
from .constants import (
    JOURNAL_FETCH_LIMIT,
    LOG_LEVEL_PRIORITY,
    SCRIPT_EXECUTION_TIMEOUT_SECONDS,
    VALID_LEVELS,
)
from .journal_parser import count_log_levels, fetch_journal_logs, merge_consecutive_logs
from .models import UnifiedLogEntry

logger = get_logger(__name__)


def categorize_units(
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
        unit = service_units.get(service)
        if not unit:
            return [], []
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


def get_sorted_levels(reverse: bool = False) -> list[str]:
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


def fetch_all_logs(
    service: str | None, since: str
) -> list[UnifiedLogEntry]:
    """Fetch and combine logs from both system and user journald units.

    Args:
        service: Optional service filter
        since: Time range string

    Returns:
        Combined list of log entries from system and user units
    """
    system_units, user_units = categorize_units(SERVICE_UNIT_MAPPING, service)
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


def process_logs(
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
    logs = sorted(logs, key=lambda x: x.timestamp)
    level_counts = count_log_levels(logs)

    filtered = [log for log in logs if log.level == level] if level else logs
    merged = merge_consecutive_logs(filtered)
    limited = merged[-lines:] if len(merged) > lines else merged
    return limited, level_counts


def run_set_log_level_script(level: str) -> None:
    """Execute the set-log-level.sh script with the given level.

    Args:
        level: Validated log level string

    Raises:
        HTTPException: 500 if the script fails, 504 if it times out
    """
    # parents[3] traverses: status_logs_core -> api -> app -> backend root
    project_root = Path(__file__).parents[3]
    script_path = project_root / "scripts" / "set-log-level.sh"
    try:
        result = subprocess.run(
            ["bash", str(script_path), level],
            capture_output=True,
            text=True,
            timeout=SCRIPT_EXECUTION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as err:
        logger.error("set_log_level_timeout", timeout=SCRIPT_EXECUTION_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=504,
            detail=f"set-log-level.sh timed out after {SCRIPT_EXECUTION_TIMEOUT_SECONDS}s",
        ) from err

    if result.returncode != 0:
        logger.error("set_log_level_failed", stderr=result.stderr, returncode=result.returncode)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set log level: {result.stderr or 'Unknown error'}",
        )
