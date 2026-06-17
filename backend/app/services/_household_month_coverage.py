"""Shared month-coverage rules for household spending run-rates."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

# A complete month needs this many ledger rows to count as covered; below it
# the ledger usually has incidental rows, not the household's actual spend.
MIN_ROWS_PER_COVERED_MONTH = 20


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def previous_month(month: str) -> str:
    year, mm = int(month[:4]), int(month[5:7])
    if mm == 1:
        return f"{year - 1}-12"
    return f"{year}-{mm - 1:02d}"


def month_bounds(month: str) -> tuple[date, date]:
    year, mm = int(month[:4]), int(month[5:7])
    return date(year, mm, 1), date(year, mm, calendar.monthrange(year, mm)[1])


def trailing_complete_coverage_months(
    rows: list[dict[str, Any]],
    *,
    today: date,
    start_date: date | None = None,
    end_date: date | None = None,
    min_rows: int = MIN_ROWS_PER_COVERED_MONTH,
) -> list[str]:
    """Trailing contiguous run of full, substantively covered months.

    Excludes the current partial month and any calendar month clipped by the
    selected reporting window. This keeps monthly run-rates from being diluted
    by sparse historical receipts or inflated by month-to-date spend.
    """
    current_month = month_key(today)
    resolved_end = end_date or today
    counts: dict[str, int] = {}
    for row in rows:
        month = month_key(row["date"])
        month_start, month_end = month_bounds(month)
        if month >= current_month:
            continue
        if start_date is not None and month_start < start_date:
            continue
        if month_end > resolved_end:
            continue
        counts[month] = counts.get(month, 0) + 1

    covered = {month for month, count in counts.items() if count >= min_rows}
    if not covered:
        return []

    window: list[str] = []
    month = max(covered)
    while month in covered:
        window.append(month)
        month = previous_month(month)
    return sorted(window)
