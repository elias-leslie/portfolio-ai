"""Unit tests for Monte Carlo simulation module."""

from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pytest

from app.backtest.models import BacktestTrade
from app.backtest.monte_carlo import (
    MonteCarloStatistics,
    SimulationResult,
    bootstrap_resample,
    calculate_statistics,
    create_equity_bands,
    create_histogram_data,
    extract_trade_returns,
    generate_equity_paths,
    run_monte_carlo,
)


class TestExtractTradeReturns:
    """Tests for extract_trade_returns function."""

    def test_empty_trades_returns_empty_array(self) -> None:
        """Empty trade list should return empty array."""
        result = extract_trade_returns([])
        assert len(result) == 0

    def test_extracts_pnl_pct_from_trades(self) -> None:
        """Should extract pnl_pct values from trades."""
        trades = [
            BacktestTrade(
                id="1",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 1),
                entry_price=Decimal("100"),
                exit_date=date(2024, 1, 5),
                exit_price=Decimal("110"),
                shares=10,
                pnl=Decimal("100"),
                pnl_pct=Decimal("10.0"),
                created_at=datetime.now(),
            ),
            BacktestTrade(
                id="2",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 10),
                entry_price=Decimal("110"),
                exit_date=date(2024, 1, 15),
                exit_price=Decimal("100"),
                shares=10,
                pnl=Decimal("-100"),
                pnl_pct=Decimal("-9.09"),
                created_at=datetime.now(),
            ),
        ]
        result = extract_trade_returns(trades)
        assert len(result) == 2
        assert result[0] == pytest.approx(10.0)
        assert result[1] == pytest.approx(-9.09)

    def test_skips_trades_without_pnl_pct(self) -> None:
        """Should skip trades where pnl_pct is None."""
        trades = [
            BacktestTrade(
                id="1",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 1),
                entry_price=Decimal("100"),
                shares=10,
                pnl_pct=Decimal("5.0"),
                created_at=datetime.now(),
            ),
            BacktestTrade(
                id="2",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 10),
                entry_price=Decimal("110"),
                shares=10,
                pnl_pct=None,  # Still open
                created_at=datetime.now(),
            ),
        ]
        result = extract_trade_returns(trades)
        assert len(result) == 1


class TestBootstrapResample:
    """Tests for bootstrap_resample function."""

    def test_empty_returns_gives_zeros(self) -> None:
        """Empty trade returns should produce zeros."""
        returns = np.array([])
        result = bootstrap_resample(returns, num_simulations=100, seed=42)
        assert len(result) == 100
        assert all(r == 0 for r in result)

    def test_reproducible_with_seed(self) -> None:
        """Same seed should produce same results."""
        returns = np.array([5.0, 10.0, -3.0, 7.0, -2.0])
        result1 = bootstrap_resample(returns, num_simulations=100, seed=42)
        result2 = bootstrap_resample(returns, num_simulations=100, seed=42)
        np.testing.assert_array_equal(result1, result2)

    def test_different_seeds_give_different_results(self) -> None:
        """Different seeds should produce different results."""
        returns = np.array([5.0, 10.0, -3.0, 7.0, -2.0])
        result1 = bootstrap_resample(returns, num_simulations=100, seed=42)
        result2 = bootstrap_resample(returns, num_simulations=100, seed=43)
        assert not np.array_equal(result1, result2)

    def test_returns_correct_number_of_simulations(self) -> None:
        """Should return requested number of simulations."""
        returns = np.array([5.0, 10.0, -3.0])
        result = bootstrap_resample(returns, num_simulations=500, seed=42)
        assert len(result) == 500


class TestGenerateEquityPaths:
    """Tests for generate_equity_paths function."""

    def test_empty_returns_gives_flat_paths(self) -> None:
        """Empty returns should give flat paths at 100."""
        returns = np.array([])
        result = generate_equity_paths(returns, num_simulations=10, seed=42)
        assert result.shape == (10, 1)
        assert all(result[:, 0] == 100)

    def test_path_shape_matches_trades(self) -> None:
        """Path length should be num_trades + 1."""
        returns = np.array([5.0, 10.0, -3.0, 7.0])  # 4 trades
        result = generate_equity_paths(returns, num_simulations=10, seed=42)
        assert result.shape == (10, 5)  # 10 paths, 5 steps

    def test_paths_start_at_100(self) -> None:
        """All paths should start at 100 (normalized)."""
        returns = np.array([5.0, 10.0, -3.0])
        result = generate_equity_paths(returns, num_simulations=10, seed=42)
        assert all(result[:, 0] == 100)


