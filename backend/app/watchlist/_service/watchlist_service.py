"""Core watchlist service with CRUD operations.

This module provides:
- WatchlistService class with all CRUD operations
- Score refresh logic

Note: Gap analysis has been migrated to [DEBT] subtasks on features.
See tasks/tasks-tech-debt-to-feature-subtasks-migration.md
"""

from __future__ import annotations

from typing import Any

from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...storage import PortfolioStorage
from ...utils.preferences_loader import UserPreferences
from ..watchlist_repository import WatchlistRepository
from .builders import build_base_item_data, build_snapshot_data
from .helpers import _calculate_price_change
from .item_enrichment import (
    build_data_quality_map,
    build_news_intelligence_map,
    enrich_data_quality,
    enrich_news_intelligence,
    enrich_priority_indicators,
)
from .score_refresh import backfill_historical, build_score_snapshot

logger = get_logger(__name__)


class WatchlistService:
    """Service layer for watchlist operations."""

    def __init__(self, storage: PortfolioStorage):
        """Initialize watchlist service."""
        self.storage = storage
        self.price_fetcher = PriceDataFetcher(storage)
        self.repo = WatchlistRepository(storage)

    def get_items_with_scores(self) -> list[dict[str, Any]]:
        """Get all watchlist items with latest scores (LATERAL JOIN eliminates N+1 pattern)."""
        items_df = self.repo.get_all_items_with_snapshots()

        if items_df.is_empty():
            return []

        # Load preferences once (not per-item)
        prefs = UserPreferences.load_all(self.storage)
        stale_ttl_minutes = prefs.get_stale_ttl_minutes()

        # Pre-fetch enrichment data for all symbols in batch (avoids N+1 queries)
        symbols = [row["symbol"] for row in items_df.iter_rows(named=True)]
        news_intel_map = build_news_intelligence_map(self.repo, symbols)
        data_quality_map = build_data_quality_map(self.storage, symbols)

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            item_data = build_base_item_data(row)

            if row.get("overall_score") is not None:
                build_snapshot_data(self.storage, item_data, row, stale_ttl_minutes)

            symbol = row["symbol"]
            item_data["news_intelligence"] = news_intel_map.get(symbol)
            item_data["data_quality"] = data_quality_map.get(symbol)

            results.append(item_data)

        enrich_priority_indicators(results)
        return results

    def get_item_with_score_by_id(self, item_id: str) -> dict[str, Any] | None:
        """Get a single watchlist item by ID with its latest score."""
        item_df = self.repo.get_item_by_id(item_id)

        if item_df.is_empty():
            return None

        row = item_df.to_dicts()[0]
        item_data = build_base_item_data(row)

        snapshot_df = self.repo.get_latest_snapshot(item_id)

        if not snapshot_df.is_empty():
            snap_row = snapshot_df.to_dicts()[0]
            prefs = UserPreferences.load_all(self.storage)
            stale_ttl_minutes = prefs.get_stale_ttl_minutes()
            build_snapshot_data(self.storage, item_data, snap_row, stale_ttl_minutes)

        symbol = row["symbol"]
        enrich_news_intelligence(self.repo, symbol, item_data)
        enrich_data_quality(self.storage, symbol, item_data)

        # Gap analysis removed - migrated to [DEBT] subtasks on features
        item_data["readiness_score"] = 100.0
        item_data["confidence_level"] = "HIGH"
        item_data["gap_warning"] = None

        return item_data

    def refresh_scores(self, item_id: str, symbol: str) -> None:
        """Refresh scores for a single watchlist item."""
        price_data = self.price_fetcher.fetch_price_data([symbol]).get(symbol)
        if not price_data or price_data.price <= 0:
            raise ValueError(f"Unable to fetch price data for {symbol}")

        change_pct, has_historical_data = _calculate_price_change(
            self.storage, symbol, price_data.price, item_id
        )

        if not has_historical_data:
            backfill_historical(symbol, item_id)

        if change_pct is None:
            raise ValueError(f"Insufficient historical data for {symbol} - need at least 2 days")

        snapshot = build_score_snapshot(self.storage, item_id, symbol, price_data, change_pct)
        self.repo.upsert_snapshot(snapshot.to_upsert_params())
        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)


__all__ = ["WatchlistService"]
