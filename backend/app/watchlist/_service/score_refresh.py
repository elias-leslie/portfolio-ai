"""Score refresh helpers for watchlist service.

This module provides:
- Historical data backfill logic
- Score snapshot building
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.watchlist.scoring import calculate_watchlist_scores

from ...constants import DEFAULT_BACKFILL_DAYS
from ...logging_config import get_logger
from ...portfolio.models import PriceData
from ...storage import PortfolioStorage
from ..data_loaders import load_default_weights, load_latest_technical, load_stale_ttl_minutes
from ..models import TechnicalSnapshot, WatchlistScoreInputs, WatchlistSnapshot

logger = get_logger(__name__)


def backfill_historical(symbol: str, item_id: str) -> None:
    """Attempt to backfill historical OHLCV data for symbol."""
    try:
        from ...tasks.ingestion import ingest_historical_ohlcv  # noqa: PLC0415

        ingest_historical_ohlcv([symbol], days=DEFAULT_BACKFILL_DAYS)
        logger.info(
            "watchlist_refresh_scores_queued_backfill",
            symbol=symbol,
            item_id=item_id,
        )
    except Exception as e:
        logger.warning(
            "watchlist_refresh_scores_backfill_failed", symbol=symbol, error=str(e)
        )


def build_score_snapshot(
    storage: PortfolioStorage,
    item_id: str,
    symbol: str,
    price_data: PriceData | None,
    change_pct: float,
) -> WatchlistSnapshot:
    """Build a WatchlistSnapshot from current price and technical data."""
    if price_data is None:
        raise ValueError(f"price_data is required to build score snapshot for {symbol}")
    technical_map = load_latest_technical(storage, [symbol])
    technical_snapshot = technical_map.get(symbol, TechnicalSnapshot())
    technical_snapshot.price = price_data.price

    default_weights = load_default_weights(storage)
    stale_ttl_minutes = load_stale_ttl_minutes(storage)
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

    return WatchlistSnapshot(
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


__all__ = ["backfill_historical", "build_score_snapshot"]
