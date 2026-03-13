"""Task lifecycle utilities for memory management.

Provides GC cleanup and RSS monitoring for long-running Hatchet worker tasks.
Prevents memory leaks by forcing cyclic GC collection after task completion
and logging RSS to aid in diagnosing growth patterns.
"""

from __future__ import annotations

import gc
import os
import resource
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar

from ..logging_config import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def log_task_memory(task_name: str) -> None:
    """Log current and peak RSS for the worker process.

    Args:
        task_name: Name of the task for structured log context.
    """
    pid = os.getpid()
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is in KB on Linux
    peak_rss_mb = usage.ru_maxrss / 1024.0

    # Current RSS from /proc (more accurate than rusage for current state)
    current_rss_mb = _get_current_rss_mb()

    logger.info(
        "task_memory",
        task_name=task_name,
        pid=pid,
        current_rss_mb=round(current_rss_mb, 1),
        peak_rss_mb=round(peak_rss_mb, 1),
    )


def _get_current_rss_mb() -> float:
    """Read current RSS from /proc/self/statm (Linux-specific)."""
    try:
        with Path("/proc/self/statm").open(encoding="utf-8") as f:
            # statm fields: size resident shared text lib data dt (all in pages)
            parts = f.read().split()
            resident_pages = int(parts[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (resident_pages * page_size) / (1024 * 1024)
    except (OSError, IndexError, ValueError):
        # Fallback: use rusage (less accurate for current, but works everywhere)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return usage.ru_maxrss / 1024.0


def task_cleanup(task_name: str) -> None:
    """Run post-task garbage collection and log memory.

    Should be called in a finally block after task completion to force
    Python's cyclic GC to collect circular references (torch tensors,
    httpx pools, etc.) that would otherwise linger.

    Args:
        task_name: Name of the task for structured log context.
    """
    collected = gc.collect()
    log_task_memory(task_name)
    if collected > 0:
        logger.debug(
            "task_gc_collected",
            task_name=task_name,
            objects_collected=collected,
        )


def with_cleanup(task_name: str) -> Callable[[F], F]:
    """Decorator that wraps a task function with post-execution cleanup.

    Calls task_cleanup() in a finally block regardless of success or failure.

    Args:
        task_name: Name for logging context.

    Returns:
        Decorated function.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            finally:
                task_cleanup(task_name)

        return wrapper  # type: ignore[return-value]

    return decorator
