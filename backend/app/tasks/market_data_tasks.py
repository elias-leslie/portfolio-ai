"""Celery tasks for market data maintenance.

This module defines background tasks for maintaining historical market data,
ensuring all required market indicators have complete 252-day history.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.cboe_source import get_cboe_source
from app.sources.fred import FREDSource
from app.storage import get_storage
from app.tasks.data_ingestion_tasks import ingest_historical_ohlcv
from app.tasks.indicator_tasks import calculate_fear_greed

if TYPE_CHECKING:
    from celery import Task  # type: ignore[import-untyped]

    from app.storage.facade import PortfolioStorage

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
    """Check if symbol has sufficient historical data AND is current.

    Args:
        ticker: Symbol to check

    Returns:
        Tuple of (needs_backfill, days_available)
    """
    storage = get_storage()
    with storage.connection() as conn:
        # Check both count AND latest date
        result = conn.execute(
            "SELECT COUNT(*) as days, MAX(date) as latest_date FROM day_bars WHERE ticker = %s",
            [ticker],
        ).fetchone()

    days_available = result[0] if result else 0
    latest_date = result[1] if result and result[1] else None

    # Need backfill if less than TARGET_DAYS OR data is not current
    # Data should be from today (intraday data available via yfinance)
    today = dt.date.today()

    is_stale = latest_date is None or latest_date < today
    needs_backfill = days_available < TARGET_DAYS or is_stale

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
            # Note: This is a bound task so self is automatically provided
            backfill_result = ingest_historical_ohlcv(
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
        # Get storage for metrics tracking
        storage = get_storage()

        # Fetch from CBOE official source (with metrics tracking enabled)
        cboe = get_cboe_source(storage=storage)
        data = cboe.fetch_put_call_ratios()

        # Extract key values
        cboe_date = data["date"]
        # Use SPX+SPXW as primary ratio (S&P 500 specific)
        # Fall back to total if SPX not available
        put_call_ratio = data.get("spx") or data["total"]

        # Store in fear_greed_inputs table
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


@celery_app.task(name="fetch_options_activity_metrics", bind=True)  # type: ignore[misc]
def fetch_options_activity_metrics(  # type: ignore[no-untyped-def]
    self,
) -> dict[str, Any]:
    """Fetch aggregated options activity metrics from CBOE Most Active page.

    Scrapes CBOE Most Active Options page and calculates daily metrics:
    - Sentiment: % of calls vs puts in top 25
    - Time horizon: % of near-term options (≤30 days)
    - Concentration: % of volume in top 5 contracts
    - Sector distribution: % by sector

    Data source: https://www.cboe.com/us/options/market_statistics/most_active/

    Returns:
        Dict with task results:
        - task_id: Celery task ID
        - as_of_date: Date of metrics (YYYY-MM-DD)
        - metrics: Dict with all calculated metrics
        - success: Boolean indicating success

    Example:
        >>> # Manual trigger for testing
        >>> celery -A app.celery_app call app.tasks.market_data_tasks.fetch_options_activity_metrics

    Note:
        This task should be scheduled daily at 21:15 UTC (4:15 PM ET, after market close).
        Uses Playwright to render JavaScript-heavy CBOE page.
        Stores aggregated metrics (not raw contracts) for trend analysis.
    """
    task_id = self.request.id

    logger.info(
        "fetch_options_activity_started",
        task_id=task_id,
    )

    try:
        # Get storage for metrics tracking
        storage = get_storage()

        # Import here to avoid circular dependency
        from app.sources.cboe_most_active import get_cboe_most_active_source  # noqa: PLC0415

        # Fetch from CBOE Most Active source (with metrics tracking enabled)
        cboe_most_active = get_cboe_most_active_source(storage=storage)
        metrics = cboe_most_active.fetch_most_active_metrics()

        # Store in options_market_metrics table (upsert)
        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO options_market_metrics (
                    as_of_date,
                    most_active_call_pct,
                    near_term_pct,
                    concentration_pct,
                    sector_weights,
                    source_timestamp
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    most_active_call_pct = EXCLUDED.most_active_call_pct,
                    near_term_pct = EXCLUDED.near_term_pct,
                    concentration_pct = EXCLUDED.concentration_pct,
                    sector_weights = EXCLUDED.sector_weights,
                    source_timestamp = EXCLUDED.source_timestamp
                """,
                (
                    metrics["as_of_date"],
                    metrics["most_active_call_pct"],
                    metrics["near_term_pct"],
                    metrics["concentration_pct"],
                    json.dumps(metrics["sector_weights"]),
                    metrics["source_timestamp"],
                ),
            )
            conn.commit()

        result = {
            "task_id": task_id,
            "as_of_date": metrics["as_of_date"],
            "metrics": {
                "call_pct": metrics["most_active_call_pct"],
                "near_term_pct": metrics["near_term_pct"],
                "concentration_pct": metrics["concentration_pct"],
                "sectors": len(metrics["sector_weights"]),
            },
            "success": True,
        }

        logger.info(
            "fetch_options_activity_completed",
            **result,
        )

        return result

    except Exception as e:
        logger.error(
            "fetch_options_activity_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "as_of_date": dt.date.today().isoformat(),
            "error": str(e),
            "success": False,
        }


