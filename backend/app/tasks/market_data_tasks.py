"""Celery tasks for market data maintenance.

This module defines background tasks for maintaining historical market data,
ensuring all required market indicators have complete 252-day history.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.cboe_source import get_cboe_source
from app.storage import get_storage
from app.tasks.data_ingestion_tasks import ingest_historical_ohlcv

logger = get_logger(__name__)

# Target symbols for market intelligence
ALL_MARKET_SYMBOLS = [
    "SPY",  # S&P 500 ETF (for RSI calculations)
    "^GSPC",  # S&P 500 Index
    "^VIX",  # Volatility Index
    "^TNX",  # 10-Year Treasury Note Yield
    "DX-Y.NYB",  # US Dollar Index
    "XLK",  # Technology
    "XLF",  # Financials
    "XLE",  # Energy
    "XLV",  # Healthcare
    "XLY",  # Consumer Discretionary
    "XLP",  # Consumer Staples
    "XLI",  # Industrials
    "XLU",  # Utilities
    "XLRE",  # Real Estate
    "XLB",  # Materials
    "XLC",  # Communication Services
]

# Target: 252 trading days (approximately 1 year)
TARGET_DAYS = 252


def _check_symbol_data(ticker: str) -> tuple[bool, int]:
    """Check if symbol has sufficient historical data.

    Args:
        ticker: Symbol to check

    Returns:
        Tuple of (needs_backfill, days_available)
    """
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) as days FROM day_bars WHERE ticker = %s",
            [ticker],
        ).fetchone()

    days_available = result[0] if result else 0

    # Need backfill if less than TARGET_DAYS
    needs_backfill = days_available < TARGET_DAYS

    return needs_backfill, days_available


@celery_app.task(name="maintain_historical_market_data", bind=True)  # type: ignore[misc]
def maintain_historical_market_data(  # type: ignore[no-untyped-def]
    self,
) -> dict[str, int | str | float]:
    """Maintain historical market data for all required indicators and sectors.

    This task is idempotent and self-healing:
    - Checks each symbol for sufficient data (252 trading days)
    - Backfills if missing or incomplete (uses ingest_historical_ohlcv)
    - Daily refresh handled by separate refresh-daily-ohlcv task
    - Safe to run repeatedly (scheduled daily at 04:00 UTC)

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - symbols_checked: Total symbols checked
        - symbols_backfilled: Number of symbols backfilled
        - symbols_ok: Number of symbols with sufficient data
        - duration_seconds: Total execution time

    Example:
        >>> # Manual trigger for testing
        >>> celery -A app.celery_app call app.tasks.market_data_tasks.maintain_historical_market_data
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info(
        "market_data_maintenance_started",
        task_id=task_id,
        symbols_count=len(ALL_MARKET_SYMBOLS),
        symbols=ALL_MARKET_SYMBOLS,
    )

    try:
        # Check which symbols need backfill
        symbols_to_backfill = []
        symbols_ok = 0

        for ticker in ALL_MARKET_SYMBOLS:
            needs_backfill, days_available = _check_symbol_data(ticker)

            if needs_backfill:
                symbols_to_backfill.append(ticker)
                logger.info(
                    "market_data_maintenance_needs_backfill",
                    ticker=ticker,
                    days_available=days_available,
                    target_days=TARGET_DAYS,
                )
            else:
                symbols_ok += 1
                logger.info(
                    "market_data_maintenance_ok",
                    ticker=ticker,
                    days_available=days_available,
                )

        # Backfill symbols that need it (in one batch for efficiency)
        symbols_backfilled = 0
        if symbols_to_backfill:
            logger.info(
                "market_data_maintenance_backfilling",
                symbols_count=len(symbols_to_backfill),
                symbols=symbols_to_backfill,
            )

            # Call the existing ingest_historical_ohlcv task
            # Note: Using self (the task instance) to call the task synchronously
            backfill_result = ingest_historical_ohlcv(
                self,
                tickers=symbols_to_backfill,
                days=TARGET_DAYS,
            )

            symbols_backfilled = len(symbols_to_backfill)

            logger.info(
                "market_data_maintenance_backfill_complete",
                backfill_result=backfill_result,
            )

        # Calculate duration
        end_time = dt.datetime.now(dt.UTC)
        duration = (end_time - start_time).total_seconds()

        result: dict[str, int | str | float] = {
            "task_id": task_id,
            "symbols_checked": len(ALL_MARKET_SYMBOLS),
            "symbols_backfilled": symbols_backfilled,
            "symbols_ok": symbols_ok,
            "duration_seconds": duration,
        }

        logger.info(
            "market_data_maintenance_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "market_data_maintenance_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@celery_app.task(name="fetch_putcall_ratio", bind=True)  # type: ignore[misc]
def fetch_putcall_ratio(  # type: ignore[no-untyped-def]
    self,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Fetch Put/Call Ratio from CBOE official data.

    Scrapes CBOE Daily Market Statistics page for official put/call ratios.
    This is the gold standard for market-wide options sentiment.

    Data source: https://www.cboe.com/us/options/market_statistics/daily/

    The Put/Call Ratio is a market sentiment indicator:
    - Ratio > 1.0 = More puts than calls (bearish sentiment)
    - Ratio 0.7-1.0 = Neutral sentiment
    - Ratio < 0.7 = More calls than puts (bullish sentiment)

    Args:
        as_of_date: Date to fetch data for (YYYY-MM-DD). If None, uses today's data.
                    Note: CBOE updates daily, so this should match the date shown on their page.

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - date: Date from CBOE page (YYYY-MM-DD)
        - put_call_ratio: SPX+SPXW ratio (primary metric)
        - total_ratio: Total market-wide ratio (all CBOE options)
        - index_ratio: Index options ratio
        - equity_ratio: Equity options ratio
        - success: Boolean indicating success

    Example:
        >>> # Manual trigger for testing
        >>> celery -A app.celery_app call app.tasks.market_data_tasks.fetch_putcall_ratio

    Note:
        This task should be scheduled daily at 04:30 UTC (after market close).
        Uses Playwright to render JavaScript-heavy CBOE page.
        Data represents daily trading volume ratios (not open interest).
    """
    task_id = self.request.id

    logger.info(
        "fetch_putcall_ratio_started",
        task_id=task_id,
        requested_date=as_of_date,
    )

    try:
        # Fetch from CBOE official source
        cboe = get_cboe_source()
        data = cboe.fetch_put_call_ratios()

        # Extract key values
        cboe_date = data["date"]
        # Use SPX+SPXW as primary ratio (S&P 500 specific)
        # Fall back to total if SPX not available
        put_call_ratio = data.get("spx") or data["total"]

        # Store in fear_greed_inputs table
        storage = get_storage()
        with storage.connection() as conn:
            # Insert or update
            conn.execute(
                """
                INSERT INTO fear_greed_inputs (as_of_date, put_call_ratio, source_map)
                VALUES (%s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    put_call_ratio = EXCLUDED.put_call_ratio,
                    source_map = fear_greed_inputs.source_map || EXCLUDED.source_map
                """,
                (
                    cboe_date,
                    put_call_ratio,
                    '{"put_call_ratio": "cboe_daily_statistics"}',
                ),
            )
            conn.commit()

        result = {
            "task_id": task_id,
            "date": cboe_date,
            "put_call_ratio": round(put_call_ratio, 4),
            "total_ratio": round(data["total"], 4),
            "index_ratio": round(data["index"], 4) if data.get("index") else None,
            "equity_ratio": round(data["equity"], 4) if data.get("equity") else None,
            "success": True,
        }

        logger.info(
            "fetch_putcall_ratio_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "fetch_putcall_ratio_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "date": as_of_date or dt.date.today().isoformat(),
            "error": str(e),
            "success": False,
        }
