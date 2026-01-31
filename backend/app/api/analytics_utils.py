"""Utility functions for analytics API endpoints."""

from __future__ import annotations

import datetime as dt

from fastapi import HTTPException


def parse_date_param(date: str | None) -> dt.date:
    """Parse optional date parameter, defaulting to today.

    Args:
        date: Date string in YYYY-MM-DD format or None

    Returns:
        Parsed date object

    Raises:
        HTTPException: If date format is invalid
    """
    if date is None:
        return dt.date.today()

    try:
        return dt.datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format: {date}. Use YYYY-MM-DD format.",
        ) from None


def validate_group_by(group_by: str) -> None:
    """Validate group_by parameter for peer comparisons.

    Args:
        group_by: Grouping method ("sector" or "industry")

    Raises:
        HTTPException: If group_by is invalid
    """
    if group_by not in ["sector", "industry"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by parameter: {group_by}. Use 'sector' or 'industry'.",
        )


def interpret_rvol(rvol: float) -> str:
    """Get human-readable interpretation of RVOL value.

    Args:
        rvol: Relative volume ratio (1.0 = normal volume)

    Returns:
        Human-readable interpretation string
    """
    if rvol >= 2.0:
        return "Very high volume (2x+ normal)"
    if rvol >= 1.5:
        return "High volume (1.5-2x normal)"
    if rvol >= 1.0:
        return "Above average volume"
    if rvol >= 0.5:
        return "Below average volume"
    return "Very low volume (<0.5x normal)"


def safe_round(value: float | None, decimals: int = 2) -> float | None:
    """Safely round a value or return None.

    Args:
        value: Value to round or None
        decimals: Number of decimal places

    Returns:
        Rounded value or None
    """
    return round(value, decimals) if value is not None else None
