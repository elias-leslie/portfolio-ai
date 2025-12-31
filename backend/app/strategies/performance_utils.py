"""Performance variance calculation utilities.

Shared utilities for calculating strategy performance metrics
and classification across the API layer.
"""

from __future__ import annotations

from typing import Literal

# Performance variance thresholds
EXCEEDING_THRESHOLD = 0.9  # >= 90% of expected Sharpe
MEETING_THRESHOLD = 0.7  # >= 70% of expected Sharpe

PerformanceFlag = Literal["exceeding", "meeting", "underperforming", "no_data"]


def calculate_performance_status(
    expected_sharpe: float | None,
    live_sharpe: float | None,
    live_trades_count: int,
) -> tuple[float | None, PerformanceFlag]:
    """Calculate performance variance and status flag.

    Args:
        expected_sharpe: Expected Sharpe ratio from backtest
        live_sharpe: Actual live Sharpe ratio
        live_trades_count: Number of live trades executed

    Returns:
        Tuple of (variance, flag) where:
            - variance: live_sharpe / expected_sharpe ratio, or None
            - flag: Performance classification
    """
    if live_trades_count == 0:
        return None, "no_data"

    if expected_sharpe is None or expected_sharpe <= 0 or live_sharpe is None:
        return None, "no_data"

    variance = live_sharpe / expected_sharpe

    if variance >= EXCEEDING_THRESHOLD:
        flag: PerformanceFlag = "exceeding"
    elif variance >= MEETING_THRESHOLD:
        flag = "meeting"
    else:
        flag = "underperforming"

    return variance, flag
