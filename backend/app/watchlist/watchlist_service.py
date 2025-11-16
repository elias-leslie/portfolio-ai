"""Watchlist CRUD service - backward compatibility re-export.

This module re-exports from the service package to maintain backward compatibility.
New code should import from app.watchlist.service directly.

Refactored from 733-line monolith into 6 focused modules:
- _service/formatters.py (118 lines) - Time formatting, event icons, news normalization
- _service/helpers.py (93 lines) - Price change calculation, JSON parsing, timestamps
- _service/score_helpers.py (73 lines) - Score alerts, staleness checks
- _service/builders.py (117 lines) - Snapshot and item data builders
- _service/intelligence.py (193 lines) - News intelligence, article parsing, sentiment
- _service/watchlist_service.py (223 lines) - Core WatchlistService CRUD operations
"""

from __future__ import annotations

# Re-export for backward compatibility
from ._service import WatchlistService, _calculate_price_change
from ._service.formatters import _normalize_recent_news_payload

__all__ = [
    "WatchlistService",
    "_calculate_price_change",
    "_normalize_recent_news_payload",
]
