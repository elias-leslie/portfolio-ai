"""Background task coordination for watchlist operations."""

from __future__ import annotations

from app.constants import DEFAULT_BACKFILL_DAYS, DEFAULT_DAILY_REFRESH_DAYS
from app.logging_config import get_logger
from app.services.celery_inspector import should_skip_cascade
from app.tasks import (
    ingest_historical_ohlcv,
    refresh_single_symbol_scores_task,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)

logger = get_logger(__name__)


def schedule_new_symbol_tasks(symbol: str) -> None:
    """Schedule background tasks for a newly added symbol.

    Coordinates data ingestion, technical indicators, and score refresh.
    Uses backpressure check to prevent queue saturation.

    Args:
        symbol: Stock symbol

    Note:
        This schedules async tasks and logs errors but doesn't raise exceptions.
        Failures in background tasks should not block the API response.
        Watchlist is user-level (not account-specific), so no account_id needed.
    """
    try:
        # Check queue backpressure before scheduling (except critical data ingestion)
        if should_skip_cascade():
            logger.warning(
                "Skipping cascade tasks due to queue backpressure",
                symbol=symbol,
                reason="queue_depth_exceeded",
            )
            # Still schedule data ingestion (critical for new symbol), skip the rest
            ingest_historical_ohlcv.delay(symbols=[symbol], days=DEFAULT_BACKFILL_DAYS)
            logger.info(
                "Triggered historical data ingestion", symbol=symbol, days=DEFAULT_BACKFILL_DAYS
            )
            return

        # Ingest historical OHLCV data (configurable via DEFAULT_BACKFILL_DAYS)
        ingest_historical_ohlcv.delay(symbols=[symbol], days=DEFAULT_BACKFILL_DAYS)
        logger.info(
            "Triggered historical data ingestion", symbol=symbol, days=DEFAULT_BACKFILL_DAYS
        )

        # Calculate technical indicators (will run after ingestion completes)
        # Increased delay to allow 5-year data fetch to complete
        update_technical_indicators.apply_async(
            args=[[symbol]], countdown=120
        )  # Wait 2 min for ingestion
        logger.info("Scheduled technical indicators calculation", symbol=symbol)

        # Refresh scores for this specific symbol (bypasses global rate limit)
        # Uses the dedicated single-symbol task for immediate feedback
        refresh_single_symbol_scores_task.apply_async(
            args=[symbol], countdown=180
        )  # Wait 3 min for data ingestion
        logger.info("Scheduled single-symbol score refresh", symbol=symbol)

    except Exception as bg_error:
        # Log but don't fail the request - background tasks are async
        logger.warning(
            "Failed to trigger background tasks for new symbol", symbol=symbol, error=str(bg_error)
        )


def schedule_refresh_tasks(symbols: list[str]) -> None:
    """Schedule background tasks for refreshing existing watchlist data.

    Coordinates data refresh, technical indicators update, and score refresh.
    Uses backpressure check to prevent queue saturation.

    Args:
        symbols: List of symbols to refresh

    Note:
        This schedules async tasks and logs errors but doesn't raise exceptions.
        Failures in background tasks should not block the API response.
        Watchlist is user-level (not account-specific), so no account_id needed.
    """
    try:
        # Check queue backpressure before scheduling cascade
        if should_skip_cascade():
            logger.warning(
                "Skipping refresh tasks due to queue backpressure",
                symbols=symbols,
                reason="queue_depth_exceeded",
            )
            return

        # Fetch latest OHLCV data to update recent bars
        ingest_historical_ohlcv.delay(symbols=symbols, days=DEFAULT_DAILY_REFRESH_DAYS)
        logger.info("Triggered OHLCV data refresh", symbols=symbols)

        # Update technical indicators (will run after ingestion completes)
        update_technical_indicators.apply_async(args=[symbols], countdown=15)
        logger.info("Scheduled technical indicators update", symbols=symbols)

        # Refresh watchlist scores (will run after indicators complete)
        refresh_watchlist_scores_task.apply_async(countdown=30)
        logger.info("Scheduled watchlist score refresh")

    except Exception as bg_error:
        logger.warning("Failed to trigger background refresh tasks", error=str(bg_error))
