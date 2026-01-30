"""Backtest executor."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.backtest.storage import create_backtest_run, get_backtest_run, update_backtest_status
from app.logging_config import get_logger

logger = get_logger(__name__)


def execute_run_backtest(
    storage: PortfolioStorage,
    agent_run_id: str,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 100000.0,
    strategy_name: str = "signal_classifier",
    min_signal_strength: int = 7,
    max_holding_days: int = 60,
    position_sizing_method: str = "fixed_dollars",
    position_size_value: float = 10000.0,
) -> dict[str, object]:
    """Execute run_backtest tool for strategy validation.

    Runs backtest synchronously and waits for completion (agents need results
    to make decisions). Uses Celery task but blocks until done.

    Args:
        storage: PortfolioStorage instance
        agent_run_id: ID of the agent run
        symbol: Stock symbol
        start_date: Backtest start date (ISO format: YYYY-MM-DD)
        end_date: Backtest end date (ISO format: YYYY-MM-DD)
        initial_capital: Starting capital (default: 100000.0)
        strategy_name: Strategy to use (default: 'signal_classifier')
        min_signal_strength: Minimum signal strength (1-10, default: 7)
        max_holding_days: Maximum holding period (default: 60)
        position_sizing_method: 'fixed_dollars' or 'fixed_shares' (default: 'fixed_dollars')
        position_size_value: Position size in dollars or shares (default: 10000.0)

    Returns:
        Result dictionary with backtest metrics or error
    """
    symbol = symbol.upper()

    # Validate date format and parse
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        if end < start:
            return {
                "status": "error",
                "error": f"end_date ({end_date}) must be >= start_date ({start_date})",
            }
    except ValueError as e:
        return {
            "status": "error",
            "error": f"Invalid date format (use YYYY-MM-DD): {e}",
        }

    try:
        # Create backtest run record
        run_id = create_backtest_run(
            storage=storage,
            strategy_name=strategy_name,
            symbol=symbol,
            start_date=start,
            end_date=end,
            initial_capital=Decimal(str(initial_capital)),
        )

        logger.info(
            f"Agent {agent_run_id} started backtest {run_id}: {symbol} "
            f"({start_date} to {end_date})"
        )

        # Update status to running
        update_backtest_status(storage, run_id, "running")

        # Launch Celery task (lazy import to avoid circular dependency)
        from app.tasks.backtest_tasks import run_backtest_task

        run_backtest_task.delay(
            run_id=run_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            strategy_name=strategy_name,
            min_signal_strength=min_signal_strength,
            max_holding_days=max_holding_days,
            position_sizing_method=position_sizing_method,
            position_size_value=position_size_value,
        )

        # Wait for task completion (synchronous for agent decision-making)
        # Poll database for completion (max 5 minutes)
        max_wait_seconds = 300
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Check backtest status
            run = get_backtest_run(storage, run_id)

            if not run:
                return {
                    "status": "error",
                    "error": f"Backtest run {run_id} not found",
                }

            if run.status == "completed":
                logger.info(
                    f"Backtest {run_id} completed: "
                    f"Sharpe {run.sharpe_ratio:.2f}, Win Rate {run.win_rate:.1f}%, "
                    f"Return {run.total_return_pct:.2f}%, Drawdown {run.max_drawdown_pct:.2f}%"
                )

                return {
                    "status": "completed",
                    "backtest_run_id": run_id,
                    "symbol": symbol,
                    "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else 0.0,
                    "win_rate": float(run.win_rate) if run.win_rate else 0.0,
                    "max_drawdown_pct": (
                        float(run.max_drawdown_pct) if run.max_drawdown_pct else 0.0
                    ),
                    "total_return_pct": (
                        float(run.total_return_pct) if run.total_return_pct else 0.0
                    ),
                    "num_trades": run.num_trades if run.num_trades else 0,
                    "message": (
                        f"Backtest complete: Sharpe {run.sharpe_ratio:.2f}, "
                        f"Win Rate {run.win_rate:.1f}%, Return {run.total_return_pct:.2f}%"
                    ),
                }

            if run.status == "failed":
                error_msg = run.error_message or "Unknown error"
                logger.error(f"Backtest {run_id} failed: {error_msg}")
                return {
                    "status": "error",
                    "backtest_run_id": run_id,
                    "symbol": symbol,
                    "error": f"Backtest failed: {error_msg}",
                }

        # Timeout
        logger.warning(f"Backtest {run_id} timed out after {max_wait_seconds}s")
        return {
            "status": "timeout",
            "backtest_run_id": run_id,
            "symbol": symbol,
            "error": f"Backtest timed out after {max_wait_seconds}s",
        }

    except Exception as e:
        logger.error(f"Failed to execute backtest for {symbol}: {e}")
        return {
            "status": "error",
            "symbol": symbol,
            "error": str(e),
        }


__all__ = ["execute_run_backtest"]
