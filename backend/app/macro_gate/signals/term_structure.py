"""Treasury term structure signal (10Y - 2Y).

Lower / inverted = late-cycle / recessionary risk; higher = expansionary.
The L1 gate normalises this to a 0-100 score where ``> 0`` (positive spread)
trends toward 100 and inversions toward 0. Series source is FRED via the
existing ``FREDSource`` (DGS10 + DGS2 are already mapped as ``YIELD_10Y``
and ``YIELD_2Y``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...logging_config import get_logger
from ...sources.fred import FREDSource

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TermStructureObservation:
    as_of: date
    yield_10y: float
    yield_2y: float
    spread_bps: float  # (10y - 2y) in basis points
    is_inverted: bool


def fetch_latest(source: FREDSource | None = None) -> TermStructureObservation | None:
    """Return the latest 10Y-2Y spread observation.

    Returns None when either series is missing for the latest aligned date.
    """
    source = source or FREDSource()
    if not source.is_enabled():
        logger.warning("term_structure_fred_disabled")
        return None

    y10 = source.get_latest_value("YIELD_10Y")
    y2 = source.get_latest_value("YIELD_2Y")
    if y10 is None or y2 is None:
        logger.warning("term_structure_missing_values", y10=y10, y2=y2)
        return None

    # Use the older of the two dates so the spread is genuinely aligned.
    as_of = min(y10[0], y2[0])
    spread_bps = (y10[1] - y2[1]) * 100.0  # FRED yields are in percent
    return TermStructureObservation(
        as_of=as_of,
        yield_10y=y10[1],
        yield_2y=y2[1],
        spread_bps=spread_bps,
        is_inverted=spread_bps < 0,
    )


def fetch_series(
    source: FREDSource | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> list[tuple[date, float]]:
    """Return aligned (date, spread_bps) series across the requested window."""
    source = source or FREDSource()
    if not source.is_enabled():
        return []
    y10 = dict(source.fetch_series("YIELD_10Y", start_date=start_date, end_date=end_date))
    y2 = dict(source.fetch_series("YIELD_2Y", start_date=start_date, end_date=end_date))
    common_dates = sorted(set(y10.keys()) & set(y2.keys()))
    return [(d, (y10[d] - y2[d]) * 100.0) for d in common_dates]


def normalize_to_score(spread_bps: float) -> float:
    """Project spread (basis points) onto a [0, 100] score.

    Mapping:
        -200 bps and below = 0   (deeply inverted)
        0 bps              = 50  (flat)
        +250 bps and above = 100 (steep curve)

    This is intentionally piece-wise linear and back-testable; weights are
    documented in macro_gate/scoring.py.
    """
    if spread_bps <= -200:
        return 0.0
    if spread_bps >= 250:
        return 100.0
    if spread_bps < 0:
        return 50.0 * (1 - abs(spread_bps) / 200.0)
    return 50.0 + 50.0 * (spread_bps / 250.0)
