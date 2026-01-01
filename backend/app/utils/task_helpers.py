"""Shared helper functions for Celery tasks.

This module provides common utilities used across multiple task modules,
reducing code duplication and standardizing patterns.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.storage import PortfolioStorage, get_storage
from app.utils.watchlist_cache import get_watchlist_symbols_cached

logger = get_logger(__name__)


def get_watchlist_symbols_or_early_return(
    task_id: str | None,
    log_event: str,
    secondary_metric_name: str = "symbols_updated",
) -> tuple[list[str], PortfolioStorage, dict[str, int | str | None] | None]:
    """Get watchlist symbols or return early response if none found.

    Common boilerplate pattern used by Celery tasks that process watchlist symbols.

    Args:
        task_id: Celery task ID for response
        log_event: Log event name for empty list (e.g., "no_watchlist_symbols_for_health_scores")
        secondary_metric_name: Name of secondary metric in response (default: "symbols_updated")

    Returns:
        Tuple of (symbols_list, storage, early_return_response_or_none)
        If symbols is empty, early_return_response contains the response dict.
        Otherwise, early_return_response is None.

    Example:
        symbols, storage, early_return = get_watchlist_symbols_or_early_return(
            self.request.id, "no_symbols_for_my_task"
        )
        if early_return:
            return early_return
    """
    storage = get_storage()
    symbols = get_watchlist_symbols_cached(storage, account_id=None, ttl_seconds=60)

    if not symbols:
        logger.info(log_event)
        return (
            [],
            storage,
            {
                "task_id": task_id,
                "symbols_processed": 0,
                secondary_metric_name: 0,
                "duration_seconds": 0,
            },
        )

    return symbols, storage, None