def _fetch_spy_data(
    storage: PortfolioStorage, start_date: dt.date, end_date: dt.date
) -> dict[dt.date, float]:
    """Fetch SPY OHLCV data from day_bars table.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        Dict mapping date to closing price
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE ticker = 'SPY'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            (start_date, end_date),
        )
        spy_data = result.fetchall()

    return {row[0]: row[1] for row in spy_data}


def _fetch_market_indicators(
    storage: PortfolioStorage, start_date: dt.date, end_date: dt.date
) -> tuple[dict[dt.date, float], dict[dt.date, float], float, float]:
    """Fetch VIX, HY spread, and fallback estimates.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        Tuple of (vix_dict, hy_spread_dict, vix_estimate, hy_spread_fallback)
    """
    # Get latest VIX and HY_spread for fallback estimates
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT vix_close, hy_spread
            FROM fear_greed_inputs
            WHERE vix_close IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        latest = result.fetchone()
        vix_estimate = latest[0] if latest and latest[0] else 19.5
        hy_spread_fallback = latest[1] if latest and latest[1] else 3.13

    # Fetch VIX data from database if available
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE ticker = '^VIX'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            (start_date, end_date),
        )
        vix_dict = {row[0]: row[1] for row in result.fetchall()}

    # Fetch HY spread data from FRED
    fred_source = FREDSource()
    hy_spread_data = fred_source.fetch_series("HY_SPREAD", start_date, end_date)
    hy_spread_dict = dict(hy_spread_data)

    return vix_dict, hy_spread_dict, vix_estimate, hy_spread_fallback


def _compute_date_indicators(
    spy_close: float,
    prices_up_to_date: list[float],
    date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
    vix_estimate: float,
    hy_spread_fallback: float,
) -> tuple[float, float, float, float] | None:
    """Compute all indicators for a single date.

    Returns tuple of (sma_200, rsi_14, vix_close, hy_spread) or None if calculation fails.
    """
    sma_200 = _calculate_sma(prices_up_to_date, 200)
    rsi_14 = _calculate_rsi(prices_up_to_date, 14)

    if sma_200 is None or rsi_14 is None:
        logger.warning("indicator_calculation_failed", date=str(date))
        return None

    vix_close = vix_data.get(date, vix_estimate)
    hy_spread = hy_spread_dict.get(date, hy_spread_fallback)

    return sma_200, rsi_14, vix_close, hy_spread


def _upsert_inputs_record(
    storage: PortfolioStorage,
    date: dt.date,
    spy_close: float,
    sma_200: float,
    rsi_14: float,
    vix_close: float,
    hy_spread: float,
    breadth_pct: float | None,
) -> None:
    """Upsert a single fear_greed_inputs record to database."""
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO fear_greed_inputs
            (as_of_date, spy_close, spy_sma_200, rsi_14, vix_close, hy_spread, breadth_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (as_of_date)
            DO UPDATE SET
                spy_close = EXCLUDED.spy_close,
                spy_sma_200 = EXCLUDED.spy_sma_200,
                rsi_14 = EXCLUDED.rsi_14,
                vix_close = EXCLUDED.vix_close,
                hy_spread = EXCLUDED.hy_spread,
                breadth_pct = EXCLUDED.breadth_pct
            """,
            (date, spy_close, sma_200, rsi_14, vix_close, hy_spread, breadth_pct),
        )
        conn.commit()


