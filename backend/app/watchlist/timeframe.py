"""Multi-timeframe alignment analysis for watchlist items."""

from __future__ import annotations


def calculate_timeframe_alignment(
    price: float,
    sma_20: float | None,
    sma_50: float | None,
    sma_200: float | None,
) -> tuple[bool, bool]:
    """Calculate short-term and long-term timeframe alignment.

    Short-term aligned: Price > SMA_20 > SMA_50
    Long-term aligned: SMA_50 > SMA_200

    Args:
        price: Current price
        sma_20: 20-day simple moving average
        sma_50: 50-day simple moving average
        sma_200: 200-day simple moving average

    Returns:
        Tuple of (short_aligned, long_aligned)
    """
    short_aligned = False
    long_aligned = False

    # Short-term alignment (Price > SMA_20 > SMA_50)
    if sma_20 and sma_50:
        short_aligned = price > sma_20 > sma_50

    # Long-term alignment (SMA_50 > SMA_200)
    if sma_50 and sma_200:
        long_aligned = sma_50 > sma_200

    return (short_aligned, long_aligned)


def calculate_volume_relative(
    current_volume: float,
    avg_volume_50d: float | None,
) -> float | None:
    """Calculate volume relative to 50-day average.

    Args:
        current_volume: Today's volume
        avg_volume_50d: 50-day average volume

    Returns:
        Ratio (e.g., 2.3 = 2.3x above average), or None if missing data
    """
    if not avg_volume_50d or avg_volume_50d <= 0:
        return None

    return current_volume / avg_volume_50d
