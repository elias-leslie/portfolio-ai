"""Background task coordination for watchlist operations."""

from __future__ import annotations

from app.logging_config import get_logger
from app.tasks import (
    ingest_historical_ohlcv,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)

logger = get_logger(__name__)


def schedule_new_ticker_tasks(symbol: str) -> None:
    """Schedule background tasks for a newly added ticker.

    Coordinates data ingestion, technical indicators, and score refresh.

    Args:
        symbol: Stock ticker symbol

    Note:
        This schedules async tasks and logs errors but doesn't raise exceptions.
        Failures in background tasks should not block the API response.
        Watchlist is user-level (not account-specific), so no account_id needed.
    """
    try:
        # Ingest 5 years of historical OHLCV data (~1300 trading days)
        # This ensures sufficient data for backtesting (1-year lookback)
        ingest_historical_ohlcv.delay(tickers=[symbol], days=1300)
        logger.info("Triggered historical data ingestion (5 years)", symbol=symbol)

        # Calculate technical indicators (will run after ingestion completes)
        # Increased delay to allow 5-year data fetch to complete
        update_technical_indicators.apply_async(
            args=[[symbol]], countdown=120
        )  # Wait 2 min for ingestion
        logger.info("Scheduled technical indicators calculation", symbol=symbol)

        # Refresh watchlist scores after data ingestion
        # Note: The refresh logic now safely skips tickers without sufficient historical data,
        # preventing score degradation for existing tickers
        refresh_watchlist_scores_task.apply_async(countdown=180)  # Wait 3 min for everything
        logger.info("Scheduled watchlist score refresh")

    except Exception as bg_error:
        # Log but don't fail the request - background tasks are async
        logger.warning(
            "Failed to trigger background tasks for new ticker", symbol=symbol, error=str(bg_error)
        )


def schedule_refresh_tasks(tickers: list[str]) -> None:
    """Schedule background tasks for refreshing existing watchlist data.

    Coordinates data refresh, technical indicators update, and score refresh.

    Args:
        tickers: List of ticker symbols to refresh

    Note:
        This schedules async tasks and logs errors but doesn't raise exceptions.
        Failures in background tasks should not block the API response.
        Watchlist is user-level (not account-specific), so no account_id needed.
    """
    try:
        # Fetch latest OHLCV data (last 5 days to update recent bars)
        ingest_historical_ohlcv.delay(tickers=tickers, days=5)
        logger.info("Triggered OHLCV data refresh", tickers=tickers)

        # Update technical indicators (will run after ingestion completes)
        update_technical_indicators.apply_async(args=[tickers], countdown=15)
        logger.info("Scheduled technical indicators update", tickers=tickers)

        # Refresh watchlist scores (will run after indicators complete)
        refresh_watchlist_scores_task.apply_async(countdown=30)
        logger.info("Scheduled watchlist score refresh")

    except Exception as bg_error:
        logger.warning("Failed to trigger background refresh tasks", error=str(bg_error))
