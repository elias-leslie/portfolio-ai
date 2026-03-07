"""Earnings surprise data fetching and scoring (GAP-003).

Fetches earnings surprise data (EPS estimate vs actual) from Finnhub
and provides scoring for signal classification.

Earnings surprises are predictive:
- Stocks that beat EPS estimates consistently tend to outperform
- Stocks that miss estimates consistently tend to underperform
- Large positive surprises often lead to price momentum
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger

from . import _earnings_surprise_fetch
from ._earnings_surprise_storage import get_recent_earnings_surprises, save_earnings_surprises
from .earnings_surprise_types import (
    LARGE_BEAT_PCT,
    LARGE_MISS_PCT,
    SMALL_BEAT_PCT,
    SMALL_MISS_PCT,
    EarningsSurprise,
)

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Preserve the historic patch seam used by tests/callers.
requests = _earnings_surprise_fetch.requests

__all__ = [
    "LARGE_BEAT_PCT",
    "LARGE_MISS_PCT",
    "SMALL_BEAT_PCT",
    "SMALL_MISS_PCT",
    "EarningsSurprise",
    "calculate_earnings_surprise_score",
    "fetch_and_store_earnings_surprises",
    "fetch_earnings_surprises_from_finnhub",
    "get_recent_earnings_surprises",
    "save_earnings_surprises",
]


def _recent_beat_reason(most_recent_pct: float | None) -> str:
    """Format reason string for a recent earnings beat."""
    if most_recent_pct and float(most_recent_pct) > LARGE_BEAT_PCT:
        return f"Recent earnings +{float(most_recent_pct):.1f}% surprise"
    return "Recent earnings beat"


def _score_beats_misses(
    beats: int,
    misses: int,
    total: int,
    most_recent_direction: str | None,
    most_recent_pct: float | None,
) -> tuple[int, list[str]]:
    """Return (score_delta, reasons) based on beat/miss counts and recency."""
    if beats >= 3 and misses == 0:
        return 4, [f"Earnings: {beats}/{total} quarters beat estimates"]
    if beats >= 2 and misses <= 1:
        return 3, [f"Earnings: {beats}/{total} quarters beat"]
    if most_recent_direction == "beat":
        return 2, [_recent_beat_reason(most_recent_pct)]
    if most_recent_direction == "inline":
        return 1, ["Earnings met expectations"]
    if misses >= 3:
        return -1, [f"Earnings: {misses}/{total} quarters missed estimates"]
    return 0, []


def calculate_earnings_surprise_score(
    storage: PortfolioStorage,
    symbol: str,
    quarters: int = 4,
) -> tuple[int, list[str]]:
    """Calculate 0-4 point earnings surprise score for signal classification.

    Scoring based on recent earnings history:
    - Consistent beats (3-4 quarters): +3-4 points
    - Recent beat: +2 points
    - Inline results: +1 point
    - Recent miss: 0 points
    - Consistent misses: -1 point (AVOID signal contribution)

    Args:
        storage: Database storage instance
        symbol: Stock symbol
        quarters: Number of quarters to analyze

    Returns:
        (score, reasons) tuple
    """
    surprises = get_recent_earnings_surprises(storage, symbol, quarters)
    if not surprises:
        return 0, []

    beats = sum(1 for s in surprises if s.get("surprise_direction") == "beat")
    misses = sum(1 for s in surprises if s.get("surprise_direction") == "miss")
    most_recent = surprises[0]

    return _score_beats_misses(
        beats,
        misses,
        len(surprises),
        most_recent.get("surprise_direction"),
        most_recent.get("surprise_pct"),
    )


def fetch_and_store_earnings_surprises(
    storage: PortfolioStorage,
    symbol: str,
) -> int:
    """Convenience function to fetch and store earnings surprises.

    Args:
        storage: Database storage instance
        symbol: Stock symbol

    Returns:
        Number of records saved
    """
    surprises = fetch_earnings_surprises_from_finnhub(symbol)
    if surprises:
        return save_earnings_surprises(storage, surprises)
    return 0


def fetch_earnings_surprises_from_finnhub(symbol: str, limit: int = 4) -> list[EarningsSurprise]:
    """Compatibility wrapper around the extracted Finnhub fetch helper."""
    return _earnings_surprise_fetch.fetch_earnings_surprises_from_finnhub(symbol, limit=limit)
