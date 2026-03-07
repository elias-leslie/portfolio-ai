"""Price fetching helper for recommendations."""

from __future__ import annotations

from app.logging_config import get_logger
from app.portfolio.models import PriceData
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

logger = get_logger(__name__)


def fetch_current_prices(symbols: list[str]) -> dict[str, PriceData]:
    """Fetch real-time price snapshots for the given symbols.

    Args:
        symbols: List of ticker symbols to fetch prices for.

    Returns:
        Mapping of symbol to current price snapshots. Empty on failure.
    """
    if not symbols:
        return {}
    try:
        storage = get_storage()
        price_fetcher = PriceDataFetcher(storage)
        return price_fetcher.fetch_price_data(symbols)
    except Exception as e:
        logger.warning(f"Failed to fetch real-time prices: {e}")
        return {}
