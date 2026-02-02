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

# Lazy import mapping: attribute name -> (module, import name or None if same)
_LAZY_IMPORTS = {
    "_is_stale": ("helpers", "is_stale"),
    "aggregate_results": ("aggregator", None),
    "process_all_symbols": ("aggregator", None),
    "fetch_news_batch": ("batch_loader", None),
    "fetch_prices_in_batches": ("batch_loader", None),
    "load_latest_technical": ("batch_loader", None),
    "load_watchlist_items": ("batch_loader", None),
    "trigger_auto_backfill": ("batch_loader", None),
    "initialize_scoring_context": ("context", None),
    "process_single_symbol": ("processor", None),
    "complete_refresh": ("redis_tracker", None),
    "get_redis_client": ("redis_tracker", None),
    "init_refresh_status": ("redis_tracker", None),
    "update_progress": ("redis_tracker", None),
    "refresh_watchlist_scores": ("scoring_service", None),
}


def __getattr__(name: str) -> object:
    """Lazy import to avoid circular dependencies during module initialization."""
    if name in _LAZY_IMPORTS:
        module_name, import_name = _LAZY_IMPORTS[name]
        module = __import__(f"{__name__}.{module_name}", fromlist=[import_name or name])
        return getattr(module, import_name or name)

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
