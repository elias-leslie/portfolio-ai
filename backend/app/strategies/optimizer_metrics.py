"""Performance metrics calculation for strategy optimization.

This module provides metrics calculation and aggregation for backtest results.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any

from app.backtest.replay import BacktestState


@dataclass
class BacktestMetrics:
    """Backtest performance metrics."""

    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_return: float
    num_trades: int
    profit_factor: float


def _calculate_trade_metrics(
    state: BacktestState,
) -> tuple[float, float]:
    """Calculate win rate and profit factor from trades.

    Args:
        state: Backtest state with trades

    Returns:
        Tuple of (win_rate, profit_factor)
    """
    num_trades = len(state.trades)
    wins = [t for t in state.trades if t.pnl and t.pnl > 0]
    losses = [t for t in state.trades if t.pnl and t.pnl < 0]

    win_rate = len(wins) / num_trades if num_trades > 0 else 0.0

    total_wins = sum(float(t.pnl) for t in wins if t.pnl is not None) if wins else 0.0
    total_losses = abs(sum(float(t.pnl) for t in losses if t.pnl is not None)) if losses else 0.0
    profit_factor = (
        total_wins / total_losses if total_losses > 0 else (2.0 if total_wins > 0 else 0.0)
    )

    return win_rate, profit_factor


def _calculate_sharpe_ratio(equities: list[float]) -> float:
    """Calculate annualized Sharpe ratio from equity series.

    Args:
        equities: List of equity values

    Returns:
        Annualized Sharpe ratio, or 0.0 if not calculable
    """
    if len(equities) <= 1:
        return 0.0

    daily_returns = [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] > 0
    ]

    if not daily_returns:
        return 0.0

    mean_return = statistics.mean(daily_returns)
    std_return = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0.0
    # Annualize: sqrt(252) * daily Sharpe
    return (mean_return / std_return * (252**0.5)) if std_return > 0 else 0.0


def _calculate_equity_metrics(
    state: BacktestState,
) -> tuple[float, float, float]:
    """Calculate return, drawdown, and Sharpe from equity curve.

    Args:
        state: Backtest state with equity curve

    Returns:
        Tuple of (total_return, max_drawdown, sharpe_ratio)
    """
    if not state.equity_curve:
        return 0.0, 0.0, 0.0

    equities = [float(e.equity) for e in state.equity_curve]
    initial_equity = equities[0] if equities else 1.0
    final_equity = equities[-1] if equities else initial_equity

    total_return = (
        (final_equity - initial_equity) / initial_equity if initial_equity > 0 else 0.0
    )
    max_drawdown = max(float(e.drawdown_pct) for e in state.equity_curve)
    sharpe_ratio = _calculate_sharpe_ratio(equities)

    return total_return, max_drawdown, sharpe_ratio


def calculate_metrics_from_state(state: BacktestState) -> BacktestMetrics:
    """Calculate performance metrics from backtest state.

    Calculates real metrics from:
    - state.trades (for win rate, profit factor)
    - state.equity_curve (for sharpe ratio, drawdown, returns)

    Args:
        state: Backtest state with trades and equity curve

    Returns:
        BacktestMetrics with performance statistics
    """
    num_trades = len(state.trades)

    # Default metrics for no trades
    if num_trades == 0:
        return BacktestMetrics(
            sharpe_ratio=0.0,
            win_rate=0.0,
            max_drawdown=0.0,
            total_return=0.0,
            num_trades=0,
            profit_factor=0.0,
        )

    win_rate, profit_factor = _calculate_trade_metrics(state)
    total_return, max_drawdown, sharpe_ratio = _calculate_equity_metrics(state)

    return BacktestMetrics(
        sharpe_ratio=sharpe_ratio,
        win_rate=win_rate,
        max_drawdown=max_drawdown,
        total_return=total_return,
        num_trades=num_trades,
        profit_factor=profit_factor,
    )


def aggregate_window_metrics(window_results: list[BacktestMetrics]) -> dict[str, float]:
    """Aggregate metrics across validation windows.

    Args:
        window_results: Backtest metrics from each window

    Returns:
        Dict with aggregated metrics
    """
    if not window_results:
        return {
            "avg_sharpe": 0.0,
            "max_drawdown": 1.0,
            "avg_win_rate": 0.0,
            "avg_return": 0.0,
            "total_trades": 0,
        }

    return {
        "avg_sharpe": sum(r.sharpe_ratio for r in window_results) / len(window_results),
        "max_drawdown": max(r.max_drawdown for r in window_results),
        "avg_win_rate": sum(r.win_rate for r in window_results) / len(window_results),
        "avg_return": sum(r.total_return for r in window_results) / len(window_results),
        "total_trades": sum(r.num_trades for r in window_results),
    }


def _find_viable_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find viable strategy results using progressive filter relaxation.

    Args:
        results: List of result dicts with params and metrics

    Returns:
        List of viable results (may be all results as last resort)
    """
    filters = [
        (1.0, 0.25),
        (0.7, 0.35),
        (0.0, 0.50),
    ]
    for min_sharpe, max_dd in filters:
        viable = [
            r
            for r in results
            if r["metrics"]["avg_sharpe"] > min_sharpe
            and r["metrics"]["max_drawdown"] < max_dd
        ]
        if viable:
            return viable

    # Last resort: accept all results
    return results


def select_best_metrics(
    results: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, float]]]:
    """Select best parameter configuration from results.

    Args:
        results: List of result dicts with params and metrics

    Returns:
        Tuple of (best result dict, optimization metrics list)

    Raises:
        ValueError: If no viable strategies found
    """
    if not results:
        raise ValueError("No viable strategies found (all failed Sharpe or drawdown filters)")

    viable = _find_viable_results(results)

    if not viable:
        raise ValueError("No viable strategies found (all failed Sharpe or drawdown filters)")

    # Rank by average Sharpe ratio
    best = max(viable, key=lambda x: x["metrics"]["avg_sharpe"])

    # Convert window results to dicts for storage
    optimization_metrics = [
        {
            "sharpe_ratio": m.sharpe_ratio,
            "win_rate": m.win_rate,
            "max_drawdown": m.max_drawdown,
            "total_return": m.total_return,
            "num_trades": m.num_trades,
        }
        for m in best["window_results"]
    ]

    return best, optimization_metrics
