"""Shared time-window helpers for household ledger and spending views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

_WINDOW_DAY_COUNTS: dict[str, int | None] = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "12m": 365,
    "all": None,
}

_WINDOW_LABELS: dict[str, str] = {
    "1m": "Past 30 days",
    "3m": "Past 90 days",
    "6m": "Past 6 months",
    "12m": "Past 12 months",
    "all": "All dates",
}


@dataclass(frozen=True)
class HouseholdTimeWindow:
    key: str
    label: str
    start_date: date | None
    end_date: date
    window_months: int | None


def resolve_household_time_window(
    window: str | None,
    *,
    today: date | None = None,
) -> HouseholdTimeWindow:
    resolved_today = today or date.today()
    key = (window or "all").strip().lower()
    if key not in _WINDOW_DAY_COUNTS:
        key = "all"

    day_count = _WINDOW_DAY_COUNTS[key]
    start_date = (
        resolved_today - timedelta(days=day_count - 1)
        if day_count is not None
        else None
    )
    return HouseholdTimeWindow(
        key=key,
        label=_WINDOW_LABELS[key],
        start_date=start_date,
        end_date=resolved_today,
        window_months={
            "1m": 1,
            "3m": 3,
            "6m": 6,
            "12m": 12,
            "all": None,
        }[key],
    )
