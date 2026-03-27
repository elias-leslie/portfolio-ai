"""Repository layer for watchlist database operations."""

from __future__ import annotations

from ..storage import PortfolioStorage
from ._repository_mixins import (
    _WatchlistCoreReadRepository,
    _WatchlistNewsRepository,
    _WatchlistReviewReadRepository,
    _WatchlistWriteRepository,
)


class WatchlistRepository(
    _WatchlistCoreReadRepository,
    _WatchlistReviewReadRepository,
    _WatchlistNewsRepository,
    _WatchlistWriteRepository,
):
    """Composite repository preserving the existing public API."""

    def __init__(self, storage: PortfolioStorage):
        self.storage = storage


__all__ = ["WatchlistRepository"]
