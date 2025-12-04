"""Redis-based task deduplication locks.

Prevents duplicate Celery tasks from running concurrently by using Redis locks.
This is especially useful for tasks that are scheduled frequently (Beat) or
triggered from multiple sources (cascades).

PROBLEM:
- Tasks like ingest_historical_ohlcv can be triggered from multiple sources
- Without deduplication, identical tasks pile up in queue
- Even with backpressure, duplicate work wastes resources

SOLUTION:
- Redis SET NX (set-if-not-exists) with TTL for distributed locking
- Tasks acquire lock before running, skip if lock exists
- Lock auto-expires after TTL to prevent deadlocks
- Graceful degradation if Redis unavailable (tasks run normally)

USAGE:
    from app.utils.task_locks import task_lock, is_task_locked

    @celery_app.task
    def my_task(symbol: str):
        lock_key = f"my_task:{ticker}"
        with task_lock(lock_key, ttl=300) as acquired:
            if not acquired:
                return {"skipped": True, "reason": "duplicate_task"}
            # Do actual work...
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import redis

from ..logging_config import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# Redis client for task locks (singleton)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis_client: redis.Redis[bytes] | None = None

# Default lock TTL in seconds (5 minutes - enough for most tasks to complete)
DEFAULT_LOCK_TTL = 300

# Lock key prefix to namespace task locks
LOCK_PREFIX = "task_lock:"


def _get_redis_client() -> redis.Redis[bytes]:
    """Get or create Redis client singleton."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def acquire_task_lock(lock_key: str, ttl: int = DEFAULT_LOCK_TTL) -> bool:
    """Attempt to acquire a task lock.

    Uses Redis SET NX (set-if-not-exists) with TTL for atomic lock acquisition.

    Args:
        lock_key: Unique key identifying the task (e.g., "ingest:AAPL,MSFT")
        ttl: Lock expiration in seconds (default: 300 = 5 minutes)

    Returns:
        True if lock was acquired, False if already locked or Redis error
    """
    try:
        client = _get_redis_client()
        full_key = f"{LOCK_PREFIX}{lock_key}"

        # SET NX with TTL - atomic acquire
        result = client.set(full_key, "1", nx=True, ex=ttl)
        acquired = result is True

        if acquired:
            logger.debug("task_lock_acquired", lock_key=lock_key, ttl=ttl)
        else:
            logger.info("task_lock_exists", lock_key=lock_key, reason="duplicate_skipped")

        return acquired

    except redis.RedisError as e:
        # Graceful degradation - if Redis fails, allow task to run
        logger.warning("task_lock_redis_error", lock_key=lock_key, error=str(e))
        return True


def release_task_lock(lock_key: str) -> bool:
    """Release a task lock.

    Args:
        lock_key: Lock key to release

    Returns:
        True if lock was released, False if not found or Redis error
    """
    try:
        client = _get_redis_client()
        full_key = f"{LOCK_PREFIX}{lock_key}"

        result = client.delete(full_key)
        released = result > 0

        if released:
            logger.debug("task_lock_released", lock_key=lock_key)

        return released

    except redis.RedisError as e:
        logger.warning("task_lock_release_error", lock_key=lock_key, error=str(e))
        return False


def is_task_locked(lock_key: str) -> bool:
    """Check if a task lock exists (without acquiring).

    Args:
        lock_key: Lock key to check

    Returns:
        True if locked, False otherwise
    """
    try:
        client = _get_redis_client()
        full_key = f"{LOCK_PREFIX}{lock_key}"
        return client.exists(full_key) > 0

    except redis.RedisError as e:
        logger.warning("task_lock_check_error", lock_key=lock_key, error=str(e))
        return False


@contextmanager
def task_lock(lock_key: str, ttl: int = DEFAULT_LOCK_TTL) -> Generator[bool]:
    """Context manager for task locking with automatic release.

    Usage:
        with task_lock("my_task:AAPL") as acquired:
            if not acquired:
                return {"skipped": True}
            # Do work...

    Args:
        lock_key: Unique key for this task instance
        ttl: Lock expiration in seconds

    Yields:
        True if lock was acquired, False if task should skip
    """
    acquired = acquire_task_lock(lock_key, ttl)
    try:
        yield acquired
    finally:
        if acquired:
            release_task_lock(lock_key)


def generate_task_lock_key(task_name: str, *args: str | int | list[str]) -> str:
    """Generate a consistent lock key from task name and arguments.

    Args:
        task_name: Name of the task (e.g., "ingest_historical_ohlcv")
        *args: Task arguments to include in key

    Returns:
        Lock key string (e.g., "ingest_historical_ohlcv:AAPL,MSFT:252")
    """
    parts = [task_name]
    for arg in args:
        if isinstance(arg, list):
            # Sort lists for consistent keys regardless of order
            parts.append(",".join(sorted(str(x) for x in arg)))
        else:
            parts.append(str(arg))
    return ":".join(parts)
