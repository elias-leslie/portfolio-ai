"""Walk-forward backtesting for strategy evolution."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.backtest.walk_forward import WalkForwardEngine

from .models import BacktestMetrics


async def run_walk_forward_validation(
    symbol: str,
    parameters: dict[str, Any],
    lookback_days: int = 365,
    training_days: int = 180,
    validation_days: int = 60,
) -> BacktestMetrics:
    """Run walk-forward validation for strategy parameters.

    Args:
        symbol: Stock symbol
        parameters: Strategy parameters dict
        lookback_days: Total lookback period (default 365 days)
        training_days: Training window size (default 180 days)
        validation_days: Validation window size (default 60 days)

    Returns:
        BacktestMetrics with aggregated results
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    # Create walk-forward engine
    engine = WalkForwardEngine(
        train_days=training_days,
        val_days=validation_days,
        test_days=validation_days,  # Use same size for test
        gap_days=10,
        step_days=60,
    )

    # Extract parameters
    min_confirmations = parameters.get("min_confirmations", 6)
    stop_loss_atr = parameters.get("stop_loss_atr_multiplier", 2.0)
    max_holding_days = parameters.get("max_holding_days", 60)

    # Run walk-forward
    result = engine.run_walk_forward(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        strategy_type="enhanced",
        min_confirmations=min_confirmations,
        stop_loss_atr_multiplier=float(stop_loss_atr),
        max_holding_days=max_holding_days,
    )

    # Return simplified metrics
    return BacktestMetrics(
        sharpe_ratio=result.mean_sharpe,
        win_rate=result.mean_win_rate,
        max_drawdown=result.max_drawdown_pct / 100.0,  # Convert to 0-1
        total_return=result.mean_return_pct,
        num_trades=result.total_trades,
    )
