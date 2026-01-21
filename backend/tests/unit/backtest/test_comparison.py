"""Unit tests for backtest comparison module."""

from datetime import UTC, date, datetime
from decimal import Decimal

from app.backtest.comparison import (
    ComparisonResult,
    NormalizedEquityPoint,
    RunMetrics,
    calculate_correlation,
    compare_backtests,
    create_run_metrics,
    normalize_equity_curve,
    rank_metrics,
)
from app.backtest.models import BacktestEquity, BacktestRun


class TestNormalizeEquityCurve:
    """Tests for normalize_equity_curve function."""

    def test_empty_curve_returns_empty(self) -> None:
        """Empty input should return empty output."""
        result = normalize_equity_curve([])
        assert result == []

    def test_single_point_returns_zero_return(self) -> None:
        """Single point should return 0% return."""
        equity = [
            BacktestEquity(
                id="1",
                run_id="run1",
                date=date(2024, 1, 1),
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                position_value=Decimal("0"),
                drawdown_pct=Decimal("0"),
                created_at=datetime.now(UTC),
            )
        ]
        result = normalize_equity_curve(equity)
        assert len(result) == 1
        assert result[0].cumulative_return_pct == Decimal("0.0")

    def test_positive_return_calculated_correctly(self) -> None:
        """Positive returns should be calculated correctly."""
        equity = [
            BacktestEquity(
                id="1",
                run_id="run1",
                date=date(2024, 1, 1),
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                position_value=Decimal("0"),
                drawdown_pct=Decimal("0"),
                created_at=datetime.now(UTC),
            ),
            BacktestEquity(
                id="2",
                run_id="run1",
                date=date(2024, 1, 2),
                equity=Decimal("110000"),  # 10% gain
                cash=Decimal("10000"),
                position_value=Decimal("100000"),
                drawdown_pct=Decimal("0"),
                created_at=datetime.now(UTC),
            ),
        ]
        result = normalize_equity_curve(equity)
        assert len(result) == 2
        assert result[0].cumulative_return_pct == Decimal("0.0")
        assert result[1].cumulative_return_pct == Decimal("10.0")

    def test_negative_return_calculated_correctly(self) -> None:
        """Negative returns should be calculated correctly."""
        equity = [
            BacktestEquity(
                id="1",
                run_id="run1",
                date=date(2024, 1, 1),
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                position_value=Decimal("0"),
                drawdown_pct=Decimal("0"),
                created_at=datetime.now(UTC),
            ),
            BacktestEquity(
                id="2",
                run_id="run1",
                date=date(2024, 1, 2),
                equity=Decimal("95000"),  # 5% loss
                cash=Decimal("5000"),
                position_value=Decimal("90000"),
                drawdown_pct=Decimal("5"),
                created_at=datetime.now(UTC),
            ),
        ]
        result = normalize_equity_curve(equity)
        assert result[1].cumulative_return_pct == Decimal("-5.0")


