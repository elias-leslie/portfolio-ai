"""Unit tests for MeanReversionStrategy."""

from datetime import date
from decimal import Decimal

import pytest

from app.backtest.additional_strategies import MeanReversionStrategy
from app.backtest.replay import Position


class TestMeanReversionStrategyEntry:
    """Tests for MeanReversionStrategy.should_enter."""

    @pytest.fixture
    def strategy(self) -> MeanReversionStrategy:
        """Create strategy with default parameters."""
        return MeanReversionStrategy(
            rsi_oversold=30.0,
            rsi_exit=50.0,
            volume_threshold=0.8,
            target_profit_pct=Decimal("5.0"),
            stop_loss_pct=Decimal("3.0"),
            max_holding_days=10,
        )

    @pytest.fixture
    def valid_entry_indicators(self) -> dict:
        """Indicators that satisfy all entry conditions."""
        return {
            "rsi_14": 25.0,  # Oversold (< 30)
            "sma_200": 95.0,  # Below price
            "volume_avg_20": 1_000_000.0,
        }

    @pytest.fixture
    def valid_entry_ohlcv(self) -> dict:
        """OHLCV that satisfies all entry conditions."""
        return {
            "open": 100.0,
            "high": 102.0,
            "low": 98.0,
            "close": 100.0,
            "volume": 900_000.0,  # 90% of average (>80% threshold)
        }

    def test_entry_signal_when_all_conditions_met(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should enter when RSI < 30, price > SMA_200, and volume >= 80%."""
        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=valid_entry_indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is True

    def test_no_entry_when_rsi_above_threshold(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when RSI >= 30 (not oversold)."""
        indicators = valid_entry_indicators.copy()
        indicators["rsi_14"] = 35.0  # Above oversold threshold

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False

    def test_no_entry_when_rsi_exactly_at_threshold(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when RSI = 30 (boundary condition)."""
        indicators = valid_entry_indicators.copy()
        indicators["rsi_14"] = 30.0

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False

    def test_no_entry_when_price_below_sma_200(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when price <= SMA_200 (downtrend)."""
        indicators = valid_entry_indicators.copy()
        indicators["sma_200"] = 105.0  # Above price

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False

    def test_no_entry_when_price_equals_sma_200(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when price = SMA_200 (boundary condition)."""
        indicators = valid_entry_indicators.copy()
        indicators["sma_200"] = 100.0  # Equals price

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False

    def test_no_entry_when_sma_200_is_zero(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when SMA_200 is missing or zero."""
        indicators = valid_entry_indicators.copy()
        indicators["sma_200"] = 0.0

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False

    def test_no_entry_when_volume_below_threshold(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should not enter when volume < 80% of average."""
        ohlcv = valid_entry_ohlcv.copy()
        ohlcv["volume"] = 700_000.0  # 70% of average (below 80% threshold)

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=valid_entry_indicators,
            ohlcv=ohlcv,
        )
        assert result is False

    def test_entry_when_volume_exactly_at_threshold(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should enter when volume = 80% of average (boundary condition)."""
        ohlcv = valid_entry_ohlcv.copy()
        ohlcv["volume"] = 800_000.0  # Exactly 80% of average

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=valid_entry_indicators,
            ohlcv=ohlcv,
        )
        assert result is True

    def test_entry_when_volume_avg_is_zero(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_indicators: dict,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should enter when volume_avg is 0 (skip volume check)."""
        indicators = valid_entry_indicators.copy()
        indicators["volume_avg_20"] = 0.0

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is True

    def test_entry_with_custom_parameters(self) -> None:
        """Should respect custom RSI and volume thresholds."""
        strategy = MeanReversionStrategy(
            rsi_oversold=35.0,  # More aggressive
            volume_threshold=0.5,  # Lower volume requirement
        )

        indicators = {
            "rsi_14": 33.0,  # Would fail default (30), passes custom (35)
            "sma_200": 90.0,
            "volume_avg_20": 1_000_000.0,
        }

        ohlcv = {
            "close": 100.0,
            "volume": 600_000.0,  # 60% (would fail 80%, passes 50%)
        }

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=ohlcv,
        )
        assert result is True

    def test_handles_missing_indicator_fields(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should handle missing indicator fields gracefully."""
        indicators = {
            "rsi_14": 25.0,
            # Missing sma_200, volume_avg_20
        }

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False  # Missing SMA_200 fails entry

    def test_handles_none_indicator_values(
        self,
        strategy: MeanReversionStrategy,
        valid_entry_ohlcv: dict,
    ) -> None:
        """Should handle None indicator values gracefully."""
        indicators = {
            "rsi_14": None,
            "sma_200": None,
            "volume_avg_20": None,
        }

        result = strategy.should_enter(
            symbol="AAPL",
            backtest_date=date(2024, 1, 15),
            indicators=indicators,
            ohlcv=valid_entry_ohlcv,
        )
        assert result is False


class TestMeanReversionStrategyExit:
    """Tests for MeanReversionStrategy.should_exit."""

    @pytest.fixture
    def strategy(self) -> MeanReversionStrategy:
        """Create strategy with default parameters."""
        return MeanReversionStrategy(
            rsi_oversold=30.0,
            rsi_exit=50.0,
            volume_threshold=0.8,
            target_profit_pct=Decimal("5.0"),
            stop_loss_pct=Decimal("3.0"),
            max_holding_days=10,
        )

    @pytest.fixture
    def position(self) -> Position:
        """Create test position."""
        return Position(
            symbol="AAPL",
            shares=100,
            entry_price=Decimal("100.0"),
            entry_date=date(2024, 1, 1),
        )

    @pytest.fixture
    def neutral_indicators(self) -> dict:
        """Indicators that don't trigger signal exit."""
        return {
            "rsi_14": 45.0,  # Below exit threshold (50)
        }

    @pytest.fixture
    def neutral_ohlcv(self) -> dict:
        """OHLCV with no profit/loss."""
        return {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,  # Break even
            "volume": 1_000_000.0,
        }

    def test_exit_when_rsi_above_threshold(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_ohlcv: dict,
    ) -> None:
        """Should exit when RSI >= 50 (back to neutral)."""
        indicators = {"rsi_14": 52.0}

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is True
        assert reason == "signal"

    def test_exit_when_rsi_exactly_at_threshold(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_ohlcv: dict,
    ) -> None:
        """Should exit when RSI = 50 (boundary condition)."""
        indicators = {"rsi_14": 50.0}

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is True
        assert reason == "signal"

    def test_no_exit_when_rsi_below_threshold(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
        neutral_ohlcv: dict,
    ) -> None:
        """Should not exit when RSI < 50."""
        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=neutral_indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is False
        assert reason == ""

    def test_exit_when_target_profit_hit(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
    ) -> None:
        """Should exit when profit >= 5% target."""
        ohlcv = {
            "close": 105.5,  # +5.5% profit (above 5% target)
        }

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=neutral_indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "target"

    def test_exit_when_exactly_at_target_profit(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
    ) -> None:
        """Should exit when profit = 5% target (boundary condition)."""
        ohlcv = {
            "close": 105.0,  # Exactly +5% profit
        }

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=neutral_indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "target"

    def test_exit_when_stop_loss_hit(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
    ) -> None:
        """Should exit when loss >= 3% stop."""
        ohlcv = {
            "close": 96.5,  # -3.5% loss (below -3% stop)
        }

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=neutral_indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "stop"

    def test_exit_when_exactly_at_stop_loss(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
    ) -> None:
        """Should exit when loss = -3% stop (boundary condition)."""
        ohlcv = {
            "close": 97.0,  # Exactly -3% loss
        }

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=neutral_indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "stop"

    def test_exit_when_max_holding_period_reached(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
        neutral_ohlcv: dict,
    ) -> None:
        """Should exit when holding period >= 10 days."""
        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 12),  # 11 days after entry (2024-01-01)
            indicators=neutral_indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is True
        assert reason == "time"

    def test_exit_when_exactly_at_max_holding_period(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
        neutral_ohlcv: dict,
    ) -> None:
        """Should exit when holding period = 10 days (boundary condition)."""
        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 11),  # Exactly 10 days after entry
            indicators=neutral_indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is True
        assert reason == "time"

    def test_no_exit_before_max_holding_period(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_indicators: dict,
        neutral_ohlcv: dict,
    ) -> None:
        """Should not exit when holding period < 10 days."""
        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 10),  # 9 days after entry
            indicators=neutral_indicators,
            ohlcv=neutral_ohlcv,
        )

        assert should_exit is False
        assert reason == ""

    def test_exit_priority_target_before_signal(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
    ) -> None:
        """Target profit should be checked before RSI signal."""
        indicators = {"rsi_14": 55.0}  # Would trigger signal exit
        ohlcv = {"close": 106.0}  # +6% profit (would trigger target exit)

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "target"  # Target takes priority

    def test_exit_priority_stop_before_signal(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
    ) -> None:
        """Stop loss should be checked before RSI signal."""
        indicators = {"rsi_14": 55.0}  # Would trigger signal exit
        ohlcv = {"close": 95.0}  # -5% loss (would trigger stop exit)

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "stop"  # Stop takes priority

    def test_exit_priority_signal_before_time(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
    ) -> None:
        """RSI signal should be checked before max holding period."""
        indicators = {"rsi_14": 55.0}  # Triggers signal exit
        ohlcv = {"close": 100.0}

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 12),  # 11 days (would trigger time exit)
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "signal"  # Signal takes priority over time

    def test_with_custom_parameters(self) -> None:
        """Should respect custom exit parameters."""
        strategy = MeanReversionStrategy(
            rsi_exit=60.0,  # Higher exit threshold
            target_profit_pct=Decimal("10.0"),  # Higher target
            stop_loss_pct=Decimal("5.0"),  # Wider stop
            max_holding_days=5,  # Shorter holding period
        )

        position = Position(
            symbol="AAPL",
            shares=100,
            entry_price=Decimal("100.0"),
            entry_date=date(2024, 1, 1),
        )

        # Test custom RSI threshold
        indicators = {"rsi_14": 55.0}  # Would exit default (50), not custom (60)
        ohlcv = {"close": 100.0}

        should_exit, _ = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 3),
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is False

        # Test custom target profit
        ohlcv = {"close": 107.0}  # +7% (would exit default 5%, not custom 10%)

        should_exit, _ = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 3),
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is False

        # Test custom stop loss
        ohlcv = {"close": 96.0}  # -4% (would exit default -3%, not custom -5%)

        should_exit, _ = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 3),
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is False

        # Test custom max holding
        ohlcv = {"close": 100.0}

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 7),  # 6 days (exits custom 5, not default 10)
            indicators=indicators,
            ohlcv=ohlcv,
        )

        assert should_exit is True
        assert reason == "time"

    def test_handles_missing_rsi_indicator(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_ohlcv: dict,
    ) -> None:
        """Should use default RSI value of 50 when missing."""
        indicators = {}  # Missing rsi_14

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=neutral_ohlcv,
        )

        # Default RSI of 50 triggers exit (>= threshold)
        assert should_exit is True
        assert reason == "signal"

    def test_handles_none_rsi_indicator(
        self,
        strategy: MeanReversionStrategy,
        position: Position,
        neutral_ohlcv: dict,
    ) -> None:
        """Should use default RSI value of 50 when None."""
        indicators = {"rsi_14": None}

        should_exit, reason = strategy.should_exit(
            position=position,
            backtest_date=date(2024, 1, 5),
            indicators=indicators,
            ohlcv=neutral_ohlcv,
        )

        # Default RSI of 50 triggers exit (>= threshold)
        assert should_exit is True
        assert reason == "signal"
