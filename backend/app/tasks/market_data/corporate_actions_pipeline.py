"""
Corporate Actions Pipeline - Buybacks, Dividends, Splits.

Fetches share repurchase data from yfinance cash flow statements.
Runs weekly for watchlist symbols (large caps).

FEAT-175: Share Buybacks
"""

from __future__ import annotations

import datetime as dt
from typing import Any


from app.logging_config import get_logger
from app.sources.buyback_source import fetch_and_store_buybacks
from app.storage import get_storage

logger = get_logger(__name__)


def _get_watchlist_symbols() -> list[str]:
    """Get symbols from watchlist (large caps)."""
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute("SELECT DISTINCT symbol FROM watchlist ORDER BY symbol").fetchall()
    return [str(r[0]) for r in result]


def fetch_corporate_actions(
    self: Task[..., Any],
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """
    Fetch and store corporate actions (buybacks) for symbols.

    Args:
        symbols: Optional list of symbols. If None, uses watchlist.

    Returns:
        Summary dict with processing results.
    """
    task_id = getattr(self.request, "id", None)

    logger.info(
        "fetch_corporate_actions_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Get symbols from watchlist if not provided
        if symbols is None:
            symbols = _get_watchlist_symbols()
            logger.info(
                "watchlist_symbols_loaded",
                count=len(symbols),
            )

        if not symbols:
            return {
                "success": True,
                "task_id": task_id,
                "message": "No symbols to process",
                "records_stored": 0,
            }

        # Fetch and store buyback data
        result = fetch_and_store_buybacks(storage, symbols)

        logger.info(
            "fetch_corporate_actions_completed",
            task_id=task_id,
            symbols_processed=result["symbols_processed"],
            records_stored=result["records_stored"],
            failed_count=len(result["failed_symbols"]),
        )

        return {
            "success": True,
            "task_id": task_id,
            "date": dt.date.today().isoformat(),
            **result,
        }

    except Exception as e:
        logger.error(
            "fetch_corporate_actions_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
        }
