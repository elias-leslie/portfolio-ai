"""Helper functions for scoring calculations."""

from __future__ import annotations

from datetime import datetime, timedelta


def is_stale(timestamp: datetime | None, ttl_minutes: int, now: datetime) -> bool:
    """Check if timestamp exceeds TTL threshold.

    Args:
        timestamp: Timestamp to check (None considered stale)
        ttl_minutes: Time-to-live threshold in minutes
        now: Current reference time

    Returns:
        True if stale, False otherwise
    """
    if timestamp is None:
        return True
    cutoff = now - timedelta(minutes=ttl_minutes)
    return timestamp < cutoff


def score_from_change_percent(change_pct: float) -> float:
    """Map price change percent (-20% to +20%) into 0-100 range.

    Args:
        change_pct: Price change percentage (e.g., 5.0 for 5%)

    Returns:
        Score in 0-100 range
    """
    clamped = max(-20.0, min(20.0, change_pct))
    return (clamped + 20.0) / 40.0 * 100.0


def score_from_rsi(rsi: float) -> float:
    """Reward balanced RSI; penalise overbought/oversold extremes.

    Args:
        rsi: RSI value (0-100)

    Returns:
        Score in 0-100 range (50 = optimal, extremes penalized)
    """
    clamped = max(0.0, min(100.0, rsi))
    distance = abs(clamped - 50.0)
    # Distance 0 => score 100, distance 50 => score 0
    return max(0.0, 100.0 - (distance * 2.0))


def score_from_trend(
    price: float | None, sma_50: float | None, sma_200: float | None
) -> float | None:
    """Blend moving average crossover into a 0-100 score.

    Args:
        price: Current price
        sma_50: 50-day simple moving average
        sma_200: 200-day simple moving average

    Returns:
        Score in 0-100 range, or None if data unavailable
    """
    if price is None or sma_50 is None or sma_200 is None:
        return None

    # Positive spread if price > averages; clamp to [-20%, 20%]
    spread_short = (price - sma_50) / sma_50 if sma_50 else 0.0
    spread_long = (price - sma_200) / sma_200 if sma_200 else 0.0

    composite = (spread_short * 0.6) + (spread_long * 0.4)
    composite = max(-0.2, min(0.2, composite))

    return (composite + 0.2) / 0.4 * 100.0
