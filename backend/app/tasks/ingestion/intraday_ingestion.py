"""Current-session intraday bar ingestion for the watchlist scanner.

Populates ``intraday_bars`` with the live trading day's 5-minute bars so the
Investing > Symbols "Today" trendline has honest data. Runs hourly during market
hours as the slow background baseline (see ``WATCHLIST_INTRADAY_CRONS``); when the
PWA is open the Data Feed freshness path tops it up faster (intraday_bars is
registered in TABLE_FRESHNESS_CONFIG, remediating via this same task). Each run
fetches via the tested yfinance -> TwelveData -> Polygon fallback chain, upserts
the latest session per symbol, and prunes sessions older than the short retention
window.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import polars as pl

from app.logging_config import get_logger
from app.sources.intraday_source import fetch_intraday_with_fallback
from app.storage import PortfolioStorage, get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.tasks.ingestion._ohlcv_helpers import load_watchlist_symbols
from app.utils.task_lifecycle import task_cleanup

logger = get_logger(__name__)

# Intraday is throwaway once the session closes (day_bars carries the official
# daily bar), so keep only a short rolling window to bound table size.
_INTRADAY_RETENTION_DAYS = 5

_INTRADAY_COLUMNS = [
    "symbol",
    "ts",
    "session_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "ingest_run_id",
]


def _latest_session_only(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep just each symbol's most recent session so writes stay one day deep.

    yfinance already returns only today, but the TwelveData/Polygon fallbacks
    return multi-day windows; the "Today" view only needs the latest session.
    """
    return frame.filter(
        pl.col("session_date") == pl.col("session_date").max().over("symbol")
    )


def _prune_old_sessions(storage: PortfolioStorage, ingest_run_id: str) -> int:
    with storage.connection() as conn:
        cursor = conn.execute(
            "DELETE FROM intraday_bars "
            "WHERE session_date < CURRENT_DATE - make_interval(days => %s)",
            [_INTRADAY_RETENTION_DAYS],
        )
        deleted = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
        conn.commit()
    if deleted:
        logger.info("intraday_pruned", ingest_run_id=ingest_run_id, rows_deleted=deleted)
    return deleted


def refresh_watchlist_intraday() -> dict[str, Any]:
    """Refresh current-session intraday bars for all watchlist symbols."""
    task_id = str(uuid.uuid4())
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    try:
        load_credentials_from_database()
        storage = get_storage()
        symbols = load_watchlist_symbols(storage, task_id)
        if not symbols:
            return {"task_id": task_id, "symbols_count": 0, "rows_upserted": 0, "sources": {}}

        frame, source_counts = fetch_intraday_with_fallback(symbols)
        rows_upserted = 0
        if frame is not None and not frame.is_empty():
            frame = _latest_session_only(frame).with_columns(
                pl.lit(ingest_run_id).alias("ingest_run_id")
            ).select(_INTRADAY_COLUMNS)
            storage.insert_dataframe("intraday_bars", frame, mode="upsert")
            rows_upserted = len(frame)
        else:
            logger.warning(
                "refresh_watchlist_intraday_no_data",
                ingest_run_id=ingest_run_id,
                symbols_count=len(symbols),
            )

        _prune_old_sessions(storage, ingest_run_id)

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        result = {
            "task_id": task_id,
            "ingest_run_id": ingest_run_id,
            "symbols_count": len(symbols),
            "rows_upserted": rows_upserted,
            "sources": source_counts,
            "duration_seconds": duration,
        }
        logger.info("refresh_watchlist_intraday_completed", **result)
        return result
    except Exception as e:
        logger.error(
            "refresh_watchlist_intraday_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
    finally:
        task_cleanup("refresh_watchlist_intraday")
