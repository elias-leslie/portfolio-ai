"""Whether a merchant is a commitment, or just a merchant seen more than once.

The old test was "seen twice, and the biggest average wins", which is how a
three-week Airbnb stay became the household's largest recurring bill while Duke
Energy sat below the cut. A commitment has to prove three things instead: it
keeps a cadence, it charges roughly the same amount each time, and it has been
doing both for long enough that one trip cannot fake it.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import pairwise

# Three sightings is the floor for inferring a rhythm. Two sightings only ever
# describe a single gap, and a single gap is a coincidence: it cannot tell a
# monthly bill from two unrelated purchases five weeks apart. A cadence the
# household has declared still admits on one sighting -- that path never reaches
# this module.
MIN_SIGHTINGS = 3

# A commitment has to have been running for about two monthly cycles across
# three different calendar months. Both bars exist for the same reason and neither
# is redundant: the span rejects the Airbnb stay that billed weekly for a
# fortnight, and the month count rejects a burst of purchases that happens to
# straddle a month boundary.
MIN_SPAN_DAYS = 55
MIN_DISTINCT_MONTHS = 3

# How far a single gap or a single charge may stray from the merchant's own
# median before it stops counting as part of the pattern, and how much of the
# series has to stay inside that band. Both are share-based rather than
# all-or-nothing so that one off-cycle charge -- a gym day pass, a late payment
# -- does not erase a year of evidence.
INTERVAL_TOLERANCE = 0.35
AMOUNT_TOLERANCE = 0.35
MIN_REGULAR_SHARE = 0.7
MIN_STABLE_SHARE = 0.7

# Gap in days -> cadence. Below the first floor is a shopping habit, not a
# commitment; above the last ceiling the evidence is too thin to be a cadence at
# all. Bimonthly and semiannual are here because real utilities bill on them:
# P C Utilities runs on a 61-day cycle, and rounding that to "quarterly" would
# under-fund its sinking fund by a third.
_CADENCE_BUCKETS: tuple[tuple[int, int, str], ...] = (
    (5, 10, "weekly"),
    (11, 20, "biweekly"),
    (21, 45, "monthly"),
    (46, 75, "bimonthly"),
    (76, 135, "quarterly"),
    (136, 250, "semiannual"),
    (251, 430, "annual"),
)

CADENCE_LABELS: dict[str, str] = {
    "weekly": "likely weekly",
    "biweekly": "likely bi-weekly",
    "monthly": "likely monthly",
    "bimonthly": "likely every 2 months",
    "quarterly": "likely quarterly",
    "semiannual": "likely twice a year",
    "annual": "likely annual",
}

# Nominal length of each cadence, for judging whether a pattern is still alive.
CADENCE_DAYS: dict[str, int] = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "bimonthly": 61,
    "quarterly": 91,
    "semiannual": 182,
    "annual": 365,
}

# Two missed cycles is where a commitment stops being one. A monthly bill last
# seen ten weeks ago is not "overdue by forty days", it is a series that ended --
# a cancelled subscription, or a merchant that got renamed underneath the feed --
# and presenting it as a live obligation invents money the household still owes.
LAPSED_AFTER_CYCLES = 2

CADENCE_FOR_LABEL: dict[str, str] = {label: cadence for cadence, label in CADENCE_LABELS.items()}

# Which recurring things are obligations and which are just habits. A merchant
# the household cannot stop paying without consequence is a bill; a merchant it
# happens to visit on a rhythm is a purchase, and calling that a bill is what put
# a rental car in the same list as the electricity.
_BILL_CATEGORIES = {
    "bills",
    "home",
    "housing",
    "utilities",
    "insurance",
    "healthcare",
    "health",
    "medical",
    "childcare",
    "taxes",
    "debt",
    "loans",
}
_SUBSCRIPTION_CATEGORIES = {
    "subscriptions",
    "fitness",
    "entertainment",
    "education",
    "memberships",
}

BILL = "bill"
SUBSCRIPTION = "subscription"
RECURRING_PURCHASE = "recurring_purchase"

_MIN_CONFIDENCE = 0.5
_MAX_CONFIDENCE = 0.95


@dataclass(frozen=True)
class RecurrencePattern:
    """A merchant that passed the periodicity and amount-stability tests."""

    cadence: str
    label: str
    confidence: float
    typical_amount: float
    last_seen: date
    sightings: int
    median_interval_days: int
    span_days: int
    distinct_months: int
    evidence: str


def commitment_type_for(category: str | None) -> str:
    """Classify a recurring merchant as a bill, a subscription or a purchase."""
    key = (category or "").strip().lower()
    if key in _SUBSCRIPTION_CATEGORIES:
        return SUBSCRIPTION
    if key in _BILL_CATEGORIES:
        return BILL
    # "General Services Insurance" and friends arrive from Plaid as compound
    # labels, so fall back to a word match before giving up on them.
    words = set(key.replace("/", " ").replace("-", " ").split())
    if words & _SUBSCRIPTION_CATEGORIES:
        return SUBSCRIPTION
    if words & _BILL_CATEGORIES:
        return BILL
    return RECURRING_PURCHASE


def detect_recurrence(events: Iterable[tuple[date, float]]) -> RecurrencePattern | None:
    """Return the cadence a merchant keeps, or None when it keeps none."""
    charges = _one_charge_per_day(events)
    days = sorted(charges)
    if len(days) < MIN_SIGHTINGS:
        return None

    amounts = [charges[day] for day in days]
    intervals = [(later - earlier).days for earlier, later in pairwise(days)]
    median_interval = round(statistics.median(intervals))
    cadence = _cadence_for_interval(median_interval)
    span_days = (days[-1] - days[0]).days
    distinct_months = len({(day.year, day.month) for day in days})
    if cadence is None or span_days < MIN_SPAN_DAYS or distinct_months < MIN_DISTINCT_MONTHS:
        return None

    regular_share = _share_within(intervals, median_interval, INTERVAL_TOLERANCE)
    typical_amount = float(statistics.median(amounts))
    stable_share = _share_within(amounts, typical_amount, AMOUNT_TOLERANCE)
    if regular_share < MIN_REGULAR_SHARE or stable_share < MIN_STABLE_SHARE:
        return None

    return RecurrencePattern(
        cadence=cadence,
        label=CADENCE_LABELS[cadence],
        confidence=_confidence(len(days), regular_share, stable_share),
        typical_amount=round(typical_amount, 2),
        last_seen=days[-1],
        sightings=len(days),
        median_interval_days=median_interval,
        span_days=span_days,
        distinct_months=distinct_months,
        evidence=(
            f"{len(days)} charges across {distinct_months} months, "
            f"about {median_interval} days apart, "
            f"typically {typical_amount:,.2f}."
        ),
    )


def _one_charge_per_day(events: Iterable[tuple[date, float]]) -> dict[date, float]:
    """Collapse a day's rows to its largest charge.

    Two rows on the same day for the same merchant are far more often one bill
    imported twice than two bills genuinely paid: summing them would double the
    obligation, so the larger of the pair stands for the day.
    """
    charges: dict[date, float] = {}
    for day, amount in events:
        value = abs(float(amount))
        if value <= 0:
            continue
        if value > charges.get(day, 0.0):
            charges[day] = value
    return charges


def _cadence_for_interval(median_interval: int) -> str | None:
    for low, high, cadence in _CADENCE_BUCKETS:
        if low <= median_interval <= high:
            return cadence
    return None


def _share_within(values: list[float] | list[int], center: float, tolerance: float) -> float:
    if center <= 0 or not values:
        return 0.0
    low = center * (1 - tolerance)
    high = center * (1 + tolerance)
    inside = sum(1 for value in values if low <= value <= high)
    return inside / len(values)


def _confidence(sightings: int, regular_share: float, stable_share: float) -> float:
    evidence = min(sightings, 8) / 8
    fit = (regular_share + stable_share) / 2
    raw = 0.45 + 0.30 * evidence + 0.25 * ((fit - MIN_REGULAR_SHARE) / (1 - MIN_REGULAR_SHARE))
    return round(min(max(raw, _MIN_CONFIDENCE), _MAX_CONFIDENCE), 2)


__all__ = [
    "AMOUNT_TOLERANCE",
    "BILL",
    "CADENCE_DAYS",
    "CADENCE_FOR_LABEL",
    "CADENCE_LABELS",
    "INTERVAL_TOLERANCE",
    "LAPSED_AFTER_CYCLES",
    "MIN_DISTINCT_MONTHS",
    "MIN_REGULAR_SHARE",
    "MIN_SIGHTINGS",
    "MIN_SPAN_DAYS",
    "MIN_STABLE_SHARE",
    "RECURRING_PURCHASE",
    "SUBSCRIPTION",
    "RecurrencePattern",
    "commitment_type_for",
    "detect_recurrence",
]
