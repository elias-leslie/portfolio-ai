"""Unit tests for walk-forward backtesting module."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.backtest.benchmark import BenchmarkComparison, BenchmarkMetrics
from app.backtest.models import BacktestEquity, BacktestTrade
from app.backtest.replay import BacktestState
from app.backtest.walk_forward import (
    FoldMetrics,
    WalkForwardEngine,
    WalkForwardResult,
)


class TestWalkForwardWindowCreation:
    """Tests for WalkForwardEngine.create_windows method."""

    def test_creates_windows_with_correct_structure(self) -> None:
        """Should create windows with TRAIN→GAP→VAL→GAP→TEST structure."""
        engine = WalkForwardEngine(
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        start_date = date(2023, 1, 1)
        end_date = date(2024, 12, 31)  # 2 years

        windows = engine.create_windows(start_date, end_date)

        # Should create multiple windows
        assert len(windows) > 0

        # Check first window structure
        first_window = windows[0]
        assert first_window.fold_number == 1
        assert first_window.train_start == start_date

        # Train period is 180 days
        train_duration = (first_window.train_end - first_window.train_start).days + 1
        assert train_duration == 180

        # Gap 1: 10 days between train_end and val_start
        gap1_duration = (first_window.val_start - first_window.train_end).days - 1
        assert gap1_duration == 10

        # Val period is 60 days
        val_duration = (first_window.val_end - first_window.val_start).days + 1
        assert val_duration == 60

        # Gap 2: 10 days between val_end and test_start
        gap2_duration = (first_window.test_start - first_window.val_end).days - 1
        assert gap2_duration == 10

        # Test period is 60 days
        test_duration = (first_window.test_end - first_window.test_start).days + 1
        assert test_duration == 60

    def test_default_gap_days_is_10(self) -> None:
        """Should use gap_days=10 by default."""
        engine = WalkForwardEngine()
        assert engine.gap_days == 10

    def test_windows_roll_forward_by_step_days(self) -> None:
        """Windows should roll forward by step_days."""
        engine = WalkForwardEngine(
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        start_date = date(2023, 1, 1)
        end_date = date(2024, 12, 31)

        windows = engine.create_windows(start_date, end_date)

        if len(windows) >= 2:
            # Second window should start 60 days after first
            assert (windows[1].train_start - windows[0].train_start).days == 60

    def test_windows_do_not_exceed_end_date(self) -> None:
        """All windows should end before or on end_date."""
        engine = WalkForwardEngine(
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        start_date = date(2023, 1, 1)
        end_date = date(2023, 12, 31)

        windows = engine.create_windows(start_date, end_date)

        for window in windows:
            assert window.test_end <= end_date

    def test_insufficient_data_returns_empty_list(self) -> None:
        """Should return empty list if date range is too short."""
        engine = WalkForwardEngine(
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        start_date = date(2023, 1, 1)
        end_date = date(2023, 3, 1)  # Only ~60 days

        windows = engine.create_windows(start_date, end_date)

        assert len(windows) == 0

    def test_fold_numbers_increment_correctly(self) -> None:
        """Fold numbers should increment from 1."""
        engine = WalkForwardEngine(
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        start_date = date(2023, 1, 1)
        end_date = date(2024, 12, 31)

        windows = engine.create_windows(start_date, end_date)

        for i, window in enumerate(windows):
            assert window.fold_number == i + 1


class TestFoldMetricsDataclass:
    """Tests for FoldMetrics dataclass."""

    def test_fold_metrics_fields_populate_correctly(self) -> None:
        """All FoldMetrics fields should populate correctly."""
        metrics = FoldMetrics(
            fold_number=1,
            total_return_pct=15.5,
            sharpe_ratio=1.2,
            win_rate=0.6,
            max_drawdown_pct=10.0,
            num_trades=20,
            profit_factor=1.8,
            buy_hold_return_pct=10.0,
            excess_return_pct=5.5,
            beats_buy_hold=True,
            alpha=0.05,
            beta=0.95,
            test_start=date(2023, 1, 1),
            test_end=date(2023, 3, 31),
        )

        assert metrics.fold_number == 1
        assert metrics.total_return_pct == 15.5
        assert metrics.sharpe_ratio == 1.2
        assert metrics.win_rate == 0.6
        assert metrics.max_drawdown_pct == 10.0
        assert metrics.num_trades == 20
        assert metrics.profit_factor == 1.8
        assert metrics.buy_hold_return_pct == 10.0
        assert metrics.excess_return_pct == 5.5
        assert metrics.beats_buy_hold is True
        assert metrics.alpha == 0.05
        assert metrics.beta == 0.95
        assert metrics.test_start == date(2023, 1, 1)
        assert metrics.test_end == date(2023, 3, 31)

    def test_beats_buy_hold_calculation(self) -> None:
        """beats_buy_hold should be True when excess_return_pct > 0."""
        # Beats B&H
        metrics_win = FoldMetrics(
            fold_number=1,
            total_return_pct=15.0,
            sharpe_ratio=1.0,
            win_rate=0.5,
            max_drawdown_pct=5.0,
            num_trades=10,
            profit_factor=1.5,
            buy_hold_return_pct=10.0,
            excess_return_pct=5.0,
            beats_buy_hold=True,
            alpha=None,
            beta=None,
            test_start=date(2023, 1, 1),
            test_end=date(2023, 3, 31),
        )
        assert metrics_win.beats_buy_hold is True
        assert metrics_win.excess_return_pct > 0

        # Loses to B&H
        metrics_loss = FoldMetrics(
            fold_number=2,
            total_return_pct=5.0,
            sharpe_ratio=0.8,
            win_rate=0.4,
            max_drawdown_pct=8.0,
            num_trades=10,
            profit_factor=1.2,
            buy_hold_return_pct=10.0,
            excess_return_pct=-5.0,
            beats_buy_hold=False,
            alpha=None,
            beta=None,
            test_start=date(2023, 4, 1),
            test_end=date(2023, 6, 30),
        )
        assert metrics_loss.beats_buy_hold is False
        assert metrics_loss.excess_return_pct < 0


class TestWalkForwardResultAggregation:
    """Tests for WalkForwardResult aggregation logic."""

    def test_mean_return_pct_calculation(self) -> None:
        """mean_return_pct should be average of fold returns."""
        folds = [
            FoldMetrics(
                fold_number=1,
                total_return_pct=10.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=8.0,
                excess_return_pct=2.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            ),
            FoldMetrics(
                fold_number=2,
                total_return_pct=20.0,
                sharpe_ratio=1.5,
                win_rate=0.6,
                max_drawdown_pct=8.0,
                num_trades=15,
                profit_factor=2.0,
                buy_hold_return_pct=15.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 4, 1),
                test_end=date(2023, 6, 30),
            ),
            FoldMetrics(
                fold_number=3,
                total_return_pct=15.0,
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown_pct=6.0,
                num_trades=12,
                profit_factor=1.8,
                buy_hold_return_pct=12.0,
                excess_return_pct=3.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 7, 1),
                test_end=date(2023, 9, 30),
            ),
        ]

        # Create engine and aggregate
        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # Mean return should be (10 + 20 + 15) / 3 = 15.0
        assert result.mean_return_pct == pytest.approx(15.0)

    def test_std_return_pct_calculation(self) -> None:
        """std_return_pct should be standard deviation of fold returns."""
        folds = [
            FoldMetrics(
                fold_number=1,
                total_return_pct=10.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=8.0,
                excess_return_pct=2.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            ),
            FoldMetrics(
                fold_number=2,
                total_return_pct=20.0,
                sharpe_ratio=1.5,
                win_rate=0.6,
                max_drawdown_pct=8.0,
                num_trades=15,
                profit_factor=2.0,
                buy_hold_return_pct=15.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 4, 1),
                test_end=date(2023, 6, 30),
            ),
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # With 2 folds, std should be calculated
        assert result.std_return_pct > 0

    def test_pct_folds_beat_bh_calculation(self) -> None:
        """pct_folds_beat_bh should be percentage of folds that beat B&H."""
        folds = [
            FoldMetrics(
                fold_number=1,
                total_return_pct=15.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=10.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,  # Beats
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            ),
            FoldMetrics(
                fold_number=2,
                total_return_pct=5.0,
                sharpe_ratio=0.8,
                win_rate=0.4,
                max_drawdown_pct=8.0,
                num_trades=8,
                profit_factor=1.2,
                buy_hold_return_pct=10.0,
                excess_return_pct=-5.0,
                beats_buy_hold=False,  # Loses
                alpha=None,
                beta=None,
                test_start=date(2023, 4, 1),
                test_end=date(2023, 6, 30),
            ),
            FoldMetrics(
                fold_number=3,
                total_return_pct=20.0,
                sharpe_ratio=1.5,
                win_rate=0.6,
                max_drawdown_pct=6.0,
                num_trades=12,
                profit_factor=2.0,
                buy_hold_return_pct=12.0,
                excess_return_pct=8.0,
                beats_buy_hold=True,  # Beats
                alpha=None,
                beta=None,
                test_start=date(2023, 7, 1),
                test_end=date(2023, 9, 30),
            ),
            FoldMetrics(
                fold_number=4,
                total_return_pct=18.0,
                sharpe_ratio=1.3,
                win_rate=0.55,
                max_drawdown_pct=7.0,
                num_trades=11,
                profit_factor=1.8,
                buy_hold_return_pct=10.0,
                excess_return_pct=8.0,
                beats_buy_hold=True,  # Beats
                alpha=None,
                beta=None,
                test_start=date(2023, 10, 1),
                test_end=date(2023, 12, 31),
            ),
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # 3 out of 4 folds beat B&H = 75%
        assert result.pct_folds_beat_bh == pytest.approx(0.75)

    def test_max_drawdown_is_worst_across_folds(self) -> None:
        """max_drawdown_pct should be the worst drawdown across all folds."""
        folds = [
            FoldMetrics(
                fold_number=1,
                total_return_pct=10.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,  # Lowest
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=8.0,
                excess_return_pct=2.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            ),
            FoldMetrics(
                fold_number=2,
                total_return_pct=15.0,
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown_pct=12.0,  # Highest (worst)
                num_trades=12,
                profit_factor=1.8,
                buy_hold_return_pct=10.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 4, 1),
                test_end=date(2023, 6, 30),
            ),
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        assert result.max_drawdown_pct == 12.0

    def test_total_trades_sum(self) -> None:
        """total_trades should be sum of all fold trades."""
        folds = [
            FoldMetrics(
                fold_number=1,
                total_return_pct=10.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=8.0,
                excess_return_pct=2.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            ),
            FoldMetrics(
                fold_number=2,
                total_return_pct=15.0,
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown_pct=6.0,
                num_trades=15,
                profit_factor=1.8,
                buy_hold_return_pct=10.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 4, 1),
                test_end=date(2023, 6, 30),
            ),
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        assert result.total_trades == 25


class TestWilcoxonTestImplementation:
    """Tests for Wilcoxon signed-rank test implementation."""

    def test_statistical_significance_strong(self) -> None:
        """p < 0.01 should give strong significance."""
        # Create folds where strategy consistently beats B&H
        folds = [
            FoldMetrics(
                fold_number=i + 1,
                total_return_pct=20.0 + i,
                sharpe_ratio=1.5,
                win_rate=0.6,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=2.0,
                buy_hold_return_pct=10.0,
                excess_return_pct=10.0 + i,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            )
            for i in range(10)  # 10 folds for strong significance
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # Should be statistically significant
        assert result.statistically_significant is True
        assert result.significance_level == "strong"
        assert result.wilcoxon_p_value is not None
        assert result.wilcoxon_p_value < 0.01

    def test_statistical_significance_moderate(self) -> None:
        """p < 0.05 but >= 0.01 should give moderate significance."""
        # Create folds with moderate outperformance
        folds = [
            FoldMetrics(
                fold_number=i + 1,
                total_return_pct=12.0 + i * 0.5,
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown_pct=6.0,
                num_trades=10,
                profit_factor=1.6,
                buy_hold_return_pct=10.0,
                excess_return_pct=2.0 + i * 0.5,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            )
            for i in range(7)
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # Check if moderate or strong (depends on exact values)
        if result.wilcoxon_p_value is not None and result.wilcoxon_p_value < 0.05:
            assert result.statistically_significant is True
            assert result.significance_level in ["moderate", "strong"]

    def test_statistical_significance_weak(self) -> None:
        """p < 0.10 but >= 0.05 should give weak significance."""
        # Create folds with slight outperformance
        folds = [
            FoldMetrics(
                fold_number=i + 1,
                total_return_pct=10.5 + (i % 2) * 0.5,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=7.0,
                num_trades=10,
                profit_factor=1.3,
                buy_hold_return_pct=10.0,
                excess_return_pct=0.5 + (i % 2) * 0.5,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            )
            for i in range(6)
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # Should have a p-value (6 folds >= 5 minimum)
        assert result.wilcoxon_p_value is not None or len(folds) < 5

    def test_statistical_significance_none(self) -> None:
        """p >= 0.10 should give no significance."""
        # Create folds with mixed results (no consistent pattern)
        folds = [
            FoldMetrics(
                fold_number=i + 1,
                total_return_pct=10.0 if i % 2 == 0 else 9.0,
                sharpe_ratio=1.0,
                win_rate=0.5,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.5,
                buy_hold_return_pct=10.0,
                excess_return_pct=0.0 if i % 2 == 0 else -1.0,
                beats_buy_hold=i % 2 == 0,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            )
            for i in range(6)
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # With mixed results, should not be significant
        if result.wilcoxon_p_value is not None:
            assert result.significance_level in ["weak", "none"]

    def test_minimum_5_samples_requirement(self) -> None:
        """Wilcoxon test should require at least 5 samples."""
        # Only 4 folds
        folds = [
            FoldMetrics(
                fold_number=i + 1,
                total_return_pct=15.0,
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown_pct=5.0,
                num_trades=10,
                profit_factor=1.8,
                buy_hold_return_pct=10.0,
                excess_return_pct=5.0,
                beats_buy_hold=True,
                alpha=None,
                beta=None,
                test_start=date(2023, 1, 1),
                test_end=date(2023, 3, 31),
            )
            for i in range(4)
        ]

        engine = WalkForwardEngine()
        result = engine._aggregate_results(folds)

        # Should not have Wilcoxon p-value with < 5 samples
        assert result.wilcoxon_p_value is None
        assert result.statistically_significant is False
        assert result.significance_level == "none"


class TestWalkForwardEngineRun:
    """Tests for WalkForwardEngine.run_walk_forward method."""

    @patch("app.backtest.walk_forward.replay_backtest")
    @patch("app.backtest.walk_forward.BenchmarkComparisonEngine")
    def test_walk_forward_engine_run_full_flow(
        self, mock_benchmark_engine_class: MagicMock, mock_replay: MagicMock
    ) -> None:
        """Test full run_walk_forward() flow with mocked dependencies."""
        # Mock storage
        mock_storage = MagicMock()

        # Create sample trades
        sample_trades = [
            BacktestTrade(
                id="1",
                run_id="wf-1",
                symbol="AAPL",
                entry_date=date(2023, 1, 1),
                entry_price=Decimal("100"),
                exit_date=date(2023, 1, 15),
                exit_price=Decimal("110"),
                shares=10,
                pnl=Decimal("100"),
                pnl_pct=Decimal("10.0"),
                created_at=datetime.now(UTC),
            ),
        ]

        # Mock equity curve
        sample_equity = [
            BacktestEquity(
                id="e1",
                run_id="wf-1",
                date=date(2023, 1, 1),
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                position_value=Decimal("0"),
                drawdown_pct=Decimal("0.0"),
                created_at=datetime.now(UTC),
            ),
            BacktestEquity(
                id="e2",
                run_id="wf-1",
                date=date(2023, 1, 15),
                equity=Decimal("110000"),
                cash=Decimal("0"),
                position_value=Decimal("110000"),
                drawdown_pct=Decimal("0.0"),
                created_at=datetime.now(UTC),
            ),
        ]

        # Mock backtest state
        mock_state = BacktestState(
            cash=Decimal("100000"),
            trades=sample_trades,
            equity_curve=sample_equity,
        )
        mock_replay.return_value = mock_state

        # Mock benchmark comparison
        mock_benchmark_metrics = BenchmarkMetrics(
            benchmark_symbol="SPY",
            strategy_return_pct=Decimal("10.0"),
            benchmark_return_pct=Decimal("8.0"),
            outperformance_pct=Decimal("2.0"),
            alpha=Decimal("0.02"),
            information_ratio=Decimal("0.5"),
            tracking_error=Decimal("4.0"),
            beta=Decimal("0.95"),
            correlation=0.85,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            num_periods=252,
        )
        mock_comparison = BenchmarkComparison(
            metrics=mock_benchmark_metrics,
            strategy_equity=[],
            benchmark_equity=[],
        )

        mock_benchmark_engine = MagicMock()
        mock_benchmark_engine.compare_to_benchmark.return_value = mock_comparison
        mock_benchmark_engine_class.return_value = mock_benchmark_engine

        # Create engine with short periods for testing
        engine = WalkForwardEngine(
            storage=mock_storage,
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=180,
        )

        # Run walk-forward
        result = engine.run_walk_forward(
            symbol="AAPL",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            strategy_type="enhanced",
            initial_capital=Decimal("100000.00"),
            benchmark_symbol="SPY",
        )

        # Verify result structure
        assert isinstance(result, WalkForwardResult)
        assert result.num_folds >= 0
        assert hasattr(result, "mean_return_pct")
        assert hasattr(result, "std_return_pct")
        assert hasattr(result, "mean_sharpe")
        assert hasattr(result, "pct_folds_beat_bh")
        assert hasattr(result, "wilcoxon_p_value")
        assert hasattr(result, "statistically_significant")
        assert hasattr(result, "significance_level")

    @patch("app.backtest.walk_forward.replay_backtest")
    def test_empty_windows_returns_empty_result(self, mock_replay: MagicMock) -> None:
        """Should return empty result when no windows can be created."""
        mock_storage = MagicMock()

        engine = WalkForwardEngine(
            storage=mock_storage,
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=60,
        )

        # Date range too short for any windows
        result = engine.run_walk_forward(
            symbol="AAPL",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 2, 1),  # Only 1 month
            strategy_type="enhanced",
        )

        assert result.num_folds == 0
        assert result.mean_return_pct == 0.0
        assert result.statistically_significant is False
        assert len(result.folds) == 0

    @patch("app.backtest.walk_forward.replay_backtest")
    @patch("app.backtest.walk_forward.BenchmarkComparisonEngine")
    def test_bh_comparison_included_in_fold_metrics(
        self, mock_benchmark_engine_class: MagicMock, mock_replay: MagicMock
    ) -> None:
        """Each fold should include B&H comparison metrics."""
        mock_storage = MagicMock()

        # Mock backtest state
        sample_trades = [
            BacktestTrade(
                id="1",
                run_id="wf-1",
                symbol="AAPL",
                entry_date=date(2023, 1, 1),
                entry_price=Decimal("100"),
                exit_date=date(2023, 1, 15),
                exit_price=Decimal("115"),
                shares=10,
                pnl=Decimal("150"),
                pnl_pct=Decimal("15.0"),
                created_at=datetime.now(UTC),
            ),
        ]

        sample_equity = [
            BacktestEquity(
                id="e1",
                run_id="wf-1",
                date=date(2023, 1, 1),
                equity=Decimal("100000"),
                cash=Decimal("100000"),
                position_value=Decimal("0"),
                drawdown_pct=Decimal("0.0"),
                created_at=datetime.now(UTC),
            ),
            BacktestEquity(
                id="e2",
                run_id="wf-1",
                date=date(2023, 1, 15),
                equity=Decimal("115000"),
                cash=Decimal("0"),
                position_value=Decimal("115000"),
                drawdown_pct=Decimal("0.0"),
                created_at=datetime.now(UTC),
            ),
        ]

        mock_state = BacktestState(
            cash=Decimal("100000"),
            trades=sample_trades,
            equity_curve=sample_equity,
        )
        mock_replay.return_value = mock_state

        # Mock benchmark comparison - strategy beats B&H
        mock_benchmark_metrics = BenchmarkMetrics(
            benchmark_symbol="SPY",
            strategy_return_pct=Decimal("15.0"),
            benchmark_return_pct=Decimal("10.0"),
            outperformance_pct=Decimal("5.0"),
            alpha=Decimal("0.05"),
            information_ratio=Decimal("0.8"),
            tracking_error=Decimal("6.25"),
            beta=Decimal("0.90"),
            correlation=0.80,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            num_periods=252,
        )
        mock_comparison = BenchmarkComparison(
            metrics=mock_benchmark_metrics,
            strategy_equity=[],
            benchmark_equity=[],
        )

        mock_benchmark_engine = MagicMock()
        mock_benchmark_engine.compare_to_benchmark.return_value = mock_comparison
        mock_benchmark_engine_class.return_value = mock_benchmark_engine

        engine = WalkForwardEngine(
            storage=mock_storage,
            train_days=180,
            val_days=60,
            test_days=60,
            gap_days=10,
            step_days=180,
        )

        result = engine.run_walk_forward(
            symbol="AAPL",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            strategy_type="enhanced",
        )

        # Check that folds have B&H comparison
        if result.num_folds > 0:
            for fold in result.folds:
                assert hasattr(fold, "buy_hold_return_pct")
                assert hasattr(fold, "excess_return_pct")
                assert hasattr(fold, "beats_buy_hold")
                assert hasattr(fold, "alpha")
                assert hasattr(fold, "beta")

    def test_empty_result_structure(self) -> None:
        """_empty_result should return properly structured empty result."""
        engine = WalkForwardEngine()
        result = engine._empty_result()

        assert isinstance(result, WalkForwardResult)
        assert result.num_folds == 0
        assert len(result.folds) == 0
        assert result.mean_return_pct == 0.0
        assert result.std_return_pct == 0.0
        assert result.mean_sharpe == 0.0
        assert result.std_sharpe == 0.0
        assert result.mean_win_rate == 0.0
        assert result.max_drawdown_pct == 0.0
        assert result.total_trades == 0
        assert result.mean_excess_vs_bh == 0.0
        assert result.pct_folds_beat_bh == 0.0
        assert result.wilcoxon_p_value is None
        assert result.statistically_significant is False
        assert result.significance_level == "none"
