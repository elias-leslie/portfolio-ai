"""Fear & Greed indicator pipeline tasks.

Populates fear_greed_inputs table with market data for Fear & Greed Index calculation:
- SPY price data (SMA_200, RSI_14)
- VIX volatility index
- High-Yield spread from FRED
- Market breadth from sector ETFs
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.fred import FREDSource
from app.storage import get_storage
from app.tasks.indicators import calculate_fear_greed
from app.tasks.types import FearGreedPipelineResultDict

if TYPE_CHECKING:
    from celery import Task

    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


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
            WHERE symbol = 'SPY'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            [str(start_date), str(end_date)],
        )
        spy_data = result.fetchall()

    spy_dict: dict[dt.date, float] = {}
    for row in spy_data:
        date_value = row[0]
        close_value = row[1]
        if isinstance(date_value, dt.date) and close_value is not None:
            spy_dict[date_value] = float(close_value)

    return spy_dict


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
        vix_estimate = float(latest[0]) if latest and latest[0] is not None else 19.5
        hy_spread_fallback = float(latest[1]) if latest and latest[1] is not None else 3.13

    # Fetch VIX data from database if available
    vix_dict: dict[dt.date, float] = {}
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE symbol = '^VIX'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            [str(start_date), str(end_date)],
        )
        for row in result.fetchall():
            date_value = row[0]
            close_value = row[1]
            if isinstance(date_value, dt.date) and close_value is not None:
                vix_dict[date_value] = float(close_value)

    # Fetch HY spread data from FRED
    fred_source = FREDSource()
    hy_spread_data = fred_source.fetch_series("HY_SPREAD", start_date, end_date)
    hy_spread_dict = dict(hy_spread_data)

    return vix_dict, hy_spread_dict, vix_estimate, hy_spread_fallback


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
        # Note: sector_tickers is a list[str], so we pass it directly as first param
        params: list[str | int | float | bool | list[str] | None] = [
            sector_tickers,
            str(target_date),
            str(target_date),
            str(target_date),
        ]
        result = conn.execute(
            """
            WITH price_data AS (
                SELECT
                    ticker,
                    date,
                    close as current_close,
                    LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close
                FROM day_bars
                WHERE symbol = ANY(%s)
                  AND date <= %s::date
                  AND date >= %s::date - INTERVAL '10 days'
            )
            SELECT symbol, current_close, prev_close
            FROM price_data
            WHERE date = %s::date
            """,
            params,  # type: ignore[arg-type]
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
    for row in rows:
        ticker = str(row[0]) if row[0] is not None else ""
        current_close = float(row[1]) if row[1] is not None else 0.0
        prev_close = float(row[2]) if row[2] is not None else None
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
            [str(date), spy_close, sma_200, rsi_14, vix_close, hy_spread, breadth_pct],
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
) -> FearGreedPipelineResultDict:
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


@celery_app.task(
    bind=True,
    name="populate_fear_greed_inputs",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def populate_fear_greed_inputs(self: Task, days: int = 7) -> FearGreedPipelineResultDict:
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
        FearGreedPipelineResultDict: Task result with update count and status
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
