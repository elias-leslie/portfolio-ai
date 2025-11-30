"""
Backtest comparison module.

Provides functionality for comparing multiple backtest runs:
- Normalized equity curves (starting at 100%)
- Side-by-side metrics comparison
- Correlation analysis between strategies
- Performance ranking

Phase B: Strategy Comparison Mode (VISION.md B2)
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np

from app.backtest.models import BacktestEquity, BacktestRun


@dataclass
class NormalizedEquityPoint:
    """Equity point normalized to 100% starting value."""

    date: date
    cumulative_return_pct: Decimal  # Starting from 0%


@dataclass
class RunMetrics:
    """Metrics summary for a single backtest run."""

    run_id: str
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: Decimal | None
    sharpe_ratio: Decimal | None
    max_drawdown_pct: Decimal | None
    win_rate: Decimal | None
    num_trades: int | None
    profit_factor: Decimal | None
    # Ranking within comparison group (1 = best)
    return_rank: int | None = None
    sharpe_rank: int | None = None
    drawdown_rank: int | None = None


@dataclass
class ComparisonResult:
    """Complete comparison result for multiple backtest runs."""

    # Normalized equity curves for each run
    equity_curves: dict[str, list[NormalizedEquityPoint]]
    # Metrics with rankings for each run
    metrics: list[RunMetrics]
    # Correlation matrix (optional - if overlapping dates exist)
    correlation_matrix: dict[str, dict[str, float]] | None = None


def normalize_equity_curve(
    equity_curve: list[BacktestEquity],
) -> list[NormalizedEquityPoint]:
    """Normalize equity curve to start at 0% return.

    Converts absolute equity values to cumulative return percentages
    for fair comparison between runs with different initial capital.

    Args:
        equity_curve: List of equity points with absolute values

    Returns:
        List of normalized equity points with cumulative return %
    """
    if not equity_curve:
        return []

    initial_equity = float(equity_curve[0].equity)
    if initial_equity <= 0:
        initial_equity = 1.0  # Prevent division by zero

    return [
        NormalizedEquityPoint(
            date=point.date,
            cumulative_return_pct=Decimal(
                str(round(((float(point.equity) - initial_equity) / initial_equity) * 100, 4))
            ),
        )
        for point in equity_curve
    ]


def calculate_correlation(
    curves: dict[str, list[NormalizedEquityPoint]],
) -> dict[str, dict[str, float]] | None:
    """Calculate correlation matrix between normalized equity curves.

    Only calculates correlation for overlapping date ranges.

    Args:
        curves: Dict mapping run_id to normalized equity curves

    Returns:
        Correlation matrix as nested dict, or None if insufficient data
    """
    if len(curves) < 2:
        return None

    run_ids = list(curves.keys())

    # Build date-aligned returns for each run
    date_returns: dict[str, dict[date, float]] = {}
    all_dates: set[date] = set()

    for run_id, points in curves.items():
        if len(points) < 2:
            continue
        date_returns[run_id] = {}
        prev_return = 0.0
        for point in points:
            current_return = float(point.cumulative_return_pct)
            # Daily return = change in cumulative return
            daily_return = current_return - prev_return
            date_returns[run_id][point.date] = daily_return
            prev_return = current_return
            all_dates.add(point.date)

    if len(date_returns) < 2:
        return None

    # Find common dates
    common_dates = sorted(all_dates)
    if len(common_dates) < 10:  # Need at least 10 overlapping days
        return None

    # Build aligned arrays
    aligned_returns: dict[str, list[float]] = {run_id: [] for run_id in date_returns}
    for d in common_dates:
        # Only include date if all runs have data for it
        if all(d in date_returns[run_id] for run_id in date_returns):
            for run_id in date_returns:
                aligned_returns[run_id].append(date_returns[run_id][d])

    if len(aligned_returns[run_ids[0]]) < 10:
        return None

    # Calculate correlation matrix
    correlation: dict[str, dict[str, float]] = {}
    for run_id1 in run_ids:
        if run_id1 not in aligned_returns:
            continue
        correlation[run_id1] = {}
        arr1 = np.array(aligned_returns.get(run_id1, []))
        for run_id2 in run_ids:
            if run_id2 not in aligned_returns:
                continue
            arr2 = np.array(aligned_returns.get(run_id2, []))
            if len(arr1) > 0 and len(arr2) > 0 and len(arr1) == len(arr2):
                # Handle case where std is 0
                std1, std2 = np.std(arr1), np.std(arr2)
                if std1 == 0 or std2 == 0:
                    corr = 1.0 if run_id1 == run_id2 else 0.0
                else:
                    corr = float(np.corrcoef(arr1, arr2)[0, 1])
                    if np.isnan(corr):
                        corr = 0.0
                correlation[run_id1][run_id2] = round(corr, 4)

    return correlation if correlation else None


def rank_metrics(metrics_list: list[RunMetrics]) -> list[RunMetrics]:
    """Calculate rankings for each metric across runs.

    Higher is better for: total_return, sharpe_ratio, win_rate
    Lower is better for: max_drawdown

    Args:
        metrics_list: List of run metrics to rank

    Returns:
        Same list with ranking fields populated
    """
    if not metrics_list:
        return metrics_list

    # Rank by total return (higher is better)
    returns = [(i, m.total_return_pct) for i, m in enumerate(metrics_list) if m.total_return_pct is not None]
    returns.sort(key=lambda x: float(x[1]), reverse=True)
    for rank, (idx, _) in enumerate(returns, 1):
        metrics_list[idx].return_rank = rank

    # Rank by Sharpe ratio (higher is better)
    sharpes = [(i, m.sharpe_ratio) for i, m in enumerate(metrics_list) if m.sharpe_ratio is not None]
    sharpes.sort(key=lambda x: float(x[1]), reverse=True)
    for rank, (idx, _) in enumerate(sharpes, 1):
        metrics_list[idx].sharpe_rank = rank

    # Rank by max drawdown (lower is better)
    drawdowns = [(i, m.max_drawdown_pct) for i, m in enumerate(metrics_list) if m.max_drawdown_pct is not None]
    drawdowns.sort(key=lambda x: float(x[1]))  # Lower drawdown is better
    for rank, (idx, _) in enumerate(drawdowns, 1):
        metrics_list[idx].drawdown_rank = rank

    return metrics_list


def create_run_metrics(run: BacktestRun) -> RunMetrics:
    """Create RunMetrics from BacktestRun.

    Args:
        run: Backtest run with results

    Returns:
        RunMetrics dataclass
    """
    return RunMetrics(
        run_id=run.id,
        symbol=run.symbol,
        strategy_name=run.strategy_name,
        start_date=run.start_date,
        end_date=run.end_date,
        total_return_pct=run.total_return_pct,
        sharpe_ratio=run.sharpe_ratio,
        max_drawdown_pct=run.max_drawdown_pct,
        win_rate=run.win_rate,
        num_trades=run.num_trades,
        profit_factor=run.profit_factor,
    )


def compare_backtests(
    runs: list[BacktestRun],
    equity_curves: dict[str, list[BacktestEquity]],
) -> ComparisonResult:
    """Compare multiple backtest runs.

    Args:
        runs: List of backtest runs to compare
        equity_curves: Dict mapping run_id to equity curve data

    Returns:
        ComparisonResult with normalized curves, metrics, and correlation
    """
    # Normalize equity curves
    normalized_curves: dict[str, list[NormalizedEquityPoint]] = {}
    for run_id, curve in equity_curves.items():
        normalized_curves[run_id] = normalize_equity_curve(curve)

    # Create metrics with rankings
    metrics_list = [create_run_metrics(run) for run in runs]
    metrics_list = rank_metrics(metrics_list)

    # Calculate correlation
    correlation = calculate_correlation(normalized_curves)

    return ComparisonResult(
        equity_curves=normalized_curves,
        metrics=metrics_list,
        correlation_matrix=correlation,
    )