class TestCalculateStatistics:
    """Tests for calculate_statistics function."""

    def test_returns_all_required_fields(self) -> None:
        """Should return statistics with all required fields."""
        returns = np.random.randn(1000) * 10 + 5  # Mean 5%, std 10%
        stats = calculate_statistics(returns, original_return=5.0)

        assert stats.num_simulations == 1000
        assert hasattr(stats, "percentile_5")
        assert hasattr(stats, "percentile_50")
        assert hasattr(stats, "percentile_95")
        assert hasattr(stats, "probability_of_loss")
        assert hasattr(stats, "value_at_risk_95")
        assert hasattr(stats, "expected_shortfall")
        assert hasattr(stats, "mean_return")
        assert hasattr(stats, "std_dev")

    def test_probability_of_loss_calculated_correctly(self) -> None:
        """Probability of loss should match % of negative returns."""
        # 100 returns, 30 are negative
        returns = np.array([1.0] * 70 + [-1.0] * 30)
        stats = calculate_statistics(returns, original_return=0.5)
        assert stats.probability_of_loss == 30.0

    def test_percentiles_in_correct_order(self) -> None:
        """Percentiles should be in ascending order."""
        returns = np.random.randn(1000) * 10
        stats = calculate_statistics(returns, original_return=0.0)

        assert stats.percentile_5 <= stats.percentile_25
        assert stats.percentile_25 <= stats.percentile_50
        assert stats.percentile_50 <= stats.percentile_75
        assert stats.percentile_75 <= stats.percentile_95


class TestCreateHistogramData:
    """Tests for create_histogram_data function."""

    def test_returns_correct_number_of_bins(self) -> None:
        """Should return requested number of bins."""
        returns = np.random.randn(100)
        result = create_histogram_data(returns, num_bins=20)
        assert len(result) == 20

    def test_bins_have_required_fields(self) -> None:
        """Each bin should have bin_start, bin_end, frequency."""
        returns = np.random.randn(100)
        result = create_histogram_data(returns, num_bins=10)

        for bin_data in result:
            assert "bin_start" in bin_data
            assert "bin_end" in bin_data
            assert "frequency" in bin_data

    def test_bins_are_consecutive(self) -> None:
        """Bin end should match next bin start."""
        returns = np.random.randn(100)
        result = create_histogram_data(returns, num_bins=10)

        for i in range(len(result) - 1):
            assert result[i]["bin_end"] == pytest.approx(result[i + 1]["bin_start"], abs=0.01)


class TestCreateEquityBands:
    """Tests for create_equity_bands function."""

    def test_returns_correct_number_of_steps(self) -> None:
        """Should return one entry per step."""
        paths = np.ones((100, 10)) * 100  # 100 paths, 10 steps
        result = create_equity_bands(paths)
        assert len(result) == 10

    def test_bands_have_required_fields(self) -> None:
        """Each band should have step, p5, p50, p95."""
        paths = np.ones((100, 5)) * 100
        result = create_equity_bands(paths)

        for band in result:
            assert "step" in band
            assert "p5" in band
            assert "p50" in band
            assert "p95" in band

    def test_bands_in_correct_order(self) -> None:
        """p5 <= p50 <= p95 at each step."""
        # Create paths with variance
        paths = np.random.randn(100, 10) * 10 + 100
        result = create_equity_bands(paths)

        for band in result:
            assert band["p5"] <= band["p50"]
            assert band["p50"] <= band["p95"]


class TestRunMonteCarlo:
    """Tests for run_monte_carlo function."""

    def test_returns_simulation_result(self) -> None:
        """Should return SimulationResult with all components."""
        trades = [
            BacktestTrade(
                id="1",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 1),
                entry_price=Decimal("100"),
                exit_date=date(2024, 1, 5),
                exit_price=Decimal("110"),
                shares=10,
                pnl=Decimal("100"),
                pnl_pct=Decimal("10.0"),
                created_at=datetime.now(),
            ),
            BacktestTrade(
                id="2",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 10),
                entry_price=Decimal("110"),
                exit_date=date(2024, 1, 15),
                exit_price=Decimal("105"),
                shares=10,
                pnl=Decimal("-50"),
                pnl_pct=Decimal("-4.55"),
                created_at=datetime.now(),
            ),
        ]

        result = run_monte_carlo(trades, num_simulations=100, seed=42)

        assert isinstance(result, SimulationResult)
        assert isinstance(result.statistics, MonteCarloStatistics)
        assert result.statistics.num_simulations == 100
        assert len(result.histogram_data) > 0
        assert len(result.equity_bands) > 0

    def test_empty_trades_returns_zero_stats(self) -> None:
        """Empty trades should return zero statistics."""
        result = run_monte_carlo([], num_simulations=100, seed=42)

        assert result.statistics.mean_return == 0.0
        assert result.statistics.std_dev == 0.0
        assert result.statistics.probability_of_loss == 0.0

    def test_reproducible_with_seed(self) -> None:
        """Same seed should produce same results."""
        trades = [
            BacktestTrade(
                id="1",
                run_id="run1",
                symbol="AAPL",
                entry_date=date(2024, 1, 1),
                entry_price=Decimal("100"),
                exit_date=date(2024, 1, 5),
                exit_price=Decimal("110"),
                shares=10,
                pnl=Decimal("100"),
                pnl_pct=Decimal("10.0"),
                created_at=datetime.now(),
            ),
        ]

        result1 = run_monte_carlo(trades, num_simulations=100, seed=42)
        result2 = run_monte_carlo(trades, num_simulations=100, seed=42)

        assert result1.statistics.mean_return == result2.statistics.mean_return
        assert result1.statistics.percentile_50 == result2.statistics.percentile_50
