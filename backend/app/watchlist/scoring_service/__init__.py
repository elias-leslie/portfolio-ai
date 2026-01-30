"""Watchlist scoring sub-module.

This package contains the refactored scoring service split into focused modules:
- helpers: Shared scoring helper functions
- components: Individual score component calculators
- redis_tracker: Redis-based progress tracking
- batch_loader: Batch data loading operations
- context: Scoring context initialization
- processor: Single symbol processing
- aggregator: Multi-symbol processing and result aggregation

Main entry point:
- refresh_watchlist_scores: Public API for scoring watchlist items
"""

from __future__ import annotations


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies during module initialization."""
    # Helper functions - can be imported immediately
    if name == "_is_stale":
        from .helpers import is_stale as _is_stale

        return _is_stale

    # Service functions - lazy load to avoid circular imports
    if name == "aggregate_results":
        from .aggregator import aggregate_results

        return aggregate_results
    if name == "process_all_symbols":
        from .aggregator import process_all_symbols

        return process_all_symbols
    if name == "fetch_news_batch":
        from .batch_loader import fetch_news_batch

        return fetch_news_batch
    if name == "fetch_prices_in_batches":
        from .batch_loader import fetch_prices_in_batches

        return fetch_prices_in_batches
    if name == "load_latest_technical":
        from .batch_loader import load_latest_technical

        return load_latest_technical
    if name == "load_watchlist_items":
        from .batch_loader import load_watchlist_items

        return load_watchlist_items
    if name == "trigger_auto_backfill":
        from .batch_loader import trigger_auto_backfill

        return trigger_auto_backfill
    if name == "initialize_scoring_context":
        from .context import initialize_scoring_context

        return initialize_scoring_context
    if name == "process_single_symbol":
        from .processor import process_single_symbol

        return process_single_symbol
    if name == "complete_refresh":
        from .redis_tracker import complete_refresh

        return complete_refresh
    if name == "get_redis_client":
        from .redis_tracker import get_redis_client

        return get_redis_client
    if name == "init_refresh_status":
        from .redis_tracker import init_refresh_status

        return init_refresh_status
    if name == "update_progress":
        from .redis_tracker import update_progress

        return update_progress
    if name == "refresh_watchlist_scores":
        from .scoring_service import refresh_watchlist_scores

        return refresh_watchlist_scores

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "_is_stale",
    "aggregate_results",
    "complete_refresh",
    "fetch_news_batch",
    "fetch_prices_in_batches",
    "get_redis_client",
    "init_refresh_status",
    "initialize_scoring_context",
    "load_latest_technical",
    "load_watchlist_items",
    "process_all_symbols",
    "process_single_symbol",
    "refresh_watchlist_scores",
    "trigger_auto_backfill",
    "update_progress",
]
