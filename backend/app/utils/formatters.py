"""Common formatters for data transformation.

Provides utilities for formatting dates, numbers, and other common types
consistently across the codebase.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def format_db_date(value: Any) -> str | None:
    """Format a database date value to ISO format string.

    Handles datetime, date, and string types safely. Returns None for
    null or invalid values.

    Args:
        value: Date value from database (datetime, date, str, or None)

    Returns:
        ISO format date string or None if value is null/invalid
    """
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return value  # Already a string, pass through
    return None


def format_db_date_required(value: Any, skip_invalid: bool = True) -> str | None:
    """Format a database date value, optionally signaling to skip invalid rows.

    Similar to format_db_date but designed for list building where invalid
    values should cause the row to be skipped.

    Args:
        value: Date value from database
        skip_invalid: If True, returns None for invalid values (caller should skip row)

    Returns:
        ISO format date string, or None if invalid and skip_invalid=True

    Raises:
        ValueError: If value is invalid and skip_invalid=False
    """
    result = format_db_date(value)
    if result is None and not skip_invalid:
        raise ValueError(f"Invalid date value: {value}")
    return result
