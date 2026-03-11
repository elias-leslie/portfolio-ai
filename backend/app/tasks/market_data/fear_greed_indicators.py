"""Fear & Greed indicator calculations.

Technical indicators for Fear & Greed Index:
- SMA (Simple Moving Average)
- RSI (Relative Strength Index)
- Market Breadth (sector ETF analysis)
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.constants import SECTOR_ETF_SYMBOLS
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


def calculate_sma(prices: list[float], period: int) -> float | None:
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


def calculate_rsi(prices: list[float], period: int = 14) -> float | None:
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


def calculate_market_breadth(storage: PortfolioStorage, target_date: dt.date) -> float | None:
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
        >>> breadth = calculate_market_breadth(storage, dt.date(2025, 11, 12))
        >>> breadth  # e.g., 63.64 (7 out of 11 sectors up)
    """
    # Use shared sector ETF symbols constant
    sector_symbols = SECTOR_ETF_SYMBOLS

    with storage.connection() as conn:
        # Use subquery with window function to get current and previous close
        # We need to filter for the target_date specifically after computing LAG
        # Note: sector_symbols is a list[str], so we pass it directly as first param
        params: list[str | int | float | bool | list[str] | None] = [
            sector_symbols,
            str(target_date),
            str(target_date),
            str(target_date),
        ]
        result = conn.execute(
            """
            WITH price_data AS (
                SELECT
                    symbol,
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
            params,
        )
        rows = result.fetchall()

    if not rows:
        logger.warning(
            "market_breadth_no_data",
            target_date=str(target_date),
        )
        return None

    # Collect data for each symbol
    symbol_data: dict[str, tuple[float, float | None]] = {}
    for row in rows:
        symbol = str(row[0]) if row[0] is not None else ""
        current_close = float(row[1]) if row[1] is not None else 0.0
        prev_close = float(row[2]) if row[2] is not None else None
        symbol_data[symbol] = (current_close, prev_close)

    # Count sectors with valid data (both current and previous close)
    sectors_up = 0
    sectors_with_data = 0

    for _symbol, (current_close, prev_close) in symbol_data.items():
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
