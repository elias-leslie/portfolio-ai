"""Watchlist scoring sub-module.

This package contains the refactored scoring service split into focused modules:
- redis_tracker: Redis-based progress tracking
- batch_loader: Batch data loading operations
- context: Scoring context initialization
- processor: Single symbol processing
- aggregator: Multi-symbol processing and result aggregation

Main entry point:
- refresh_watchlist_scores: Public API for scoring watchlist items
"""

from __future__ import annotations

# Re-export scoring calculations from parent module (app.watchlist.scoring vs app.watchlist.scoring/)
# Import from absolute path to avoid mypy confusion
from ..scoring import (
    _is_stale,
    calculate_watchlist_scores,
)
from .aggregator import aggregate_results, process_all_symbols
from .batch_loader import (
    fetch_news_batch,
    fetch_prices_in_batches,
    load_latest_technical,
    load_watchlist_items,
    trigger_auto_backfill,
)
from .context import initialize_scoring_context
from .processor import process_single_symbol
from .redis_tracker import complete_refresh, get_redis_client, init_refresh_status, update_progress
from .scoring_service import refresh_watchlist_scores

__all__ = [
    "_is_stale",
    "aggregate_results",
    # Score calculations (from parent scoring.py)
    "calculate_watchlist_scores",
    "complete_refresh",
    "fetch_news_batch",
    "fetch_prices_in_batches",
    # Redis tracking
    "get_redis_client",
    "init_refresh_status",
    # Context
    "initialize_scoring_context",
    "load_latest_technical",
    # Batch loading
    "load_watchlist_items",
    "process_all_symbols",
    # Processing
    "process_single_symbol",
    # Main API
    "refresh_watchlist_scores",
    "trigger_auto_backfill",
    "update_progress",
]
