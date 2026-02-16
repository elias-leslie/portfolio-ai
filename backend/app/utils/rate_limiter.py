"""Rate limiting utilities using Redis.

Provides daily and sliding window rate limiting for scheduled tasks and API endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import redis

from ..config import REDIS_URL


class RateLimitResult(NamedTuple):
    """Result of a rate limit check."""

    allowed: bool
    current_count: int
    remaining: int
    limit: int


def get_redis_client() -> redis.Redis[Any]:
    """Get a Redis client instance.

    Returns:
        Redis client configured from REDIS_URL setting
    """
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def check_daily_limit(key_prefix: str, max_count: int) -> RateLimitResult:
    """Check if daily rate limit has been reached.

    Uses a Redis key that resets at midnight UTC.

    Args:
        key_prefix: Prefix for the rate limit key (date will be appended)
        max_count: Maximum allowed requests per day

    Returns:
        RateLimitResult with allowed status and counts
    """
    rate_key = f"{key_prefix}:{date.today().isoformat()}"
    r = get_redis_client()

    current_count = int(r.get(rate_key) or 0)
    remaining = max(0, max_count - current_count)
    allowed = current_count < max_count

    return RateLimitResult(
        allowed=allowed,
        current_count=current_count,
        remaining=remaining,
        limit=max_count,
    )


def increment_daily_count(key_prefix: str, expire_seconds: int = 86400 * 2) -> int:
    """Increment the daily rate limit counter.

    Args:
        key_prefix: Prefix for the rate limit key
        expire_seconds: TTL for the key (default 2 days for safety)

    Returns:
        New count after increment
    """
    rate_key = f"{key_prefix}:{date.today().isoformat()}"
    r = get_redis_client()

    pipe = r.pipeline()
    pipe.incr(rate_key)
    pipe.expire(rate_key, expire_seconds)
    results = pipe.execute()

    return int(results[0])  # Return the new count


def check_and_increment_daily_limit(key_prefix: str, max_count: int) -> RateLimitResult:
    """Check daily rate limit and increment if allowed.

    Atomically checks if limit is reached and increments the counter.
    Use this when you want to claim a slot in the limit.

    Args:
        key_prefix: Prefix for the rate limit key
        max_count: Maximum allowed requests per day

    Returns:
        RateLimitResult with allowed status and counts
    """
    result = check_daily_limit(key_prefix, max_count)

    if result.allowed:
        # Increment the counter
        new_count = increment_daily_count(key_prefix)
        return RateLimitResult(
            allowed=True,
            current_count=new_count,
            remaining=max(0, max_count - new_count),
            limit=max_count,
        )

    return result
