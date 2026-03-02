"""Cache read/write helpers for price data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .models import PriceData

logger = get_logger(__name__)


def get_cached_prices(
    symbols: list[str],
    storage: PortfolioStorage,
    cache_ttl_minutes: int,
) -> dict[str, PriceData]:
    """Get cached prices that are still within the TTL window.

    Args:
        symbols: List of symbols to look up
        storage: PortfolioStorage instance
        cache_ttl_minutes: Cache TTL in minutes

    Returns:
        Dictionary of valid cached PriceData entries
    """
    if not symbols:
        return {}

    cutoff_time = datetime.now(UTC) - timedelta(minutes=cache_ttl_minutes)
    placeholders = ",".join(["?" for _ in symbols])

    df = storage.query(
        f"""
        SELECT symbol, price, beta, volatility, sector, bid, ask, bid_size, ask_size,
               cached_at, source, error
        FROM price_cache
        WHERE symbol IN ({placeholders})
          AND cached_at >= ?
        ORDER BY symbol, cached_at DESC
        """,
        [*symbols, cutoff_time],
    )

    if df.is_empty():
        return {}

    # Get most recent entry per symbol
    df = df.group_by("symbol").agg(pl.all().first())

    result = {}
    for row in df.iter_rows(named=True):
        result[row["symbol"]] = PriceData(**row)

    logger.info(
        "cache_hit",
        num_cached=len(result),
        symbols=list(result.keys()),
        cache_hit=True,
    )
    return result


def cache_prices(
    price_data: dict[str, PriceData],
    storage: PortfolioStorage,
) -> None:
    """Persist price data to the price_cache table.

    Args:
        price_data: Dictionary of PriceData to cache
        storage: PortfolioStorage instance
    """
    if not price_data:
        return

    rows = [data.model_dump() for data in price_data.values()]
    df = pl.DataFrame(rows)
    storage.insert_dataframe("price_cache", df, mode="append")

    logger.info(
        "prices_cached",
        num_cached=len(rows),
        symbols=list(price_data.keys()),
    )
