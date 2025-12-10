"""Core watchlist service with CRUD operations.

This module provides:
- WatchlistService class with all CRUD operations
- Score refresh logic

Note: Gap analysis has been migrated to [DEBT] subtasks on features.
See tasks/tasks-tech-debt-to-feature-subtasks-migration.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

# Import from scoring.py (file, not scoring/ package)
from app.watchlist.scoring import calculate_watchlist_scores

from ...constants import DEFAULT_BACKFILL_DAYS
from ...logging_config import get_logger
from ...portfolio.price_fetcher import PriceDataFetcher
from ...storage import PortfolioStorage
from ...utils.preferences_loader import UserPreferences
from ..data_loaders import (
    load_default_weights,
    load_latest_technical,
    load_stale_ttl_minutes,
)

# Import data quality function
from ..data_quality import calculate_data_quality
from ..models import (
    TechnicalSnapshot,
    WatchlistItemDict,
    WatchlistScoreInputs,
    WatchlistSnapshot,
)
from ..priority import calculate_priority_indicators
from ..watchlist_repository import WatchlistRepository
from .builders import build_base_item_data, build_snapshot_data
from .helpers import _calculate_price_change
from .intelligence import build_news_intelligence

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

        results: list[dict[str, Any]] = []

        for row in items_df.iter_rows(named=True):
            item_data = build_base_item_data(row)

            # Add snapshot data if available
            if row.get("overall_score") is not None:
                build_snapshot_data(self.storage, item_data, row, stale_ttl_minutes)

            # Build news intelligence
            try:
                news_intel = build_news_intelligence(self.repo, row["symbol"])
                item_data["news_intelligence"] = (
                    news_intel.model_dump(mode="json") if news_intel else None
                )
            except Exception as e:
                logger.warning(
                    "watchlist_news_intelligence_failed",
                    symbol=row["symbol"],
                    error=str(e),
                )
                item_data["news_intelligence"] = None

            # Calculate data quality
            try:
                symbol = row["symbol"]
                quality_map = calculate_data_quality(self.storage, [symbol])
                dq = quality_map.get(symbol)
                if dq:
                    item_data["data_quality"] = {
                        "overall_pct": dq.overall_pct,
                        "pillars": {
                            name: {
                                "status": pq.status,
                                "score": pq.score,
                                "details": pq.details,
                            }
                            for name, pq in dq.pillars.items()
                        },
                    }
                else:
                    item_data["data_quality"] = None
            except Exception as e:
                logger.warning(
                    "watchlist_data_quality_failed",
                    symbol=row["symbol"],
                    error=str(e),
                )
                item_data["data_quality"] = None

            results.append(item_data)

        # Calculate priority indicators
        for item in results:
            # Cast to WatchlistItemDict - structure matches from builders
            indicators = calculate_priority_indicators(
                cast(list[WatchlistItemDict], results), cast(WatchlistItemDict, item)
            )
            item["priority_indicators"] = [ind.model_dump() for ind in indicators]

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

            # Load preferences once
            prefs = UserPreferences.load_all(self.storage)
            stale_ttl_minutes = prefs.get_stale_ttl_minutes()

            # Use helper to build snapshot data
            build_snapshot_data(self.storage, item_data, snap_row, stale_ttl_minutes)

        # Build news intelligence summary
        try:
            news_intel = build_news_intelligence(self.repo, row["symbol"])
            item_data["news_intelligence"] = (
                news_intel.model_dump(mode="json") if news_intel else None
            )
        except Exception as e:
            logger.warning(
                "watchlist_news_intelligence_failed",
                symbol=row["symbol"],
                error=str(e),
            )
            item_data["news_intelligence"] = None

        # Calculate data quality
        try:
            symbol = row["symbol"]
            quality_map = calculate_data_quality(self.storage, [symbol])
            dq = quality_map.get(symbol)
            if dq:
                item_data["data_quality"] = {
                    "overall_pct": dq.overall_pct,
                    "pillars": {
                        name: {
                            "status": pq.status,
                            "score": pq.score,
                            "details": pq.details,
                        }
                        for name, pq in dq.pillars.items()
                    },
                }
            else:
                item_data["data_quality"] = None
        except Exception as e:
            logger.warning(
                "watchlist_data_quality_failed",
                symbol=row["symbol"],
                error=str(e),
            )
            item_data["data_quality"] = None

        # Gap analysis removed - migrated to [DEBT] subtasks on features
        # Set default values for readiness fields (always high confidence now)
        item_data["readiness_score"] = 100.0  # All data is available
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
            try:
                from ...tasks.ingestion import ingest_historical_ohlcv  # noqa: PLC0415

                ingest_historical_ohlcv.delay([symbol], days=DEFAULT_BACKFILL_DAYS)
                logger.info(
                    "watchlist_refresh_scores_queued_backfill",
                    symbol=symbol,
                    item_id=item_id,
                )
            except Exception as e:
                logger.warning(
                    "watchlist_refresh_scores_backfill_failed", symbol=symbol, error=str(e)
                )

        if change_pct is None:
            raise ValueError(f"Insufficient historical data for {symbol} - need at least 2 days")

        technical_map = load_latest_technical(self.storage, [symbol])
        technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
        technical_snapshot.price = price_data.price

        default_weights = load_default_weights(self.storage)
        stale_ttl_minutes = load_stale_ttl_minutes(self.storage)
        now = datetime.now(UTC)

        breakdown = calculate_watchlist_scores(
            WatchlistScoreInputs(
                price=price_data,
                price_change_pct=change_pct,
                technical=technical_snapshot,
                weights=default_weights,
                now=now,
                stale_ttl_minutes=stale_ttl_minutes,
            )
        )

        snapshot = WatchlistSnapshot(
            item_id=item_id,
            fetched_at=now,
            price=price_data.price,
            change_pct=change_pct,
            beta=price_data.beta,
            volatility=price_data.volatility,
            overall_score=breakdown.overall,
            technical_score=breakdown.technical.score,
            raw_metrics=breakdown.to_snapshot_payload(),
        )

        self.repo.upsert_snapshot(snapshot.to_upsert_params())
        logger.info("Watchlist item scores refreshed", item_id=item_id, symbol=symbol)


__all__ = ["WatchlistService"]
