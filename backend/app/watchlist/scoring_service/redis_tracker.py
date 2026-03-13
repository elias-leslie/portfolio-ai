"""Redis-based progress tracking for watchlist refresh operations.

This module handles:
- Redis client singleton
- Refresh status initialization
- Progress updates during processing
- Completion status tracking
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import redis

from ...config import REDIS_URL
from ...logging_config import get_logger

logger = get_logger(__name__)
_redis_client: redis.Redis[str] | None = None


def get_redis_client() -> redis.Redis[str]:  # redis.Redis with decode_responses=True
    """Get or create Redis client for progress tracking."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def init_refresh_status(account_id: str | None, symbols: list[str], total_items: int) -> str:
    """Initialize refresh status in Redis and return the key.

    Args:
        account_id: Optional account ID for filtering
        symbols: List of symbols being refreshed
        total_items: Total number of items to process

    Returns:
        Redis key for this refresh operation
    """
    redis_key = f"watchlist:refresh:{account_id or 'all'}"
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            redis_key,
            900,  # 15 minute TTL
            json.dumps(
                {
                    "status": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                    "total_items": total_items,
                    "processed_items": 0,
                    "current_symbol": None,
                    "symbols": symbols,
                }
            ),
        )
    except Exception as e:
        logger.warning("redis_refresh_init_failed", error=str(e))
    return redis_key


def update_progress(redis_key: str, symbol: str, processed: int) -> None:
    """Update Redis with current refresh progress.

    Args:
        redis_key: Redis key for this refresh operation
        symbol: Currently processing symbol
        processed: Number of items processed so far
    """
    try:
        redis_client = get_redis_client()
        redis_value = redis_client.get(redis_key)
        status_data = json.loads(str(redis_value) if redis_value else "{}")
        status_data.update(
            {
                "current_symbol": symbol,
                "processed_items": processed,
            }
        )
        redis_client.setex(redis_key, 900, json.dumps(status_data))
    except Exception as e:
        logger.debug("redis_refresh_update_failed", error=str(e))


def complete_refresh(redis_key: str, total_items: int, processed: int) -> None:
    """Mark refresh as completed in Redis.

    Args:
        redis_key: Redis key for this refresh operation
        total_items: Total number of items
        processed: Number of items successfully processed
    """
    try:
        redis_client = get_redis_client()
        redis_value = redis_client.get(redis_key)
        existing_data = json.loads(str(redis_value) if redis_value else "{}")
        completed_data = {
            "status": "completed",
            "started_at": existing_data.get("started_at"),
            "total_items": total_items,
            "processed_items": processed,
            "current_symbol": None,
            "is_refreshing": False,
        }
        redis_client.setex(redis_key, 5, json.dumps(completed_data))
    except Exception as e:
        logger.warning("redis_refresh_completion_update_failed", error=str(e))