def _calculate_and_upsert_inputs(
    storage: PortfolioStorage,
    spy_dict: dict[dt.date, float],
    dates: list[dt.date],
    start_date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
    vix_estimate: float,
    hy_spread_fallback: float,
) -> int:
    """Calculate indicators for each date and upsert to database.

    Args:
        storage: Storage instance
        spy_dict: SPY prices by date
        dates: Sorted list of all dates with SPY data
        start_date: Start date for processing
        vix_data: VIX prices by date
        hy_spread_dict: HY spread values by date
        vix_estimate: Fallback VIX estimate
        hy_spread_fallback: Fallback HY spread value

    Returns:
        Number of successful updates
    """
    updates_count = 0
    for i, date in enumerate(dates):
        if date < start_date:
            continue

        prices_up_to_date = [spy_dict[d] for d in dates[: i + 1]]

        if len(prices_up_to_date) < 200:
            logger.warning(
                "insufficient_data_for_indicators",
                date=str(date),
                data_points=len(prices_up_to_date),
            )
            continue

        spy_close = spy_dict[date]
        indicators = _compute_date_indicators(
            spy_close,
            prices_up_to_date,
            date,
            vix_data,
            hy_spread_dict,
            vix_estimate,
            hy_spread_fallback,
        )

        if indicators is None:
            continue

        sma_200, rsi_14, vix_close, hy_spread = indicators
        breadth_pct = _calculate_market_breadth(storage, date)

        _upsert_inputs_record(
            storage, date, spy_close, sma_200, rsi_14, vix_close, hy_spread, breadth_pct
        )
        updates_count += 1

    return updates_count


def _validate_and_fetch_data(
    storage: PortfolioStorage, end_date: dt.date, start_date: dt.date, data_start: dt.date
) -> (
    tuple[
        dict[dt.date, float],
        list[dt.date],
        dict[dt.date, float],
        dict[dt.date, float],
        float,
        float,
    ]
    | None
):
    """Validate SPY data and fetch all required market indicators.

    Returns (spy_dict, dates, vix_data, hy_spread_dict, vix_est, hy_fallback) or None on error.
    """
    spy_dict = _fetch_spy_data(storage, data_start, end_date)

    if len(spy_dict) < 200:
        return None

    dates = sorted(spy_dict.keys())
    vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback = _fetch_market_indicators(
        storage, start_date, end_date
    )

    return spy_dict, dates, vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback


def _process_and_return_results(
    task_id: str,
    storage: PortfolioStorage,
    spy_dict: dict[dt.date, float],
    dates: list[dt.date],
    start_date: dt.date,
    end_date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
    vix_estimate: float,
    hy_spread_fallback: float,
) -> dict[str, Any]:
    """Process market data and return task results."""
    logger.info(
        "populated_market_indicators",
        task_id=task_id,
        vix_count=len(vix_data),
        hy_spread_count=len(hy_spread_dict),
    )

    updates_count = _calculate_and_upsert_inputs(
        storage,
        spy_dict,
        dates,
        start_date,
        vix_data,
        hy_spread_dict,
        vix_estimate,
        hy_spread_fallback,
    )

    logger.info(
        "populate_fear_greed_inputs_completed",
        task_id=task_id,
        updates_count=updates_count,
    )

    calculate_fear_greed.apply_async()

    return {
        "task_id": task_id,
        "updates_count": updates_count,
        "date_range": f"{start_date} to {end_date}",
        "success": True,
    }


