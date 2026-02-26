"""Market movers data source with failover.

Primary: yahooquery (Yahoo Finance Screener)
Fallback: Alpaca Markets Data API

Both sources provide day gainers/losers, but yahooquery has better
quality filtering (excludes penny stocks, warrants).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.sources._market_movers_helpers import (
    MarketMover,
    MarketMoversResult,
    fetch_from_alpaca,
    fetch_from_yahooquery,
)

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)

__all__ = [
    "MarketMover",
    "MarketMoversResult",
    "fetch_from_alpaca",
    "fetch_from_yahooquery",
    "fetch_market_movers",
]


def fetch_market_movers(storage: PortfolioStorage, count: int = 10) -> MarketMoversResult:
    """Fetch market movers with automatic failover.

    Tries yahooquery first (better quality), falls back to Alpaca.

    Args:
        storage: Storage instance for Alpaca credentials
        count: Number of gainers/losers to fetch

    Returns:
        MarketMoversResult (may have empty lists if all sources fail)
    """
    result = fetch_from_yahooquery(count)
    if result and (result.gainers or result.losers):
        return result

    logger.info("market_movers_fallback_to_alpaca")
    result = fetch_from_alpaca(storage, count)
    if result and (result.gainers or result.losers):
        return result

    logger.warning("market_movers_all_sources_failed")
    return MarketMoversResult(
        gainers=[],
        losers=[],
        most_active=[],
        top_rvol=[],
        source="none",
        last_updated=None,
    )
