"""Background task coordination for watchlist operations."""

from __future__ import annotations

from app.constants import DEFAULT_BACKFILL_DAYS, DEFAULT_DAILY_REFRESH_DAYS
from app.logging_config import get_logger
from app.tasks import (
    ingest_historical_ohlcv,
    refresh_single_symbol_scores_task,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)
from app.tasks.ingestion import ingest_fundamental_data, update_earnings_surprises
from app.tasks.reference_tasks import refresh_yfinance_reference_data

logger = get_logger(__name__)


def schedule_new_symbol_tasks(symbol: str) -> None:
    """Schedule background tasks for a newly added symbol.

    Coordinates data ingestion, technical indicators, and score refresh.
    Hatchet ConcurrencyExpression handles backpressure natively.

    Args:
        symbol: Stock symbol
    """
    try:
        ingest_historical_ohlcv(symbols=[symbol], days=DEFAULT_BACKFILL_DAYS)
        logger.info(
            "Triggered historical data ingestion", symbol=symbol, days=DEFAULT_BACKFILL_DAYS
        )

        ingest_fundamental_data(symbols=[symbol])
        logger.info("fundamental_data_ingestion_triggered", symbol=symbol)

        update_earnings_surprises([symbol])
        logger.info("earnings_surprises_fetch_triggered", symbol=symbol)

        refresh_yfinance_reference_data()
        logger.info("yfinance_reference_refresh_triggered", symbol=symbol)

        update_technical_indicators([symbol])
        logger.info("technical_indicators_calculation_triggered", symbol=symbol)

        refresh_single_symbol_scores_task(symbol)
        logger.info("single_symbol_score_refresh_triggered", symbol=symbol)

    except Exception as bg_error:
        logger.warning(
            "background_tasks_trigger_failed", symbol=symbol, error=str(bg_error)
        )


def schedule_refresh_tasks(symbols: list[str]) -> None:
    """Schedule background tasks for refreshing existing watchlist data.

    Coordinates data refresh, technical indicators update, and score refresh.
    Hatchet ConcurrencyExpression handles backpressure natively.

    Args:
        symbols: List of symbols to refresh
    """
    try:
        ingest_historical_ohlcv(symbols=symbols, days=DEFAULT_DAILY_REFRESH_DAYS)
        logger.info("ohlcv_data_refresh_triggered", symbols=symbols)

        update_technical_indicators(symbols)
        logger.info("technical_indicators_update_triggered", symbols=symbols)

        refresh_watchlist_scores_task()
        logger.info("watchlist_score_refresh_triggered")

    except Exception as bg_error:
        logger.warning("background_refresh_tasks_trigger_failed", error=str(bg_error))
