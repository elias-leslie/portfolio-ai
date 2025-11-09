"""Redis cache for watchlist data to prevent duplicate queries across concurrent tasks.

This module provides caching for watchlist symbols to eliminate duplicate database
queries when multiple Celery tasks (watchlist refresh, news refresh) run concurrently.

PROBLEM (Issue #4):
- watchlist_tasks and news_tasks both query watchlist_items independently
- Concurrent execution causes duplicate queries within same time window
- Example: 10 symbols x 2 tasks = 2 queries instead of 1

SOLUTION:
- Redis cache with 60-second TTL (aligned with typical refresh intervals)
- First task to run fetches from DB and caches
- Subsequent tasks within 60s window use cached data
- Automatic expiration prevents stale data

IMPACT:
- Eliminates inter-task query duplication
- Minimal latency overhead (Redis local, <1ms)
- Graceful degradation if Redis unavailable
"""

from __future__ import annotations

import json
import os
from typing import cast

import redis

from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Redis client for caching (singleton)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: redis.Redis[bytes] | None = None


def _get_redis_client() -> redis.Redis[bytes]:
    """Get or create Redis client singleton."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=False,  # We handle JSON ourselves
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def get_watchlist_symbols_cached(
    storage: PortfolioStorage,
    account_id: str | None = None,
    ttl_seconds: int = 60,
) -> list[str]:
    """Get watchlist symbols with Redis caching.

    Uses Redis cache to prevent duplicate queries when multiple tasks
    (watchlist refresh, news refresh) run concurrently.

    Args:
        storage: Database storage instance
        account_id: Optional account ID filter (None = all items, user-level)
        ttl_seconds: Cache TTL in seconds (default: 60s)

    Returns:
        List of ticker symbols from watchlist

    Cache Strategy:
        - Key format: "watchlist:symbols:{account_id}"
        - TTL: 60 seconds (aligns with typical refresh intervals)
        - Fallback: Query DB directly if Redis unavailable
    """
    # Build cache key
    cache_key = f"watchlist:symbols:{account_id or 'all'}"

    try:
        redis_client = _get_redis_client()

        # Try cache first
        cached_data = redis_client.get(cache_key)
        if cached_data:
            symbols = cast(list[str], json.loads(cached_data.decode("utf-8")))
            logger.debug(
                "watchlist_symbols_cache_hit",
                cache_key=cache_key,
                symbol_count=len(symbols),
            )
            return symbols

    except (redis.RedisError, ConnectionError, json.JSONDecodeError) as e:
        logger.warning(
            "watchlist_symbols_cache_error",
            error=str(e),
            cache_key=cache_key,
            fallback="query_database",
        )
        # Continue to database query on cache failure

    # Cache miss or error - query database
    symbols = _fetch_symbols_from_db(storage, account_id)

    # Store in cache for next request
    try:
        redis_client = _get_redis_client()
        redis_client.setex(
            cache_key,
            ttl_seconds,
            json.dumps(symbols).encode("utf-8"),
        )
        logger.debug(
            "watchlist_symbols_cache_set",
            cache_key=cache_key,
            symbol_count=len(symbols),
            ttl_seconds=ttl_seconds,
        )
    except (redis.RedisError, ConnectionError) as e:
        logger.warning(
            "watchlist_symbols_cache_set_error",
            error=str(e),
            cache_key=cache_key,
        )
        # Continue without caching - data is still valid

    return symbols


def _fetch_symbols_from_db(
    storage: PortfolioStorage,
    account_id: str | None = None,
) -> list[str]:
    """Fetch watchlist symbols directly from database.

    Args:
        storage: Database storage instance
        account_id: Optional account ID filter (None = all items, user-level)

    Returns:
        List of ticker symbols
    """
    # Note: Watchlist is user-level (no account_id FK anymore)
    # account_id parameter kept for backward compatibility
    df = storage.query(
        """
        SELECT DISTINCT symbol
        FROM watchlist_items
        ORDER BY symbol
        """
    )

    if df.is_empty():
        return []

    symbols = df["symbol"].to_list()
    logger.debug(
        "watchlist_symbols_fetched_from_db",
        symbol_count=len(symbols),
    )
    return symbols


def invalidate_watchlist_cache(account_id: str | None = None) -> None:
    """Invalidate watchlist symbols cache.

    Call this when watchlist items are added/removed to force cache refresh.

    Args:
        account_id: Optional account ID (None = invalidate all)
    """
    cache_key = f"watchlist:symbols:{account_id or 'all'}"

    try:
        redis_client = _get_redis_client()
        deleted = redis_client.delete(cache_key)
        logger.debug(
            "watchlist_symbols_cache_invalidated",
            cache_key=cache_key,
            deleted=deleted,
        )
    except (redis.RedisError, ConnectionError) as e:
        logger.warning(
            "watchlist_symbols_cache_invalidate_error",
            error=str(e),
            cache_key=cache_key,
        )
