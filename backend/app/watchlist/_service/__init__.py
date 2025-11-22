"""Watchlist service internal package.

This package contains the refactored watchlist service split into focused modules.
Import from app.watchlist.watchlist_service for backward compatibility.
"""

from .helpers import _calculate_price_change
from .watchlist_service import WatchlistService

__all__ = [
    "WatchlistService",
    "_calculate_price_change",
]
