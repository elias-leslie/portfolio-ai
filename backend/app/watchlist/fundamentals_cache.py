"""Caching layer for fundamental data with 24-hour TTL.

This module provides cached access to fundamental data using the reference_cache
table to minimize external API calls and improve performance.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.storage.types import DatabaseConnection
from app.watchlist.fundamentals_models import FundamentalData
from app.watchlist.fundamentals_sources import fetch_fundamentals


def fetch_fundamentals_cached(
    conn: DatabaseConnection, symbol: str, ttl_days: int = 1
) -> FundamentalData | None:
    """Fetch fundamental data with caching support (default TTL: 24 hours).

    This function checks the reference_cache table first. If valid cached data
    exists (within TTL), it returns the cached data without calling external APIs.
    If cache is stale or missing, it fetches fresh data and caches it.

    Args:
        conn: Database connection
        symbol: Stock symbol
        ttl_days: Cache TTL in days (default: 1 day = 24 hours)

    Returns:
        FundamentalData if successful, None if failed

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     data = fetch_fundamentals_cached(conn, "NVDA")
        >>> # First call fetches from API and caches
        >>> # Second call within 24 hours uses cache
    """
    # Check cache first
    cache_cutoff = date.today() - timedelta(days=ttl_days)

    cached_row = conn.execute(
        """
        SELECT payload
        FROM reference_cache
        WHERE symbol = %s
          AND source = %s
          AND as_of_date >= %s
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [symbol, "fundamentals", cache_cutoff.isoformat()],
    ).fetchone()

    # Cache hit - return cached data
    if cached_row is not None:
        payload = cached_row[0]
        if isinstance(payload, dict):
            return FundamentalData(**payload)
        return None

    # Cache miss or stale - fetch fresh data
    fresh_data = fetch_fundamentals(symbol)

    if fresh_data is None:
        return None

    # Cache the fresh data
    conn.execute(
        """
        INSERT INTO reference_cache (symbol, as_of_date, payload, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (symbol, as_of_date, source)
        DO UPDATE SET payload = EXCLUDED.payload
        """,
        [
            symbol,
            date.today().isoformat(),
            json.dumps(fresh_data.model_dump()),
            "fundamentals",
        ],
    )
    conn.commit()

    return fresh_data
