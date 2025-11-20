"""Unit tests for StrategyOptimizer."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from app.strategies.models import (
    ExpectedCharacteristics,
    OptimizedStrategyConfig,
    StrategyGenerationResult,
    StrategyParameters,
)
from app.strategies.optimizer import BacktestMetrics, StrategyOptimizer, ValidationWindow


@pytest.fixture
def mock_storage():
    """Create mock PortfolioStorage."""
    return Mock()


@pytest.fixture
def optimizer(mock_storage):
    """Create StrategyOptimizer with mock storage."""
    with patch("app.strategies.optimizer.PortfolioStorage", return_value=mock_storage):
        return StrategyOptimizer()


@pytest.fixture
def sample_strategy_template():
    """Create sample strategy generation result."""
    return StrategyGenerationResult(
        strategy_type="momentum",
        reasoning="Strong momentum with good fundamentals. Test strategy for optimization.",
        confidence=0.85,
        parameters=StrategyParameters(
            weight_price_trend=0.20,
            weight_rsi_health=0.10,
            weight_momentum=0.25,
            weight_volume=0.10,
            weight_fundamentals=0.15,
            weight_news_sentiment=0.15,
            weight_sector_alignment=0.05,
            min_confirmations=6,
            min_weighted_score=0.65,
            stop_loss_atr_multiplier=Decimal("2.0"),
            max_holding_days=60,
            position_sizing_method="fixed_dollars",
            position_size_value=Decimal("10000.00"),
            rsi_oversold_threshold=30,
            rsi_overbought_threshold=70,
            volume_multiplier_threshold=0.7,
            news_sentiment_threshold=0.2,
        ),
        expected_characteristics=ExpectedCharacteristics(
            avg_holding_period_days=45,
            expected_win_rate=0.58,
            expected_sharpe=1.4,
            risk_level="medium",
        ),
    )


class TestStrategyOptimizer:
    """Test suite for StrategyOptimizer."""

    def test_initialization(self, optimizer):
        """Test optimizer initialization."""
        assert optimizer.storage is not None

    def test_create_walk_forward_windows(self, optimizer):
        """Test walk-forward validation window creation."""
        start_date = date(2023, 1, 1)
        end_date = date(2024, 1, 1)

        windows = optimizer._create_walk_forward_windows(start_date, end_date)

        # Should create multiple windows
        assert len(windows) >= 2
        assert all(isinstance(w, ValidationWindow) for w in windows)

        # Windows should not overlap (train ends before val starts)
        for window in windows:
            assert window.train_start < window.train_end
            assert window.val_start < window.val_end
            assert window.train_end <= window.val_start

        # Windows should be in chronological order
        for i in range(len(windows) - 1):
            assert windows[i].val_end <= windows[i + 1].train_start

    def test_generate_param_grid_respects_max_combinations(
        self, optimizer, sample_strategy_template
    ):
        """Test parameter grid generation respects max_combinations limit."""
        max_combinations = 20

        param_grid = optimizer._generate_param_grid(sample_strategy_template, max_combinations)

        assert len(param_grid) <= max_combinations
        assert all(isinstance(params, StrategyParameters) for params in param_grid)

    def test_generate_param_grid_explores_parameter_space(
        self, optimizer, sample_strategy_template
    ):
        """Test parameter grid explores reasonable parameter space."""
        param_grid = optimizer._generate_param_grid(sample_strategy_template, max_combinations=30)

        # Should generate multiple variations
        assert len(param_grid) > 1

        # Parameters should have different values
        unique_min_confirmations = {p.min_confirmations for p in param_grid}
        unique_max_holding_days = {p.max_holding_days for p in param_grid}

        assert len(unique_min_confirmations) > 1
        assert len(unique_max_holding_days) > 1

        # All parameters should be valid
        for params in param_grid:
            assert 3 <= params.min_confirmations <= 8
            assert 20 <= params.max_holding_days <= 120
            assert params.stop_loss_atr_multiplier > 0

    @pytest.mark.asyncio
    async def test_optimize_strategy_parameters_success(self, optimizer, sample_strategy_template):
        """Test successful strategy optimization."""
        symbol = "AAPL"

        # Mock backtest runs
        mock_backtest_results = [
            BacktestMetrics(
                sharpe_ratio=1.2,
                win_rate=0.55,
                max_drawdown=0.18,
                total_return=0.22,
                num_trades=12,
                profit_factor=1.8,
            ),
            BacktestMetrics(
                sharpe_ratio=1.5,  # Best Sharpe
                win_rate=0.60,
                max_drawdown=0.15,
                total_return=0.28,
                num_trades=10,
                profit_factor=2.1,
            ),
            BacktestMetrics(
                sharpe_ratio=1.1,
                win_rate=0.52,
                max_drawdown=0.20,
                total_return=0.18,
                num_trades=15,
                profit_factor=1.6,
            ),
        ]

        with (
            patch.object(
                optimizer,
                "_generate_param_grid",
                return_value=[sample_strategy_template.parameters for _ in range(3)],
            ),
            patch.object(
                optimizer,
                "_create_walk_forward_windows",
                return_value=[
                    ValidationWindow(
                        train_start=date(2023, 1, 1),
                        train_end=date(2023, 6, 30),
                        val_start=date(2023, 7, 1),
                        val_end=date(2023, 12, 31),
                    )
                ],
            ),
            patch.object(
                optimizer,
                "_run_backtest_for_params",
                side_effect=mock_backtest_results,
            ),
        ):
            result = await optimizer.optimize_strategy_parameters(
                symbol=symbol,
                strategy_template=sample_strategy_template,
                lookback_days=365,
                max_combinations=3,
            )

        # Verify result structure
        assert isinstance(result, OptimizedStrategyConfig)
        assert result.strategy_type == "momentum"
        assert result.avg_sharpe == 1.5  # Best Sharpe from mocks
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0
        assert len(result.optimization_metrics) == 3

    @pytest.mark.asyncio
    async def test_optimize_strategy_rejects_poor_strategies(
        self, optimizer, sample_strategy_template
    ):
        """Test optimization rejects strategies with poor metrics."""
        symbol = "WEAK"

        # Mock backtest results with poor performance
        poor_backtest = BacktestMetrics(
            sharpe_ratio=0.3,  # Poor Sharpe
            win_rate=0.42,  # Low win rate
            max_drawdown=0.35,  # High drawdown
            total_return=0.05,
            num_trades=20,
            profit_factor=1.1,
        )

        with (
            patch.object(
                optimizer,
                "_generate_param_grid",
                return_value=[sample_strategy_template.parameters],
            ),
            patch.object(
                optimizer,
                "_create_walk_forward_windows",
                return_value=[
                    ValidationWindow(
                        train_start=date(2023, 1, 1),
                        train_end=date(2023, 6, 30),
                        val_start=date(2023, 7, 1),
                        val_end=date(2023, 12, 31),
                    )
                ],
            ),
            patch.object(optimizer, "_run_backtest_for_params", return_value=poor_backtest),
            pytest.raises(ValueError, match="No viable strategies found|insufficient"),
        ):
            await optimizer.optimize_strategy_parameters(
                symbol=symbol, strategy_template=sample_strategy_template, lookback_days=365
            )

    @pytest.mark.asyncio
    async def test_optimize_strategy_handles_multiple_windows(
        self, optimizer, sample_strategy_template
    ):
        """Test optimization across multiple validation windows."""
        symbol = "AAPL"

        # Create multiple validation windows
        windows = [
            ValidationWindow(
                train_start=date(2023, 1, 1),
                train_end=date(2023, 3, 31),
                val_start=date(2023, 4, 1),
                val_end=date(2023, 6, 30),
            ),
            ValidationWindow(
                train_start=date(2023, 4, 1),
                train_end=date(2023, 6, 30),
                val_start=date(2023, 7, 1),
                val_end=date(2023, 9, 30),
            ),
            ValidationWindow(
                train_start=date(2023, 7, 1),
                train_end=date(2023, 9, 30),
                val_start=date(2023, 10, 1),
                val_end=date(2023, 12, 31),
            ),
        ]

        good_backtest = BacktestMetrics(
            sharpe_ratio=1.4,
            win_rate=0.58,
            max_drawdown=0.16,
            total_return=0.25,
            num_trades=10,
            profit_factor=1.9,
        )

        with (
            patch.object(
                optimizer,
                "_generate_param_grid",
                return_value=[sample_strategy_template.parameters],
            ),
            patch.object(optimizer, "_create_walk_forward_windows", return_value=windows),
            patch.object(optimizer, "_run_backtest_for_params", return_value=good_backtest),
        ):
            result = await optimizer.optimize_strategy_parameters(
                symbol=symbol, strategy_template=sample_strategy_template, lookback_days=365
            )

        # Should have tested across all windows (3 windows x 1 param combo = 3 runs)
        assert len(result.optimization_metrics) == 3

    def test_backtest_metrics_dataclass(self):
        """Test BacktestMetrics dataclass creation."""
        metrics = BacktestMetrics(
            sharpe_ratio=1.5,
            win_rate=0.60,
            max_drawdown=0.15,
            total_return=0.25,
            num_trades=10,
            profit_factor=2.0,
        )

        assert metrics.sharpe_ratio == 1.5
        assert metrics.win_rate == 0.60
        assert metrics.max_drawdown == 0.15
        assert metrics.total_return == 0.25
        assert metrics.num_trades == 10
        assert metrics.profit_factor == 2.0

    def test_validation_window_dataclass(self):
        """Test ValidationWindow dataclass creation."""
        window = ValidationWindow(
            train_start=date(2023, 1, 1),
            train_end=date(2023, 6, 30),
            val_start=date(2023, 7, 1),
            val_end=date(2023, 12, 31),
        )

        assert window.train_start == date(2023, 1, 1)
        assert window.train_end == date(2023, 6, 30)
        assert window.val_start == date(2023, 7, 1)
        assert window.val_end == date(2023, 12, 31)

    @pytest.mark.asyncio
    async def test_optimize_strategy_calculates_avg_metrics(
        self, optimizer, sample_strategy_template
    ):
        """Test that average metrics are calculated correctly."""
        symbol = "AAPL"

        # Different results for same params across windows
        mock_results = [
            BacktestMetrics(1.2, 0.55, 0.18, 0.22, 12, 1.8),
            BacktestMetrics(1.4, 0.60, 0.15, 0.28, 10, 2.0),
            BacktestMetrics(1.6, 0.62, 0.12, 0.30, 9, 2.2),
        ]

        with (
            patch.object(
                optimizer,
                "_generate_param_grid",
                return_value=[sample_strategy_template.parameters],
            ),
            patch.object(
                optimizer,
                "_create_walk_forward_windows",
                return_value=[
                    ValidationWindow(
                        date(2023, i, 1),
                        date(2023, i + 2, 28),
                        date(2023, i + 3, 1),
                        date(2023, i + 5, 30),
                    )
                    for i in range(1, 8, 3)
                ],
            ),
            patch.object(optimizer, "_run_backtest_for_params", side_effect=mock_results),
        ):
            result = await optimizer.optimize_strategy_parameters(
                symbol=symbol, strategy_template=sample_strategy_template, lookback_days=365
            )

        # Average Sharpe should be mean of [1.2, 1.4, 1.6] = 1.4
        assert abs(result.avg_sharpe - 1.4) < 0.01

        # Average win rate should be mean of [0.55, 0.60, 0.62] ≈ 0.59
        assert abs(result.avg_win_rate - 0.59) < 0.01

    @pytest.mark.asyncio
    async def test_optimize_strategy_confidence_based_on_metrics(
        self, optimizer, sample_strategy_template
    ):
        """Test that confidence score reflects backtest quality."""
        symbol = "AAPL"

        # Excellent metrics should yield high confidence
        excellent_backtest = BacktestMetrics(
            sharpe_ratio=2.5,
            win_rate=0.70,
            max_drawdown=0.08,
            total_return=0.45,
            num_trades=15,
            profit_factor=3.0,
        )

        with (
            patch.object(
                optimizer,
                "_generate_param_grid",
                return_value=[sample_strategy_template.parameters],
            ),
            patch.object(
                optimizer,
                "_create_walk_forward_windows",
                return_value=[
                    ValidationWindow(
                        date(2023, 1, 1), date(2023, 6, 30), date(2023, 7, 1), date(2023, 12, 31)
                    )
                ],
            ),
            patch.object(optimizer, "_run_backtest_for_params", return_value=excellent_backtest),
        ):
            result = await optimizer.optimize_strategy_parameters(
                symbol=symbol, strategy_template=sample_strategy_template, lookback_days=365
            )

        # High Sharpe + high win rate should yield confidence > 0.8
        assert result.confidence >= 0.8
