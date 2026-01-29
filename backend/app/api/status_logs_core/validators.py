"""Validation functions for log management."""

from fastapi import HTTPException

from ...constants.services import VALID_SERVICES
from .constants import MAX_LOG_LINES, VALID_LEVELS, VALID_SINCE_PATTERN


def validate_since_parameter(since: str) -> str:
    """Validate 'since' parameter against safe patterns.

    Args:
        since: Time range string (e.g., "5 minutes ago", "today")

    Returns:
        The validated 'since' string

    Raises:
        HTTPException: If the pattern is invalid
    """
    if not VALID_SINCE_PATTERN.match(since.strip()):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid 'since' parameter: '{since}'. "
            "Must be like '5 minutes ago', '1 hour ago', 'today', or 'yesterday'.",
        )
    return since.strip()


def normalize_log_level(level: str) -> str:
    """Normalize log level to standard form.

    Args:
        level: Log level string (may be "WARNING" alias)

    Returns:
        Normalized log level ("WARNING" -> "WARN", others unchanged)
    """
    return "WARN" if level == "WARNING" else level


def validate_log_params(lines: int, service: str | None, level: str | None) -> None:
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
