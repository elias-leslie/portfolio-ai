"""Watchlist CRUD service re-exports.

Re-exports from the _service package for convenience.
"""

from __future__ import annotations

from ._service import WatchlistService, _calculate_price_change
from ._service.formatters import _normalize_recent_news_payload

__all__ = [
    "WatchlistService",
    "_calculate_price_change",
    "_normalize_recent_news_payload",
]
