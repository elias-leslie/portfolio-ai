"""Tasks for analytics data ingestion.

This module defines background tasks for ingesting analytics data like
covariance matrices and earnings surprises.
"""

from __future__ import annotations

import uuid

from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)


def _query_symbols(query: str) -> list[str]:
    result = get_storage().query(query)
    return result.get_column("symbol").to_list() if not result.is_empty() else []


def _get_watchlist_and_portfolio_symbols() -> list[str]:
    watchlist = _query_symbols("SELECT DISTINCT symbol FROM watchlist_items")
    portfolio = _query_symbols("SELECT DISTINCT symbol FROM portfolio_positions")
    return list(set(watchlist + portfolio))


def _resolve_covariance_symbols(symbols: list[str] | None) -> list[str]:
    if symbols is not None:
        return symbols
    discovered = _get_watchlist_and_portfolio_symbols()
    return discovered if discovered else ["SPY"]


def _run_covariance_update(
    task_id: str, resolved: list[str], lookback_days: int
) -> dict[str, int | str]:
    from app.analytics.covariance import update_covariance_matrix

    pairs_updated = update_covariance_matrix(get_storage(), resolved, lookback_days)
    logger.info(
        "update_portfolio_covariance_completed",
        task_id=task_id,
        symbols_count=len(resolved),
        pairs_updated=pairs_updated,
    )
    return {
        "task_id": task_id,
        "symbols_count": len(resolved),
        "pairs_updated": pairs_updated,
        "status": "success",
    }


def update_portfolio_covariance(
    symbols: list[str] | None = None,
    lookback_days: int = TRADING_DAYS_PER_YEAR,
) -> dict[str, int | str]:
    """Update portfolio covariance matrix for proper risk calculation (GAP-020).

    Args:
        symbols: Optional list of symbols. If None, uses all watchlist + portfolio symbols.
        lookback_days: Number of trading days for calculation (default: 252 = 1 year).

    Returns:
        Dict with task_id, symbols_count, pairs_updated, and status keys.
    """
    task_id = str(uuid.uuid4())
    resolved = _resolve_covariance_symbols(symbols)

    logger.info(
        "update_portfolio_covariance_started",
        task_id=task_id,
        symbols=symbols,
        lookback_days=lookback_days,
    )

    try:
        return _run_covariance_update(task_id, resolved, lookback_days)
    except Exception as e:
        logger.error(
            "update_portfolio_covariance_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise


def _fetch_earnings_for_symbols(symbols: list[str]) -> int:
    from app.analytics.earnings_surprise import fetch_and_store_earnings_surprises

    storage = get_storage()
    total_records = 0
    for symbol in symbols:
        try:
            total_records += fetch_and_store_earnings_surprises(storage, symbol)
        except Exception as e:
            logger.warning("earnings_surprise_symbol_failed", symbol=symbol, error=str(e))
    return total_records


def _resolve_earnings_symbols(symbols: list[str] | None) -> list[str]:
    return list(symbols) if symbols else _get_watchlist_and_portfolio_symbols()


def _run_earnings_update(task_id: str, resolved: list[str]) -> dict[str, int | str]:
    if not resolved:
        logger.info("update_earnings_surprises_no_symbols", task_id=task_id)
        return {"task_id": task_id, "symbols_count": 0, "records_saved": 0, "status": "success"}

    total_records = _fetch_earnings_for_symbols(resolved)
    logger.info(
        "update_earnings_surprises_completed",
        task_id=task_id,
        symbols_count=len(resolved),
        records_saved=total_records,
    )
    return {
        "task_id": task_id,
        "symbols_count": len(resolved),
        "records_saved": total_records,
        "status": "success",
    }


def update_earnings_surprises(
    symbols: list[str] | None = None,
) -> dict[str, int | str]:
    """Update earnings surprise data for watchlist/portfolio symbols (GAP-003).

    Scheduled to run weekly (earnings are quarterly events).

    Args:
        symbols: Optional list of symbols. If None, uses watchlist + portfolio symbols.

    Returns:
        Dict with task_id, symbols_count, records_saved, and status keys.
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "update_earnings_surprises_started",
        task_id=task_id,
        symbols=symbols[:5] if symbols else None,
    )

    try:
        return _run_earnings_update(task_id, _resolve_earnings_symbols(symbols))
    except Exception as e:
        logger.error(
            "update_earnings_surprises_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
