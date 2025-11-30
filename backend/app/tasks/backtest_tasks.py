"""
Celery tasks for backtesting.

Async task execution for running backtests without blocking HTTP requests.

Tasks:
- run_backtest_task: Execute backtest replay and store results
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest import metrics, replay, storage, strategies
from app.celery_app import celery_app
from app.storage.facade import get_storage

logger = logging.getLogger(__name__)


def _initialize_strategy(
    strategy_name: str, min_signal_strength: int, max_holding_days: int
) -> strategies.SignalStrategy:
    """Initialize backtest strategy from name and parameters.

    Args:
        strategy_name: Strategy identifier
        min_signal_strength: Minimum signal strength for entry (1-10)
        max_holding_days: Maximum holding period

    Returns:
        Initialized SignalStrategy instance

    Raises:
        ValueError: If strategy_name is unknown
    """
    if strategy_name == "signal_classifier":
        return strategies.SignalStrategy(
            min_signal_strength=min_signal_strength,
            max_holding_days=max_holding_days,
            stop_loss_atr_multiplier=Decimal("2.0"),
        )
    raise ValueError(f"Unknown strategy: {strategy_name}")


def _calculate_performance_metrics(
    state: replay.BacktestState, initial_capital: Decimal
) -> dict[str, Any]:
    """Calculate all performance metrics from backtest state.

    Args:
        state: BacktestState object containing trades and equity curve
        initial_capital: Starting capital amount

    Returns:
        Dict containing metrics:
        - final_equity: Final account equity
        - total_return_pct: Total return percentage
        - sharpe_ratio: Sharpe ratio
        - max_drawdown_pct: Maximum drawdown percentage
        - win_rate: Win rate (0.0-100.0)
        - profit_factor: Profit factor
        - num_trades: Number of trades executed
    """
    final_equity = state.equity_curve[-1].equity if state.equity_curve else initial_capital
    return {
        "final_equity": final_equity,
        "total_return_pct": metrics.calculate_total_return(initial_capital, final_equity),
        "sharpe_ratio": metrics.calculate_sharpe_ratio(state.equity_curve),
        "max_drawdown_pct": metrics.calculate_max_drawdown(state.equity_curve),
        "win_rate": metrics.calculate_win_rate(state.trades),
        "profit_factor": metrics.calculate_profit_factor(state.trades),
        "num_trades": len(state.trades),
    }


def _save_backtest_results(
    storage_mgr: Any,
    state: replay.BacktestState,
    metrics_dict: dict[str, Any],
    run_id: str,
) -> None:
    """Save trades, equity curve, and update backtest_run with final metrics.

    Args:
        storage_mgr: Storage connection manager
        state: BacktestState object with trades and equity curve
        metrics_dict: Performance metrics dict from _calculate_performance_metrics
        run_id: Backtest run ID
    """
    # Save trades to database
    for trade in state.trades:
        storage.save_backtest_trade(storage_mgr, trade)

    # Save equity curve to database
    for snapshot in state.equity_curve:
        storage.save_equity_snapshot(storage_mgr, snapshot)

    # Update backtest_run with final results
    storage.update_backtest_result(
        storage=storage_mgr,
        run_id=run_id,
        final_equity=metrics_dict["final_equity"],
        total_return_pct=metrics_dict["total_return_pct"],
        sharpe_ratio=metrics_dict["sharpe_ratio"],
        max_drawdown_pct=metrics_dict["max_drawdown_pct"],
        win_rate=metrics_dict["win_rate"],
        num_trades=metrics_dict["num_trades"],
        profit_factor=metrics_dict["profit_factor"],
    )


@celery_app.task(  # type: ignore[misc]
    bind=True,
    max_retries=0,  # No retries for backtests (user can re-run manually)
    time_limit=600,  # 10 minute timeout (prevent infinite loops)
)
def run_backtest_task(  # type: ignore[no-untyped-def]
    self,
    run_id: str,
    symbol: str,
    start_date: str,  # ISO format (YYYY-MM-DD)
    end_date: str,  # ISO format (YYYY-MM-DD)
    initial_capital: float,
    strategy_name: str,
    min_signal_strength: int = 7,
    max_holding_days: int = 60,
    position_sizing_method: str = "fixed_dollars",
    position_size_value: float = 10000.00,
) -> dict[str, str | int | float]:
    """Execute backtest and store results.

    This task:
    1. Runs the backtest replay loop
    2. Calculates performance metrics
    3. Saves trades and equity curve to database
    4. Updates backtest_run with final results

    Args:
        run_id: Backtest run ID (UUID)
        symbol: Stock symbol
        start_date: Backtest start date (ISO format)
        end_date: Backtest end date (ISO format)
        initial_capital: Starting capital
        strategy_name: Strategy identifier (only "signal_classifier" supported in Phase A)
        min_signal_strength: Minimum signal strength for entry (1-10)
        max_holding_days: Maximum holding period
        position_sizing_method: "fixed_dollars" or "fixed_shares"
        position_size_value: Position size (dollars or shares)

    Returns:
        Dict with final metrics

    Raises:
        Exception: If backtest fails (saved to error_message field)
    """
    logger.info(f"Starting backtest task: {run_id} | {symbol} | {start_date} to {end_date}")

    storage_mgr = get_storage()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Initialize strategy
        strategy = _initialize_strategy(strategy_name, min_signal_strength, max_holding_days)

        # Run backtest replay
        state = replay.replay_backtest(
            storage=storage_mgr,
            run_id=run_id,
            symbol=symbol,
            start_date=start,
            end_date=end,
            initial_capital=Decimal(str(initial_capital)),
            strategy=strategy,
            sizing_method=position_sizing_method,
            size_value=Decimal(str(position_size_value)),
        )

        # Calculate metrics
        metrics_dict = _calculate_performance_metrics(state, Decimal(str(initial_capital)))

        # Save results
        _save_backtest_results(storage_mgr, state, metrics_dict, run_id)

        logger.info(
            f"Backtest complete: {run_id} | Return: {metrics_dict['total_return_pct']:.2f}% | "
            f"Sharpe: {metrics_dict['sharpe_ratio']:.2f} | Trades: {metrics_dict['num_trades']} | "
            f"Win Rate: {metrics_dict['win_rate']:.1f}%"
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "final_equity": float(metrics_dict["final_equity"]),
            "total_return_pct": float(metrics_dict["total_return_pct"]),
            "sharpe_ratio": float(metrics_dict["sharpe_ratio"]),
            "max_drawdown_pct": float(metrics_dict["max_drawdown_pct"]),
            "win_rate": float(metrics_dict["win_rate"]),
            "num_trades": metrics_dict["num_trades"],
            "profit_factor": float(metrics_dict["profit_factor"]),
        }

    except Exception as e:
        logger.error(f"Backtest failed: {run_id} | Error: {e}", exc_info=True)

        # Update status to failed with error message
        storage.update_backtest_status(
            storage=storage_mgr,
            run_id=run_id,
            status="failed",
            error_message=str(e),
        )

        # Re-raise so Celery marks task as failed
        raise
