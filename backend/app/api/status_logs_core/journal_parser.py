"""Journald log parsing and fetching."""

import json
import subprocess
from datetime import UTC, datetime
from typing import cast

from ...logging_config import get_logger
from .constants import JOURNALCTL_TIMEOUT_SECONDS, LOG_LEVEL_PRIORITY, SYSLOG_PRIORITY_TO_LEVEL
from .models import UnifiedLogEntry
from .validators import validate_since_parameter

logger = get_logger(__name__)


def _extract_journald_timestamp(entry: dict[str, object]) -> datetime:
    """Extract timestamp from journald entry (microsecond precision)."""
    timestamp_us = int(cast(int, entry.get("__REALTIME_TIMESTAMP", 0)))
    return datetime.fromtimestamp(timestamp_us / 1000000, tz=UTC)


def _map_service_name(entry: dict[str, object], service_units: dict[str, str]) -> str:
    """Map systemd unit to service name.

    Args:
        entry: Journald entry dict
        service_units: Mapping of service names to unit names

    Returns:
        Service name or "unknown" if no match
    """
    unit = str(entry.get("_SYSTEMD_UNIT", "") or entry.get("UNIT", ""))
    for svc, unit_name in service_units.items():
        if unit_name in unit:
            return svc
    return "unknown"


def _extract_message(entry: dict[str, object]) -> str | None:
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


def _determine_log_level(entry: dict[str, object]) -> str:
    """Determine log level from journald PRIORITY field."""
    priority = int(cast(int, entry.get("PRIORITY", 6)))  # Default to info (6)
    return SYSLOG_PRIORITY_TO_LEVEL.get(priority, "UNKNOWN")


def _is_systemd_control_message(message: str) -> bool:
    """Check if message is a systemd control message (start/stop notifications).

    Args:
        message: Log message to check

    Returns:
        True if message is a systemd control message, False otherwise
    """
    return (
        message.startswith("Starting ")
        or message.startswith("Started ")
        or message.startswith("Stopping ")
        or message.startswith("Stopped ")
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

            timestamp = _extract_journald_timestamp(entry)
            service_name = _map_service_name(entry, service_units)
            message = _extract_message(entry)

            # Skip if message extraction failed or is empty
            if message is None or not message.strip():
                continue

            # Skip systemd control messages (service start/stop notifications)
            if _is_systemd_control_message(message):
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

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.debug("journal_entry_parse_failed", error=str(e), line=line[:100])
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

    # Validate 'since' parameter to prevent command injection
    validated_since = validate_since_parameter(since)

    cmd = [
        "journalctl",
        "--no-pager",
        "-o",
        "json",
        "--since",
        validated_since,
        "-n",
        str(fetch_limit),
    ]

    if is_user_mode:
        cmd.insert(1, "--user")

    for unit in units:
        cmd.extend(["-u", unit])

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=JOURNALCTL_TIMEOUT_SECONDS, check=False
        )
        if result.returncode == 0:
            return parse_journal_output(result.stdout, service_units)
    except Exception as e:
        mode = "user" if is_user_mode else "system"
        logger.warning(f"{mode}_journal_fetch_failed", error=str(e))

    return []


def count_log_levels(logs: list[UnifiedLogEntry]) -> dict[str, int]:
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


def merge_consecutive_logs(logs: list[UnifiedLogEntry]) -> list[UnifiedLogEntry]:
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
