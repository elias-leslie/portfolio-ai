"""Tests for optimizer metrics calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

import pytest

from app.strategies.optimizer import StrategyOptimizer


@dataclass
class MockTrade:
    """Mock trade for testing."""

    pnl: Decimal | None = None
    pnl_pct: Decimal | None = None


@dataclass
class MockEquity:
    """Mock equity snapshot for testing."""

    equity: Decimal
    drawdown_pct: Decimal = Decimal("0.0")


@dataclass
class MockBacktestState:
    """Mock BacktestState for testing metrics calculation."""

    cash: Decimal = Decimal("10000")
    trades: list[MockTrade] = field(default_factory=list)
    equity_curve: list[MockEquity] = field(default_factory=list)
    peak_equity: Decimal = Decimal("10000")


class TestCalculateMetricsFromState:
    """Tests for _calculate_metrics_from_state method."""

    def test_no_trades_returns_zero_metrics(self) -> None:
        """Test empty trades list returns zero metrics."""
        optimizer = StrategyOptimizer()
        state = MockBacktestState(trades=[], equity_curve=[])

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        assert metrics.num_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.total_return == 0.0
        assert metrics.profit_factor == 0.0

    def test_all_winning_trades(self) -> None:
        """Test win rate calculation with all winning trades."""
        optimizer = StrategyOptimizer()
        trades = [
            MockTrade(pnl=Decimal("100")),
            MockTrade(pnl=Decimal("200")),
            MockTrade(pnl=Decimal("150")),
        ]
        state = MockBacktestState(trades=trades, equity_curve=[])

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        assert metrics.num_trades == 3
        assert metrics.win_rate == 1.0
        # No losses means profit_factor = 2.0 (default for all wins)
        assert metrics.profit_factor == 2.0

    def test_mixed_wins_and_losses(self) -> None:
        """Test win rate and profit factor with mixed results."""
        optimizer = StrategyOptimizer()
        trades = [
            MockTrade(pnl=Decimal("200")),  # Win
            MockTrade(pnl=Decimal("-100")),  # Loss
            MockTrade(pnl=Decimal("150")),  # Win
            MockTrade(pnl=Decimal("-50")),  # Loss
        ]
        state = MockBacktestState(trades=trades, equity_curve=[])

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        assert metrics.num_trades == 4
        assert metrics.win_rate == 0.5  # 2/4
        # Profit factor = 350 / 150 = 2.33...
        assert metrics.profit_factor == pytest.approx(2.333, rel=0.01)

    def test_equity_curve_total_return(self) -> None:
        """Test total return calculation from equity curve."""
        optimizer = StrategyOptimizer()
        equity_curve = [
            MockEquity(equity=Decimal("10000")),
            MockEquity(equity=Decimal("10500")),
            MockEquity(equity=Decimal("11000")),
        ]
        state = MockBacktestState(
            trades=[MockTrade(pnl=Decimal("1000"))],
            equity_curve=equity_curve,
        )

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        # Total return = (11000 - 10000) / 10000 = 0.10
        assert metrics.total_return == pytest.approx(0.10, rel=0.01)

    def test_equity_curve_max_drawdown(self) -> None:
        """Test max drawdown from equity curve."""
        optimizer = StrategyOptimizer()
        equity_curve = [
            MockEquity(equity=Decimal("10000"), drawdown_pct=Decimal("0")),
            MockEquity(equity=Decimal("11000"), drawdown_pct=Decimal("0")),
            MockEquity(equity=Decimal("9500"), drawdown_pct=Decimal("13.64")),  # -13.64%
            MockEquity(equity=Decimal("10200"), drawdown_pct=Decimal("7.27")),
        ]
        state = MockBacktestState(
            trades=[MockTrade(pnl=Decimal("200"))],
            equity_curve=equity_curve,
        )

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        # Max drawdown = 13.64 (from the curve)
        assert metrics.max_drawdown == pytest.approx(13.64, rel=0.01)

    def test_sharpe_ratio_calculation(self) -> None:
        """Test Sharpe ratio from equity curve returns."""
        optimizer = StrategyOptimizer()
        # Create a simple uptrend for predictable returns
        equity_curve = [
            MockEquity(equity=Decimal("10000")),
            MockEquity(equity=Decimal("10100")),  # +1%
            MockEquity(equity=Decimal("10200")),  # +0.99%
            MockEquity(equity=Decimal("10300")),  # +0.98%
            MockEquity(equity=Decimal("10400")),  # +0.97%
        ]
        state = MockBacktestState(
            trades=[MockTrade(pnl=Decimal("400"))],
            equity_curve=equity_curve,
        )

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        # Should have a positive Sharpe ratio for consistent gains
        assert metrics.sharpe_ratio > 0

    def test_none_pnl_excluded_from_calculation(self) -> None:
        """Test trades with None PnL are excluded from win/loss calc."""
        optimizer = StrategyOptimizer()
        trades = [
            MockTrade(pnl=Decimal("100")),  # Win
            MockTrade(pnl=None),  # Excluded
            MockTrade(pnl=Decimal("-50")),  # Loss
        ]
        state = MockBacktestState(trades=trades, equity_curve=[])

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        assert metrics.num_trades == 3  # All trades counted
        # Win rate only considers trades with pnl
        # 1 win out of 2 with pnl = 0.5
        assert metrics.win_rate == pytest.approx(0.333, rel=0.01)

    def test_single_equity_point(self) -> None:
        """Test with only one equity point (can't calculate Sharpe)."""
        optimizer = StrategyOptimizer()
        equity_curve = [MockEquity(equity=Decimal("10000"))]
        state = MockBacktestState(
            trades=[MockTrade(pnl=Decimal("100"))],
            equity_curve=equity_curve,
        )

        metrics = optimizer._calculate_metrics_from_state(state)  # type: ignore[arg-type]

        # Can't calculate Sharpe with 1 point
        assert metrics.sharpe_ratio == 0.0
        # Total return = 0 (start = end)
        assert metrics.total_return == 0.0
