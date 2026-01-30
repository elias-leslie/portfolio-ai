"""Walk-forward validation for strategy optimization.

This module provides validation window creation and parameter testing.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.backtest.replay import replay_backtest
from app.backtest.strategies import SignalStrategy
from app.storage import PortfolioStorage

from .models import StrategyParameters
from .optimizer_metrics import BacktestMetrics, calculate_metrics_from_state

logger = logging.getLogger(__name__)


@dataclass
class ValidationWindow:
    """Walk-forward validation window dates."""

    train_start: date
    train_end: date
    val_start: date
    val_end: date


def create_walk_forward_windows(start_date: date, end_date: date) -> list[ValidationWindow]:
    """Create walk-forward validation windows.

    Args:
        start_date: Start of historical period
        end_date: End of historical period (today)

    Returns:
        List of ValidationWindow objects
    """
    windows = []
    train_days = 180  # 6 months training
    val_days = 60  # 2 months validation
    step_days = 60  # Roll forward 2 months

    current_date = start_date
    while current_date + timedelta(days=train_days + val_days) <= end_date:
        train_start = current_date
        train_end = current_date + timedelta(days=train_days)
        val_start = train_end + timedelta(days=1)
        val_end = val_start + timedelta(days=val_days)

        windows.append(
            ValidationWindow(
                train_start=train_start,
                train_end=train_end,
                val_start=val_start,
                val_end=val_end,
            )
        )

        current_date += timedelta(days=step_days)

    return windows


async def test_params_across_windows(
    storage: PortfolioStorage,
    symbol: str,
    params: StrategyParameters,
    windows: list[ValidationWindow],
    fundamental_data: dict[str, object],
) -> list[BacktestMetrics]:
    """Test parameter configuration across validation windows.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        params: Strategy parameters to test
        windows: Validation windows
        fundamental_data: Fundamental data for signal classifier

    Returns:
        List of BacktestMetrics (one per validation window)
    """
    results = []

    for window in windows:
        # Run backtest on validation window with real fundamental data
        strategy = SignalStrategy(
            min_signal_strength=params.min_confirmations,
            max_holding_days=params.max_holding_days,
            stop_loss_atr_multiplier=params.stop_loss_atr_multiplier,
            fundamental_data=fundamental_data,
        )

        # Run backtest for this validation window
        run_id = "optimizer-" + str(uuid.uuid4())[:8]
        backtest_result = replay_backtest(
            storage=storage,  # PortfolioStorage instance
            run_id=run_id,
            symbol=symbol,
            start_date=window.val_start,
            end_date=window.val_end,
            strategy=strategy,
            initial_capital=Decimal("100000.00"),
        )

        # Extract metrics from backtest state
        metrics = calculate_metrics_from_state(backtest_result)

        results.append(metrics)

    return results