class TestRankMetrics:
    """Tests for rank_metrics function."""

    def test_empty_list_returns_empty(self) -> None:
        """Empty input should return empty output."""
        result = rank_metrics([])
        assert result == []

    def test_single_metric_gets_rank_1(self) -> None:
        """Single item should get rank 1 for all metrics."""
        metrics = [
            RunMetrics(
                run_id="run1",
                symbol="AAPL",
                strategy_name="signal_classifier",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                total_return_pct=Decimal("15.5"),
                sharpe_ratio=Decimal("1.2"),
                max_drawdown_pct=Decimal("10.0"),
                win_rate=Decimal("55.0"),
                num_trades=20,
                profit_factor=Decimal("1.5"),
            )
        ]
        result = rank_metrics(metrics)
        assert result[0].return_rank == 1
        assert result[0].sharpe_rank == 1
        assert result[0].drawdown_rank == 1

    def test_higher_return_gets_better_rank(self) -> None:
        """Higher return should get rank 1."""
        metrics = [
            RunMetrics(
                run_id="run1",
                symbol="AAPL",
                strategy_name="signal_classifier",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                total_return_pct=Decimal("10.0"),
                sharpe_ratio=Decimal("1.0"),
                max_drawdown_pct=Decimal("10.0"),
                win_rate=None,
                num_trades=None,
                profit_factor=None,
            ),
            RunMetrics(
                run_id="run2",
                symbol="MSFT",
                strategy_name="signal_classifier",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                total_return_pct=Decimal("20.0"),  # Higher
                sharpe_ratio=Decimal("0.8"),
                max_drawdown_pct=Decimal("15.0"),
                win_rate=None,
                num_trades=None,
                profit_factor=None,
            ),
        ]
        result = rank_metrics(metrics)
        # MSFT should be rank 1 for return
        assert result[0].return_rank == 2  # AAPL
        assert result[1].return_rank == 1  # MSFT

    def test_lower_drawdown_gets_better_rank(self) -> None:
        """Lower drawdown should get rank 1."""
        metrics = [
            RunMetrics(
                run_id="run1",
                symbol="AAPL",
                strategy_name="signal_classifier",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                total_return_pct=Decimal("10.0"),
                sharpe_ratio=Decimal("1.0"),
                max_drawdown_pct=Decimal("5.0"),  # Lower = better
                win_rate=None,
                num_trades=None,
                profit_factor=None,
            ),
            RunMetrics(
                run_id="run2",
                symbol="MSFT",
                strategy_name="signal_classifier",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                total_return_pct=Decimal("10.0"),
                sharpe_ratio=Decimal("1.0"),
                max_drawdown_pct=Decimal("15.0"),
                win_rate=None,
                num_trades=None,
                profit_factor=None,
            ),
        ]
        result = rank_metrics(metrics)
        # AAPL should be rank 1 for drawdown
        assert result[0].drawdown_rank == 1  # AAPL
        assert result[1].drawdown_rank == 2  # MSFT


class TestCalculateCorrelation:
    """Tests for calculate_correlation function."""

    def test_single_run_returns_none(self) -> None:
        """Single run should return None (need at least 2)."""
        curves = {
            "run1": [
                NormalizedEquityPoint(date=date(2024, 1, 1), cumulative_return_pct=Decimal("0")),
                NormalizedEquityPoint(date=date(2024, 1, 2), cumulative_return_pct=Decimal("1")),
            ]
        }
        result = calculate_correlation(curves)
        assert result is None

    def test_insufficient_data_returns_none(self) -> None:
        """Less than 10 overlapping days should return None."""
        curves = {
            "run1": [
                NormalizedEquityPoint(date=date(2024, 1, i), cumulative_return_pct=Decimal(str(i)))
                for i in range(1, 6)  # Only 5 days
            ],
            "run2": [
                NormalizedEquityPoint(
                    date=date(2024, 1, i), cumulative_return_pct=Decimal(str(i * 2))
                )
                for i in range(1, 6)
            ],
        }
        result = calculate_correlation(curves)
        assert result is None

    def test_positive_correlation(self) -> None:
        """Curves moving in same direction should have positive correlation."""
        # Create curves with varying daily returns but same general direction
        import random

        random.seed(42)  # For reproducibility

        # Generate returns with some variance but same direction
        base_returns = [random.uniform(0.3, 0.7) for _ in range(20)]

        curves = {
            "run1": [
                NormalizedEquityPoint(
                    date=date(2024, 1, i + 1),
                    cumulative_return_pct=Decimal(str(sum(base_returns[: i + 1]))),
                )
                for i in range(20)
            ],
            "run2": [
                NormalizedEquityPoint(
                    date=date(2024, 1, i + 1),
                    cumulative_return_pct=Decimal(
                        str(sum(base_returns[: i + 1]) * 1.2)
                    ),  # Same direction, scaled
                )
                for i in range(20)
            ],
        }
        result = calculate_correlation(curves)
        assert result is not None
        # Self-correlation should be 1.0
        assert result["run1"]["run1"] == 1.0
        assert result["run2"]["run2"] == 1.0
        # Cross-correlation should be high (same daily movements, just scaled)
        assert result["run1"]["run2"] > 0.9


