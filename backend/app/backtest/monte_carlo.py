"""
Monte Carlo simulation for backtest stress testing.

Implements bootstrap resampling of trade returns to estimate:
- Distribution of possible outcomes
- Confidence intervals for returns
- Value at Risk (VaR) metrics
- Probability of loss

Phase B: Monte Carlo Simulation (VISION.md B4)
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import numpy.typing as npt

from app.backtest.models import BacktestTrade

# Type alias for numpy arrays
NDArray = npt.NDArray[Any]


@dataclass
class MonteCarloStatistics:
    """Statistics from Monte Carlo simulation."""

    # Number of simulations run
    num_simulations: int

    # Percentile returns
    percentile_5: float  # Worst case (5th percentile)
    percentile_25: float  # Lower quartile
    percentile_50: float  # Median
    percentile_75: float  # Upper quartile
    percentile_95: float  # Best case (95th percentile)

    # Risk metrics
    probability_of_loss: float  # % of simulations with negative return
    value_at_risk_95: float  # VaR at 95% confidence
    expected_shortfall: float  # Average loss in worst 5% of cases

    # Distribution stats
    mean_return: float
    std_dev: float
    skewness: float
    kurtosis: float

    # Original backtest return for comparison
    original_return: float


@dataclass
class SimulationResult:
    """Complete Monte Carlo simulation result."""

    statistics: MonteCarloStatistics
    # Distribution data for histogram (binned)
    histogram_data: list[dict[str, float]]  # [{bin_start, bin_end, frequency}, ...]
    # Equity curve bands (5th, 50th, 95th percentile at each step)
    equity_bands: list[dict[str, float]]  # [{step, p5, p50, p95}, ...]
    # Timestamp
    created_at: datetime


def extract_trade_returns(trades: list[BacktestTrade]) -> NDArray:
    """Extract percentage returns from trades.

    Args:
        trades: List of backtest trades

    Returns:
        Array of trade returns as percentages
    """
    returns = []
    for trade in trades:
        if trade.pnl_pct is not None:
            returns.append(float(trade.pnl_pct))
    return np.array(returns)


def bootstrap_resample(
    trade_returns: NDArray,
    num_simulations: int = 1000,
    seed: int | None = None,
) -> NDArray:
    """Generate bootstrap resampled trade sequences.

    Each simulation resamples trades with replacement and calculates
    the total return assuming the same number of trades.

    Args:
        trade_returns: Original trade returns (percentages)
        num_simulations: Number of bootstrap samples to generate
        seed: Random seed for reproducibility

    Returns:
        Array of final returns for each simulation (shape: num_simulations,)
    """
    if len(trade_returns) == 0:
        return np.zeros(num_simulations)

    rng = np.random.default_rng(seed)
    n_trades = len(trade_returns)

    # For each simulation, resample trades and calculate cumulative return
    final_returns = np.zeros(num_simulations)

    for i in range(num_simulations):
        # Resample trades with replacement
        resampled = rng.choice(trade_returns, size=n_trades, replace=True)

        # Calculate cumulative return: (1 + r1/100) * (1 + r2/100) * ... - 1
        cumulative = np.prod(1 + resampled / 100) - 1
        final_returns[i] = cumulative * 100  # Convert back to percentage

    return final_returns


def generate_equity_paths(
    trade_returns: NDArray,
    num_simulations: int = 1000,
    seed: int | None = None,
) -> NDArray:
    """Generate full equity curve paths for each simulation.

    Used to calculate confidence bands at each trade step.

    Args:
        trade_returns: Original trade returns (percentages)
        num_simulations: Number of paths to generate
        seed: Random seed for reproducibility

    Returns:
        Array of equity paths (shape: num_simulations x (n_trades + 1))
    """
    if len(trade_returns) == 0:
        return np.ones((num_simulations, 1)) * 100  # Start at 100

    rng = np.random.default_rng(seed)
    n_trades = len(trade_returns)

    # Initialize paths starting at 100 (normalized)
    paths = np.ones((num_simulations, n_trades + 1)) * 100

    for i in range(num_simulations):
        # Resample trades with replacement
        resampled = rng.choice(trade_returns, size=n_trades, replace=True)

        # Calculate cumulative equity at each step
        for j, ret in enumerate(resampled):
            paths[i, j + 1] = paths[i, j] * (1 + ret / 100)

    return paths


def calculate_statistics(
    simulation_returns: NDArray,
    original_return: float,
) -> MonteCarloStatistics:
    """Calculate comprehensive statistics from simulation results.

    Args:
        simulation_returns: Array of final returns from simulations
        original_return: The actual backtest return for comparison

    Returns:
        MonteCarloStatistics with all calculated metrics
    """
    n = len(simulation_returns)

    # Percentiles
    percentile_5 = float(np.percentile(simulation_returns, 5))
    percentile_25 = float(np.percentile(simulation_returns, 25))
    percentile_50 = float(np.percentile(simulation_returns, 50))
    percentile_75 = float(np.percentile(simulation_returns, 75))
    percentile_95 = float(np.percentile(simulation_returns, 95))

    # Risk metrics
    probability_of_loss = float(np.sum(simulation_returns < 0) / n * 100)
    value_at_risk_95 = float(np.percentile(simulation_returns, 5))  # VaR = loss at 5th percentile

    # Expected Shortfall (CVaR) - average of worst 5%
    worst_5_pct = simulation_returns[simulation_returns <= np.percentile(simulation_returns, 5)]
    expected_shortfall = float(np.mean(worst_5_pct)) if len(worst_5_pct) > 0 else 0.0

    # Distribution stats
    mean_return = float(np.mean(simulation_returns))
    std_dev = float(np.std(simulation_returns))

    # Skewness and kurtosis (using scipy-style formulas)
    centered = simulation_returns - mean_return
    if std_dev > 0:
        skewness = float(np.mean((centered / std_dev) ** 3))
        kurtosis = float(np.mean((centered / std_dev) ** 4) - 3)  # Excess kurtosis
    else:
        skewness = 0.0
        kurtosis = 0.0

    return MonteCarloStatistics(
        num_simulations=n,
        percentile_5=round(percentile_5, 2),
        percentile_25=round(percentile_25, 2),
        percentile_50=round(percentile_50, 2),
        percentile_75=round(percentile_75, 2),
        percentile_95=round(percentile_95, 2),
        probability_of_loss=round(probability_of_loss, 2),
        value_at_risk_95=round(value_at_risk_95, 2),
        expected_shortfall=round(expected_shortfall, 2),
        mean_return=round(mean_return, 2),
        std_dev=round(std_dev, 2),
        skewness=round(skewness, 2),
        kurtosis=round(kurtosis, 2),
        original_return=round(original_return, 2),
    )


def create_histogram_data(
    simulation_returns: NDArray,
    num_bins: int = 30,
) -> list[dict[str, float]]:
    """Create histogram data for visualization.

    Args:
        simulation_returns: Array of final returns from simulations
        num_bins: Number of bins for histogram

    Returns:
        List of dicts with bin_start, bin_end, frequency
    """
    hist, bin_edges = np.histogram(simulation_returns, bins=num_bins, density=True)

    return [
        {
            "bin_start": round(float(edge_start), 2),
            "bin_end": round(float(edge_end), 2),
            "frequency": round(float(freq), 4),
        }
        for freq, edge_start, edge_end in zip(hist, bin_edges[:-1], bin_edges[1:], strict=True)
    ]


def create_equity_bands(
    equity_paths: NDArray,
) -> list[dict[str, float]]:
    """Create equity curve confidence bands.

    Calculates 5th, 50th, and 95th percentile at each step.

    Args:
        equity_paths: Array of equity paths (shape: num_simulations x steps)

    Returns:
        List of dicts with step, p5, p50, p95
    """
    n_steps = equity_paths.shape[1]

    return [
        {
            "step": i,
            "p5": round(float(np.percentile(equity_paths[:, i], 5)), 2),
            "p50": round(float(np.percentile(equity_paths[:, i], 50)), 2),
            "p95": round(float(np.percentile(equity_paths[:, i], 95)), 2),
        }
        for i in range(n_steps)
    ]


def run_monte_carlo(
    trades: list[BacktestTrade],
    num_simulations: int = 1000,
    seed: int | None = None,
) -> SimulationResult:
    """Run complete Monte Carlo simulation on backtest trades.

    Uses bootstrap resampling to estimate distribution of possible outcomes.

    Args:
        trades: List of trades from a completed backtest
        num_simulations: Number of simulations to run (default 1000)
        seed: Random seed for reproducibility

    Returns:
        SimulationResult with statistics, histogram, and equity bands
    """
    # Extract trade returns
    trade_returns = extract_trade_returns(trades)

    if len(trade_returns) == 0:
        # No trades - return zero statistics
        return SimulationResult(
            statistics=MonteCarloStatistics(
                num_simulations=num_simulations,
                percentile_5=0.0,
                percentile_25=0.0,
                percentile_50=0.0,
                percentile_75=0.0,
                percentile_95=0.0,
                probability_of_loss=0.0,
                value_at_risk_95=0.0,
                expected_shortfall=0.0,
                mean_return=0.0,
                std_dev=0.0,
                skewness=0.0,
                kurtosis=0.0,
                original_return=0.0,
            ),
            histogram_data=[],
            equity_bands=[{"step": 0, "p5": 100.0, "p50": 100.0, "p95": 100.0}],
            created_at=datetime.now(UTC),
        )

    # Calculate original backtest return
    original_return = float(np.prod(1 + trade_returns / 100) - 1) * 100

    # Run bootstrap simulations for final returns
    simulation_returns = bootstrap_resample(trade_returns, num_simulations, seed)

    # Generate equity paths for bands
    equity_paths = generate_equity_paths(trade_returns, num_simulations, seed)

    # Calculate statistics
    statistics = calculate_statistics(simulation_returns, original_return)

    # Create visualization data
    histogram_data = create_histogram_data(simulation_returns)
    equity_bands = create_equity_bands(equity_paths)

    return SimulationResult(
        statistics=statistics,
        histogram_data=histogram_data,
        equity_bands=equity_bands,
        created_at=datetime.now(UTC),
    )
