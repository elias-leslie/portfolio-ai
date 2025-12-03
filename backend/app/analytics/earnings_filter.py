"""Earnings proximity filter for paper trading (GAP-003).

Prevents entering trades too close to earnings announcements when
volatility is elevated and direction is unpredictable.

Rule: No new entries within 2 trading days of earnings.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Minimum days before earnings to allow new entries
MIN_DAYS_BEFORE_EARNINGS = 2


def get_next_earnings_date(  # noqa: PLR0911
    storage: PortfolioStorage,
    ticker: str,
) -> datetime | None:
    """Get next earnings date for a ticker from cache.

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol

    Returns:
        Next earnings datetime, or None if unknown
    """
    # Check reference_cache for cached earnings date
    query = """
        SELECT payload
        FROM reference_cache
        WHERE symbol = $1
          AND source = 'earnings'
          AND as_of_date >= CURRENT_DATE - INTERVAL '30 days'
        ORDER BY as_of_date DESC
        LIMIT 1
    """

    result = storage.query(query, [ticker])

    if result.is_empty():
        return None

    row = result.to_dicts()[0]
    payload = row["payload"]

    if payload is None:
        return None

    # Payload is stored as JSON string or dict
    if isinstance(payload, str):
        import json  # noqa: PLC0415

        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    earnings_date_str = payload.get("earnings_date")
    if not earnings_date_str:
        return None

    try:
        return datetime.fromisoformat(earnings_date_str)
    except (ValueError, TypeError):
        return None


def check_earnings_proximity(
    storage: PortfolioStorage,
    ticker: str,
    min_days: int = MIN_DAYS_BEFORE_EARNINGS,
) -> tuple[bool, str, dict[str, str | int | None]]:
    """Check if a ticker is too close to earnings for a new entry.

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol
        min_days: Minimum days before earnings to allow trade

    Returns:
        Tuple of (is_ok, message, details):
        - is_ok: True if safe to trade (not near earnings)
        - message: Human-readable status
        - details: Dict with earnings_date, days_away
    """
    earnings_date = get_next_earnings_date(storage, ticker)

    if earnings_date is None:
        # No earnings date known - allow trade but log warning
        logger.warning(
            "earnings_date_unknown",
            ticker=ticker,
            action="allowing_trade",
        )
        return (
            True,
            "Earnings date unknown - trade allowed",
            {
                "ticker": ticker,
                "earnings_date": None,
                "days_away": None,
            },
        )

    # Calculate days until earnings
    now = datetime.now(UTC)
    # Normalize to date comparison
    earnings_date_normalized = earnings_date.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC
    )
    now_normalized = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_away = (earnings_date_normalized - now_normalized).days

    details: dict[str, str | int | None] = {
        "ticker": ticker,
        "earnings_date": earnings_date.isoformat(),
        "days_away": days_away,
        "min_days_required": min_days,
    }

    # Past earnings - allow trade
    if days_away < 0:
        logger.debug(
            "earnings_passed",
            ticker=ticker,
            days_ago=abs(days_away),
        )
        return True, f"Earnings passed {abs(days_away)} days ago", details

    # Too close to earnings
    if days_away < min_days:
        message = f"BLOCKED: Earnings in {days_away} days (min {min_days} required)"
        logger.warning(
            "earnings_proximity_blocked",
            ticker=ticker,
            days_away=days_away,
            min_days=min_days,
        )
        return False, message, details

    # Safe to trade
    message = f"OK: Earnings in {days_away} days (min {min_days} required)"
    logger.debug(
        "earnings_proximity_passed",
        ticker=ticker,
        days_away=days_away,
    )
    return True, message, details


def should_block_for_earnings(
    storage: PortfolioStorage,
    ticker: str,
) -> bool:
    """Quick check if trade should be blocked due to earnings proximity.

    Args:
        storage: Database storage instance
        ticker: Stock ticker symbol

    Returns:
        True if trade should be blocked (too close to earnings)
    """
    is_ok, _, _ = check_earnings_proximity(storage, ticker)
    return not is_ok
