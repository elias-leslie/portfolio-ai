"""Backward compatibility facade for watchlist service.

DEPRECATED: This module is kept for backward compatibility.
New code should import from:
- app.watchlist.watchlist_service (WatchlistService, CRUD operations)
- app.watchlist.scoring_service (refresh_watchlist_scores, scoring operations)
- app.watchlist.snapshot_service (snapshot operations)
"""

from __future__ import annotations

# Re-export from refresh_processor (functions moved during refactoring)
from .refresh_processor import (
    calculate_price_change as _calculate_price_change,  # Renamed (removed _ prefix)
)
from .refresh_processor import (
    detect_missing_historical_data,
)

# Re-export from scoring_service (for refresh_watchlist_scores and helpers)
from .scoring_service import (
    _get_redis_client,
    _load_default_weights,
    _load_latest_technical,
    _load_risk_budget,
    _load_stale_ttl_minutes,
    _load_watchlist_items,
    refresh_watchlist_scores,
)

# Re-export from watchlist_service (for WatchlistService class)
from .watchlist_service import WatchlistService

__all__ = [
    "WatchlistService",
    "_calculate_price_change",
    "_get_redis_client",
    "_load_default_weights",
    "_load_latest_technical",
    "_load_risk_budget",
    "_load_stale_ttl_minutes",
    "_load_watchlist_items",
    "detect_missing_historical_data",
    "refresh_watchlist_scores",
]