class TestCreateRunMetrics:
    """Tests for create_run_metrics function."""

    def test_creates_metrics_from_run(self) -> None:
        """Should create RunMetrics from BacktestRun."""
        run = BacktestRun(
            id="run1",
            strategy_name="signal_classifier",
            symbol="AAPL",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("100000"),
            final_equity=Decimal("115500"),
            total_return_pct=Decimal("15.5"),
            sharpe_ratio=Decimal("1.2"),
            max_drawdown_pct=Decimal("10.0"),
            win_rate=Decimal("55.0"),
            num_trades=20,
            profit_factor=Decimal("1.5"),
            status="completed",
            created_at=datetime.now(UTC),
        )
        result = create_run_metrics(run)
        assert result.run_id == "run1"
        assert result.symbol == "AAPL"
        assert result.total_return_pct == Decimal("15.5")
        assert result.return_rank is None  # Not ranked yet


class TestCompareBacktests:
    """Tests for compare_backtests function."""

    def test_comparison_includes_normalized_curves(self) -> None:
        """Comparison should include normalized equity curves."""
        runs = [
            BacktestRun(
                id="run1",
                strategy_name="signal_classifier",
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                initial_capital=Decimal("100000"),
                total_return_pct=Decimal("10.0"),
                sharpe_ratio=Decimal("1.0"),
                max_drawdown_pct=Decimal("5.0"),
                win_rate=Decimal("60.0"),
                num_trades=5,
                profit_factor=Decimal("1.5"),
                status="completed",
                created_at=datetime.now(UTC),
            ),
            BacktestRun(
                id="run2",
                strategy_name="signal_classifier",
                symbol="MSFT",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                initial_capital=Decimal("100000"),
                total_return_pct=Decimal("8.0"),
                sharpe_ratio=Decimal("0.8"),
                max_drawdown_pct=Decimal("7.0"),
                win_rate=Decimal("55.0"),
                num_trades=6,
                profit_factor=Decimal("1.3"),
                status="completed",
                created_at=datetime.now(UTC),
            ),
        ]
        equity_curves = {
            "run1": [
                BacktestEquity(
                    id="1",
                    run_id="run1",
                    date=date(2024, 1, 1),
                    equity=Decimal("100000"),
                    cash=Decimal("100000"),
                    position_value=Decimal("0"),
                    drawdown_pct=Decimal("0"),
                    created_at=datetime.now(UTC),
                ),
            ],
            "run2": [
                BacktestEquity(
                    id="2",
                    run_id="run2",
                    date=date(2024, 1, 1),
                    equity=Decimal("100000"),
                    cash=Decimal("100000"),
                    position_value=Decimal("0"),
                    drawdown_pct=Decimal("0"),
                    created_at=datetime.now(UTC),
                ),
            ],
        }
        result = compare_backtests(runs, equity_curves)
        assert isinstance(result, ComparisonResult)
        assert "run1" in result.equity_curves
        assert "run2" in result.equity_curves
        assert len(result.metrics) == 2

    def test_comparison_ranks_metrics(self) -> None:
        """Comparison should rank metrics correctly."""
        runs = [
            BacktestRun(
                id="run1",
                strategy_name="signal_classifier",
                symbol="AAPL",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                initial_capital=Decimal("100000"),
                total_return_pct=Decimal("10.0"),  # Higher
                sharpe_ratio=Decimal("1.0"),
                max_drawdown_pct=Decimal("5.0"),
                win_rate=Decimal("60.0"),
                num_trades=5,
                profit_factor=Decimal("1.5"),
                status="completed",
                created_at=datetime.now(UTC),
            ),
            BacktestRun(
                id="run2",
                strategy_name="signal_classifier",
                symbol="MSFT",
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 10),
                initial_capital=Decimal("100000"),
                total_return_pct=Decimal("8.0"),  # Lower
                sharpe_ratio=Decimal("0.8"),
                max_drawdown_pct=Decimal("7.0"),
                win_rate=Decimal("55.0"),
                num_trades=6,
                profit_factor=Decimal("1.3"),
                status="completed",
                created_at=datetime.now(UTC),
            ),
        ]
        equity_curves = {
            "run1": [],
            "run2": [],
        }
        result = compare_backtests(runs, equity_curves)
        # AAPL should be ranked 1 for return
        aapl_metrics = next(m for m in result.metrics if m.symbol == "AAPL")
        msft_metrics = next(m for m in result.metrics if m.symbol == "MSFT")
        assert aapl_metrics.return_rank == 1
        assert msft_metrics.return_rank == 2
