"""Cache read/write helpers for price data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .models import PriceData
from .sector_labels import resolve_sector_label

logger = get_logger(__name__)


def get_cached_prices(
    symbols: list[str],
    storage: PortfolioStorage,
    cache_ttl_minutes: int | None,
) -> dict[str, PriceData]:
    """Get cached prices that are still within the TTL window.

    Args:
        symbols: List of symbols to look up
        storage: PortfolioStorage instance
        cache_ttl_minutes: Cache TTL in minutes. When None, return latest row
            per symbol without an age cutoff.

    Returns:
        Dictionary of valid cached PriceData entries
    """
    if not symbols:
        return {}

    placeholders = ",".join(["?" for _ in symbols])
    cutoff_clause = ""
    params: list[object] = list(symbols)
    if cache_ttl_minutes is not None:
        cutoff_time = datetime.now(UTC) - timedelta(minutes=cache_ttl_minutes)
        cutoff_clause = "AND cached_at >= ?"
        params.append(cutoff_time)

    df = storage.query(
        f"""
        SELECT symbol, price, beta, volatility, sector, bid, ask, bid_size, ask_size,
               cached_at, source, error
        FROM price_cache
        WHERE symbol IN ({placeholders})
          {cutoff_clause}
        ORDER BY symbol, cached_at DESC
        """,
        params,
    )

    if df.is_empty():
        return {}

    # Get most recent entry per symbol (sort ensures correct order before dedup)
    df = df.sort("cached_at", descending=True).unique(subset=["symbol"], keep="first")

    result = {}
    for row in df.iter_rows(named=True):
        row["sector"] = resolve_sector_label(str(row["symbol"]), row.get("sector"))
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

    # Delete existing rows for these symbols before inserting to prevent unbounded growth
    symbols = list(price_data.keys())
    placeholders = ",".join(["?" for _ in symbols])
    storage.execute(f"DELETE FROM price_cache WHERE symbol IN ({placeholders})", symbols)

    storage.insert_dataframe("price_cache", df, mode="append")

    logger.info(
        "prices_cached",
        num_cached=len(rows),
        symbols=list(price_data.keys()),
    )
