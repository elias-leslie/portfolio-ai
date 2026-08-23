"""The one definition of a household reporting period.

Every surface that answers "what did we spend" resolves its period through
here. The sliding 1M/3M/6M/12M windows this replaces each divided by their own
coverage months while admitting their own account set, so one question had five
answers depending on which chip was lit -- 3M said the household was bleeding
$3.5k a month and 12M said it was saving 4%, from the same ledger (P0-1).

A calendar month cannot do that. It starts on the 1st, ends on the last day, and
is the same month on every screen. The only period that is not a whole month is
the one the household is currently living in, and it is labelled as such and
paced against the same day of earlier months rather than against their totals.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

from app.services._household_month_coverage import (
    month_bounds,
    month_key,
    previous_month,
)

_MONTH_KEY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def is_month_key(value: str | None) -> bool:
    return bool(value) and bool(_MONTH_KEY_RE.match(str(value).strip()))


def month_label(month: str) -> str:
    """Render ``2026-07`` as ``July 2026``."""
    year, index = int(month[:4]), int(month[5:7])
    return f"{_MONTH_NAMES[index - 1]} {year}"


def next_month(month: str) -> str:
    year, index = int(month[:4]), int(month[5:7])
    if index == 12:
        return f"{year + 1}-01"
    return f"{year}-{index + 1:02d}"


def months_between(earliest: str, latest: str) -> list[str]:
    """Every calendar month from ``earliest`` to ``latest``, gaps included.

    A month with no rows is still a month the household lived through, and a
    selector that skipped it would quietly redefine "last month".
    """
    if earliest > latest:
        return []
    months = [earliest]
    while months[-1] < latest:
        months.append(next_month(months[-1]))
    return months


@dataclass(frozen=True)
class SpendPeriod:
    """A single reporting month, closed or still running."""

    key: str
    label: str
    start_date: date
    end_date: date
    month_end: date
    is_month_to_date: bool
    days_elapsed: int
    days_in_month: int

    @property
    def basis(self) -> str:
        """How a comparator must be sliced to compare like with like."""
        if self.is_month_to_date:
            return f"through_day_{self.days_elapsed}"
        return "full_month"

    @property
    def basis_label(self) -> str:
        if self.is_month_to_date:
            return f"through day {self.days_elapsed} of {self.days_in_month}"
        return "full month"


def build_spend_period(month: str, *, today: date) -> SpendPeriod:
    start_date, month_end = month_bounds(month)
    is_month_to_date = month == month_key(today)
    end_date = min(today, month_end) if is_month_to_date else month_end
    return SpendPeriod(
        key=month,
        label=month_label(month),
        start_date=start_date,
        end_date=end_date,
        month_end=month_end,
        is_month_to_date=is_month_to_date,
        days_elapsed=end_date.day,
        days_in_month=calendar.monthrange(start_date.year, start_date.month)[1],
    )


def resolve_spend_period(
    month: str | None,
    *,
    available_months: list[str],
    today: date,
) -> SpendPeriod:
    """Pick the month to report on.

    An unparseable or unknown month falls back to the newest month the ledger
    actually covers rather than erroring -- a stale bookmark should show the
    household this month, not a stack trace.
    """
    current_month = month_key(today)
    requested = (month or "").strip()
    if is_month_key(requested):
        return build_spend_period(requested, today=today)
    newest = max(available_months) if available_months else current_month
    return build_spend_period(max(newest, current_month), today=today)


def comparator_months(
    period: SpendPeriod,
    *,
    covered_months: list[str],
) -> tuple[str | None, list[str]]:
    """The two fixed comparators: prior month, and the all-month average set.

    Both exclude the reported month itself, and the average set excludes any
    month still running -- averaging a full month against a partial one is the
    arithmetic that produced the contradictory window figures in the first place.
    """
    prior = previous_month(period.key)
    prior_month = prior if prior in covered_months else None
    average_months = sorted(
        month
        for month in covered_months
        if month != period.key and month < period.key
    )
    return prior_month, average_months
