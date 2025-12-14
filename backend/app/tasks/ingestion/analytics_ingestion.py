"""Celery tasks for analytics data ingestion.

This module defines background tasks for ingesting analytics data like
covariance matrices and earnings surprises.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="update_portfolio_covariance",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def update_portfolio_covariance(  # type: ignore[no-untyped-def]
    self,
    symbols: list[str] | None = None,
    lookback_days: int = 252,
) -> dict[str, int | str]:
    """Update portfolio covariance matrix for proper risk calculation (GAP-020).

    Calculates pairwise covariance matrix from historical returns in day_bars.
    Uses the formula: sigma_portfolio = sqrt(w' * Cov * w)

    Args:
        symbols: Optional list of symbols. If None, uses all watchlist + portfolio symbols.
        lookback_days: Number of trading days for calculation (default: 252 = 1 year)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_count: Number of unique symbols processed
        - pairs_updated: Number of covariance pairs calculated
        - status: 'success' or 'error'

    Example:
        >>> update_portfolio_covariance.delay()  # Updates all watchlist/portfolio symbols
        >>> update_portfolio_covariance.delay(["AAPL", "MSFT", "GOOGL"])  # Custom list
    """
    from app.analytics.covariance import update_covariance_matrix

    task_id = self.request.id
    logger.info(
        "update_portfolio_covariance_started",
        task_id=task_id,
        symbols=symbols,
        lookback_days=lookback_days,
    )

    try:
        storage = get_storage()

        # If no symbols specified, get all watchlist + portfolio symbols
        if symbols is None:
            # Get watchlist symbols
            watchlist_result = storage.query("SELECT DISTINCT symbol FROM watchlist_items")
            watchlist_symbols = (
                watchlist_result.get_column("symbol").to_list()
                if not watchlist_result.is_empty()
                else []
            )

            # Get portfolio symbols
            portfolio_result = storage.query("SELECT DISTINCT symbol FROM portfolio_positions")
            portfolio_symbols = (
                portfolio_result.get_column("symbol").to_list()
                if not portfolio_result.is_empty()
                else []
            )

            # Combine and deduplicate
            all_symbols = list(set(watchlist_symbols + portfolio_symbols))
            symbols = all_symbols if all_symbols else ["SPY"]

        # Update covariance matrix
        pairs_updated = update_covariance_matrix(storage, symbols, lookback_days)

        logger.info(
            "update_portfolio_covariance_completed",
            task_id=task_id,
            symbols_count=len(symbols),
            pairs_updated=pairs_updated,
        )

        return {
            "task_id": str(task_id),
            "symbols_count": len(symbols),
            "pairs_updated": pairs_updated,
            "status": "success",
        }

    except Exception as e:
        logger.error(
            "update_portfolio_covariance_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(
    bind=True,
    name="update_earnings_surprises",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def update_earnings_surprises(  # type: ignore[no-untyped-def]
    self,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Update earnings surprise data for watchlist/portfolio symbols (GAP-003).

    Fetches historical earnings surprise data (EPS estimate vs actual)
    from Finnhub API and stores in earnings_surprises table.

    Scheduled to run weekly (earnings are quarterly events).

    Args:
        symbols: Optional list of symbols. If None, uses watchlist + portfolio symbols.

    Returns:
        Dict with:
        - task_id: Celery task ID
        - symbols_count: Number of symbols processed
        - records_saved: Number of earnings records saved
        - status: success or error
    """
    from app.analytics.earnings_surprise import fetch_and_store_earnings_surprises

    task_id = self.request.id or str(uuid.uuid4())

    logger.info(
        "update_earnings_surprises_started",
        task_id=task_id,
        symbols=symbols[:5] if symbols else None,
    )

    try:
        storage = get_storage()

        # Auto-discover symbols if not provided
        if not symbols:
            # Get watchlist symbols
            watchlist_result = storage.query("SELECT DISTINCT symbol FROM watchlist_items")
            watchlist_symbols = (
                watchlist_result.get_column("symbol").to_list()
                if not watchlist_result.is_empty()
                else []
            )

            # Get portfolio symbols
            portfolio_result = storage.query("SELECT DISTINCT symbol FROM portfolio_positions")
            portfolio_symbols = (
                portfolio_result.get_column("symbol").to_list()
                if not portfolio_result.is_empty()
                else []
            )

            # Combine and deduplicate
            all_symbols = list(set(watchlist_symbols + portfolio_symbols))
            symbols = all_symbols if all_symbols else []

        if not symbols:
            logger.info("update_earnings_surprises_no_symbols", task_id=task_id)
            return {
                "task_id": str(task_id),
                "symbols_count": 0,
                "records_saved": 0,
                "status": "success",
            }

        total_records = 0
        for symbol in symbols:
            try:
                records = fetch_and_store_earnings_surprises(storage, symbol)
                total_records += records
            except Exception as e:
                logger.warning(
                    "earnings_surprise_symbol_failed",
                    symbol=symbol,
                    error=str(e),
                )

        logger.info(
            "update_earnings_surprises_completed",
            task_id=task_id,
            symbols_count=len(symbols),
            records_saved=total_records,
        )

        return {
            "task_id": str(task_id),
            "symbols_count": len(symbols),
            "records_saved": total_records,
            "status": "success",
        }

    except Exception as e:
        logger.error(
            "update_earnings_surprises_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
