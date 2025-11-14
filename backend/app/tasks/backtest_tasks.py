"""
Celery tasks for backtesting.

Async task execution for running backtests without blocking HTTP requests.

Tasks:
- run_backtest_task: Execute backtest replay and store results
"""

import logging
from datetime import date
from decimal import Decimal

from app.backtest import metrics, replay, storage, strategies
from app.celery_app import celery_app
from app.storage.connection import get_connection_manager

logger = logging.getLogger(__name__)


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

    storage_mgr = get_connection_manager()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Initialize strategy
        if strategy_name == "signal_classifier":
            strategy = strategies.SignalStrategy(
                min_signal_strength=min_signal_strength,
                max_holding_days=max_holding_days,
                stop_loss_atr_multiplier=Decimal("2.0"),
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

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

        # Calculate final metrics
        final_equity = (
            state.equity_curve[-1].equity if state.equity_curve else Decimal(str(initial_capital))
        )
        total_return_pct = metrics.calculate_total_return(
            Decimal(str(initial_capital)), final_equity
        )
        sharpe_ratio = metrics.calculate_sharpe_ratio(state.equity_curve)
        max_drawdown_pct = metrics.calculate_max_drawdown(state.equity_curve)
        win_rate = metrics.calculate_win_rate(state.trades)
        profit_factor = metrics.calculate_profit_factor(state.trades)
        num_trades = len(state.trades)

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
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            num_trades=num_trades,
            profit_factor=profit_factor,
        )

        logger.info(
            f"Backtest complete: {run_id} | Return: {total_return_pct:.2f}% | "
            f"Sharpe: {sharpe_ratio:.2f} | Trades: {num_trades} | Win Rate: {win_rate:.1f}%"
        )

        return {
            "run_id": run_id,
            "status": "completed",
            "final_equity": float(final_equity),
            "total_return_pct": float(total_return_pct),
            "sharpe_ratio": float(sharpe_ratio),
            "max_drawdown_pct": float(max_drawdown_pct),
            "win_rate": float(win_rate),
            "num_trades": num_trades,
            "profit_factor": float(profit_factor),
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
