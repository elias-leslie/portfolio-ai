"""Shared date utilities for analytics modules."""

from __future__ import annotations

import datetime as dt


def parse_target_date(date: dt.date | str) -> dt.date:
    """Convert date input to date object.

    Args:
        date: Date as string (YYYY-MM-DD) or date object

    Returns:
        Date object
    """
    if isinstance(date, str):
        try:
            return dt.datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError as e:
            raise ValueError(f"Invalid date format: '{date}'. Expected YYYY-MM-DD.") from e
    return date