@celery_app.task(name="populate_fear_greed_inputs", bind=True)  # type: ignore[misc]
def populate_fear_greed_inputs(self: Task, days: int = 7) -> dict[str, Any]:
    """Populate fear_greed_inputs table with latest market data.

    This task replaces the manual script update_fear_greed_inputs.py.
    Runs daily to ensure fear_greed_inputs is up-to-date.

    Process:
    1. Fetch SPY OHLCV from day_bars (last N days + 200 for SMA_200)
    2. Calculate SMA_200 and RSI_14 from SPY data
    3. Fetch VIX from day_bars (if available)
    4. Use estimates for missing VIX/HY_spread data
    5. Upsert fear_greed_inputs for each date
    6. Trigger calculate_fear_greed task

    Args:
        days: Number of days to update (default 7)

    Returns:
        dict: Task result with update count and status
    """
    task_id = self.request.id
    logger.info("populate_fear_greed_inputs_started", task_id=task_id, days=days)

    try:
        storage = get_storage()
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=days)
        data_start = end_date - dt.timedelta(days=300)

        result = _validate_and_fetch_data(storage, end_date, start_date, data_start)

        if result is None:
            error_msg = "Insufficient SPY data: need >= 200 days"
            logger.error("populate_fear_greed_inputs_failed", task_id=task_id, error=error_msg)
            return {
                "task_id": task_id,
                "updates_count": 0,
                "error": error_msg,
                "success": False,
            }

        spy_dict, dates, vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback = result

        return _process_and_return_results(
            task_id,
            storage,
            spy_dict,
            dates,
            start_date,
            end_date,
            vix_data,
            hy_spread_dict,
            vix_estimate,
            hy_spread_fallback,
        )

    except Exception as e:
        logger.error(
            "populate_fear_greed_inputs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "updates_count": 0,
            "error": str(e),
            "success": False,
        }


def _calculate_sma(prices: list[float], period: int) -> float | None:
    """Calculate Simple Moving Average.

    Args:
        prices: List of closing prices (oldest first)
        period: SMA period

    Returns:
        SMA value or None if insufficient data
    """
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _calculate_rsi(prices: list[float], period: int = 14) -> float | None:
    """Calculate RSI indicator.

    Args:
        prices: List of closing prices (oldest first)
        period: RSI period (default 14)

    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None

    # Calculate price changes
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Separate gains and losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Calculate average gain/loss
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def _calculate_market_breadth(storage: PortfolioStorage, target_date: dt.date) -> float | None:
    """Calculate market breadth from 11 sector ETFs.

    Market breadth is a sentiment indicator that measures the percentage of
    sectors advancing vs declining. Higher breadth (more sectors up) typically
    indicates bullish market conditions.

    Args:
        storage: Storage instance with connection context manager
        target_date: Date to calculate breadth for

    Returns:
        Percentage (0-100) of sectors that closed higher than previous day,
        or None if insufficient data (requires at least 8/11 sectors).

    Example:
        >>> breadth = _calculate_market_breadth(storage, dt.date(2025, 11, 12))
        >>> breadth  # e.g., 63.64 (7 out of 11 sectors up)
    """
    sector_tickers = [
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

    with storage.connection() as conn:
        # Use subquery with window function to get current and previous close
        # We need to filter for the target_date specifically after computing LAG
        result = conn.execute(
            """
            WITH price_data AS (
                SELECT
                    ticker,
                    date,
                    close as current_close,
                    LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close
                FROM day_bars
                WHERE ticker = ANY(%s)
                  AND date <= %s
                  AND date >= %s - INTERVAL '10 days'
            )
            SELECT ticker, current_close, prev_close
            FROM price_data
            WHERE date = %s
            """,
            (sector_tickers, target_date, target_date, target_date),
        )
        rows = result.fetchall()

    if not rows:
        logger.warning(
            "market_breadth_no_data",
            target_date=str(target_date),
        )
        return None

    # Collect data for each ticker
    ticker_data: dict[str, tuple[float, float | None]] = {}
    for ticker, current_close, prev_close in rows:
        ticker_data[ticker] = (current_close, prev_close)

    # Count sectors with valid data (both current and previous close)
    sectors_up = 0
    sectors_with_data = 0

    for _ticker, (current_close, prev_close) in ticker_data.items():
        if prev_close is not None:
            sectors_with_data += 1
            if current_close > prev_close:
                sectors_up += 1

    # Require at least 8/11 sectors for valid calculation (72% coverage)
    min_required_sectors = 8
    if sectors_with_data < min_required_sectors:
        logger.warning(
            "market_breadth_insufficient_data",
            target_date=str(target_date),
            sectors_with_data=sectors_with_data,
            min_required=min_required_sectors,
        )
        return None

    # Calculate breadth percentage
    breadth_pct = (sectors_up / sectors_with_data) * 100

    logger.info(
        "market_breadth_calculated",
        target_date=str(target_date),
        sectors_up=sectors_up,
        sectors_total=sectors_with_data,
        breadth_pct=round(breadth_pct, 2),
    )

    return breadth_pct
