"""Additional strategy implementations for backtesting.

Implements three distinct strategies following the Strategy protocol from replay.py:

1. MomentumStrategy: Rides intermediate-term momentum with multi-horizon confirmation
2. MeanReversionStrategy: Quick oversold bounces in uptrend context
3. TrendFollowingStrategy: Long-term trend following with trailing stops

Each strategy is tunable via __init__ parameters and can be used standalone
or combined in portfolio backtests.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from app.analytics.momentum import calculate_momentum, calculate_momentum_score
from app.backtest.replay import Position
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


class MomentumStrategy:
    """Momentum strategy riding intermediate-term trends.

    Entry conditions:
    - Price > SMA_50 (uptrend context)
    - RSI > 50 (bullish momentum)
    - MACD > 0 (positive momentum)
    - Momentum score >= min_momentum_score (from multi-horizon analysis)

    Exit conditions:
    - Price < SMA_50 (trend broken)
    - RSI < rsi_exit_threshold (momentum fading)
    - Holding period >= max_holding_days
    - Target profit hit
    - Stop loss hit
    """

    def __init__(
        self,
        storage: PortfolioStorage,
        min_momentum_score: int = 3,
        rsi_entry_threshold: float = 50.0,
        rsi_exit_threshold: float = 40.0,
        max_holding_days: int = 60,
        target_profit_pct: Decimal = Decimal("20.0"),
        stop_loss_pct: Decimal = Decimal("8.0"),
    ):
        """Initialize momentum strategy.

        Args:
            storage: Database storage for momentum calculations
            min_momentum_score: Minimum momentum score for entry (0-5 scale)
            rsi_entry_threshold: RSI must be above this for entry
            rsi_exit_threshold: RSI below this triggers exit
            max_holding_days: Maximum days to hold position
            target_profit_pct: Profit target percentage
            stop_loss_pct: Stop loss percentage
        """
        self.storage = storage
        self.min_momentum_score = min_momentum_score
        self.rsi_entry_threshold = rsi_entry_threshold
        self.rsi_exit_threshold = rsi_exit_threshold
        self.max_holding_days = max_holding_days
        self.target_profit_pct = target_profit_pct
        self.stop_loss_pct = stop_loss_pct

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        """Determine if strategy should enter position.

        Requires:
        - Price > SMA_50
        - RSI > rsi_entry_threshold
        - MACD > 0
        - Momentum score >= min_momentum_score
        """
        price = float(ohlcv.get("close", 0) or 0)
        sma_50 = float(indicators.get("sma_50", 0) or 0)
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        macd = float(indicators.get("macd", 0) or 0)

        # 1. Price above SMA_50 (uptrend)
        if sma_50 == 0 or price <= sma_50:
            return False

        # 2. RSI above threshold (bullish momentum)
        if rsi_14 < self.rsi_entry_threshold:
            return False

        # 3. MACD positive
        if macd <= 0:
            return False

        # 4. Multi-horizon momentum score
        momentum = calculate_momentum(self.storage, symbol, backtest_date)
        score, reasons = calculate_momentum_score(momentum)

        if score < self.min_momentum_score:
            return False

        logger.debug(
            f"ENTRY (MOMENTUM): {symbol} | Date: {backtest_date} | "
            f"Price ${price:.2f} > SMA50 ${sma_50:.2f} | "
            f"RSI {rsi_14:.1f} | MACD {macd:.2f} | "
            f"Momentum score {score}/{self.min_momentum_score} | "
            f"{', '.join(reasons[:2])}"
        )
        return True

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        """Determine if strategy should exit position.

        Exit conditions:
        1. Price < SMA_50 (trend broken)
        2. RSI < rsi_exit_threshold (momentum fading)
        3. Max holding period exceeded
        4. Target profit hit
        5. Stop loss hit
        """
        current_price = Decimal(str(ohlcv["close"]))
        holding_days = (backtest_date - position.entry_date).days

        # Calculate return
        return_pct = (current_price - position.entry_price) / position.entry_price * Decimal("100")

        # 1. Target profit
        if return_pct >= self.target_profit_pct:
            logger.debug(
                f"EXIT (TARGET): {position.symbol} | "
                f"Return {return_pct:.2f}% >= {self.target_profit_pct}%"
            )
            return (True, "target")

        # 2. Stop loss
        if return_pct <= -self.stop_loss_pct:
            logger.debug(
                f"EXIT (STOP): {position.symbol} | "
                f"Return {return_pct:.2f}% <= -{self.stop_loss_pct}%"
            )
            return (True, "stop")

        # 3. Max holding period
        if holding_days >= self.max_holding_days:
            logger.debug("exit_time", symbol=position.symbol, holding_days=holding_days)
            return (True, "time")

        # 4. Trend broken (price < SMA_50)
        price = float(ohlcv.get("close", 0) or 0)
        sma_50 = float(indicators.get("sma_50", 0) or 0)
        if sma_50 > 0 and price < sma_50:
            logger.debug(
                f"EXIT (SIGNAL): {position.symbol} | Price ${price:.2f} < SMA50 ${sma_50:.2f}"
            )
            return (True, "signal")

        # 5. RSI fading
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        if rsi_14 < self.rsi_exit_threshold:
            logger.debug(
                f"EXIT (SIGNAL): {position.symbol} | RSI {rsi_14:.1f} < {self.rsi_exit_threshold}"
            )
            return (True, "signal")

        return (False, "")


class MeanReversionStrategy:
    """Mean reversion strategy for oversold bounces.

    Entry conditions:
    - RSI < rsi_oversold (default 30, oversold)
    - Price > SMA_200 (uptrend context to avoid falling knives)
    - Volume >= volume_threshold * average (sufficient interest)

    Exit conditions:
    - RSI > rsi_exit (default 50, back to neutral)
    - Target profit hit (quick +5% default)
    - Stop loss hit (tight -3% default)
    - Max holding period (short 10 days default)

    Philosophy: Quick tactical trades capturing oversold bounces in strong stocks.
    Target high win rate with tight stops.
    """

    def __init__(
        self,
        rsi_oversold: float = 30.0,
        rsi_exit: float = 50.0,
        volume_threshold: float = 0.8,
        target_profit_pct: Decimal = Decimal("5.0"),
        stop_loss_pct: Decimal = Decimal("3.0"),
        max_holding_days: int = 10,
    ):
        """Initialize mean reversion strategy.

        Args:
            rsi_oversold: RSI threshold for oversold entry
            rsi_exit: RSI level to exit (back to neutral)
            volume_threshold: Minimum volume as fraction of average
            target_profit_pct: Quick profit target
            stop_loss_pct: Tight stop loss
            max_holding_days: Short holding period
        """
        self.rsi_oversold = rsi_oversold
        self.rsi_exit = rsi_exit
        self.volume_threshold = volume_threshold
        self.target_profit_pct = target_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_holding_days = max_holding_days

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        """Determine if strategy should enter position.

        Requires:
        - RSI < rsi_oversold (oversold)
        - Price > SMA_200 (uptrend context)
        - Volume >= volume_threshold * average
        """
        price = float(ohlcv.get("close", 0) or 0)
        volume = float(ohlcv.get("volume", 0) or 0)
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        sma_200 = float(indicators.get("sma_200", 0) or 0)
        volume_avg = float(indicators.get("volume_avg_20", 0) or 0)

        # 1. RSI oversold
        if rsi_14 >= self.rsi_oversold:
            return False

        # 2. Uptrend context (price > SMA_200)
        if sma_200 == 0 or price <= sma_200:
            return False

        # 3. Sufficient volume
        if volume_avg > 0 and volume < self.volume_threshold * volume_avg:
            return False

        vol_pct = (volume / volume_avg * 100) if volume_avg > 0 else 0
        logger.debug(
            f"ENTRY (MEAN_REV): {symbol} | Date: {backtest_date} | "
            f"RSI {rsi_14:.1f} < {self.rsi_oversold} | "
            f"Price ${price:.2f} > SMA200 ${sma_200:.2f} | "
            f"Volume {vol_pct:.0f}% of avg"
        )
        return True

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        """Determine if strategy should exit position.

        Exit conditions:
        1. RSI > rsi_exit (back to neutral)
        2. Target profit hit
        3. Stop loss hit
        4. Max holding period
        """
        current_price = Decimal(str(ohlcv["close"]))
        holding_days = (backtest_date - position.entry_date).days

        # Calculate return
        return_pct = (current_price - position.entry_price) / position.entry_price * Decimal("100")

        # 1. Target profit (quick exit)
        if return_pct >= self.target_profit_pct:
            logger.debug(
                f"EXIT (TARGET): {position.symbol} | "
                f"Return {return_pct:.2f}% >= {self.target_profit_pct}%"
            )
            return (True, "target")

        # 2. Stop loss (tight)
        if return_pct <= -self.stop_loss_pct:
            logger.debug(
                f"EXIT (STOP): {position.symbol} | "
                f"Return {return_pct:.2f}% <= -{self.stop_loss_pct}%"
            )
            return (True, "stop")

        # 3. RSI back to neutral
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        if rsi_14 >= self.rsi_exit:
            logger.debug(
                f"EXIT (SIGNAL): {position.symbol} | RSI {rsi_14:.1f} >= {self.rsi_exit} (neutral)"
            )
            return (True, "signal")

        # 4. Max holding period
        if holding_days >= self.max_holding_days:
            logger.debug("exit_time", symbol=position.symbol, holding_days=holding_days)
            return (True, "time")

        return (False, "")


class TrendFollowingStrategy:
    """Trend following strategy for long-term trend trades.

    Entry conditions:
    - Price > SMA_20 > SMA_50 > SMA_200 (all SMAs aligned, strong uptrend)
    - Volume >= volume_threshold * average (sufficient interest)
    - MACD > 0 (confirms momentum)

    Exit conditions:
    - Price < SMA_20 (trend broken)
    - ATR-based trailing stop hit
    - Max holding period exceeded

    Philosophy: Ride strong trends with trailing stops. No fixed profit target,
    let winners run until trend breaks. Longer holding periods typical.
    """

    def __init__(
        self,
        volume_threshold: float = 0.7,
        trailing_stop_atr_multiplier: Decimal = Decimal("2.5"),
        max_holding_days: int = 120,
    ):
        """Initialize trend following strategy.

        Args:
            volume_threshold: Minimum volume as fraction of average
            trailing_stop_atr_multiplier: Trailing stop distance in ATR multiples
            max_holding_days: Maximum days to hold position
        """
        self.volume_threshold = volume_threshold
        self.trailing_stop_atr_multiplier = trailing_stop_atr_multiplier
        self.max_holding_days = max_holding_days

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        """Determine if strategy should enter position.

        Requires:
        - Price > SMA_20 > SMA_50 > SMA_200 (perfect alignment)
        - MACD > 0
        - Volume >= volume_threshold * average
        """
        price = float(ohlcv.get("close", 0) or 0)
        volume = float(ohlcv.get("volume", 0) or 0)
        sma_20 = float(indicators.get("sma_20", 0) or 0)
        sma_50 = float(indicators.get("sma_50", 0) or 0)
        sma_200 = float(indicators.get("sma_200", 0) or 0)
        macd = float(indicators.get("macd", 0) or 0)
        volume_avg = float(indicators.get("volume_avg_20", 0) or 0)

        # 1. Perfect SMA alignment
        if sma_20 == 0 or sma_50 == 0 or sma_200 == 0:
            return False

        if not (price > sma_20 > sma_50 > sma_200):
            return False

        # 2. MACD positive
        if macd <= 0:
            return False

        # 3. Sufficient volume
        if volume_avg > 0 and volume < self.volume_threshold * volume_avg:
            return False

        logger.debug(
            f"ENTRY (TREND): {symbol} | Date: {backtest_date} | "
            f"Price ${price:.2f} > SMA20 ${sma_20:.2f} > "
            f"SMA50 ${sma_50:.2f} > SMA200 ${sma_200:.2f} | "
            f"MACD {macd:.2f}"
        )
        return True

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        """Determine if strategy should exit position.

        Exit conditions:
        1. Price < SMA_20 (trend broken)
        2. ATR-based trailing stop hit (price falls 2.5x ATR from peak)
        3. Max holding period exceeded
        """
        current_price = Decimal(str(ohlcv["close"]))
        holding_days = (backtest_date - position.entry_date).days

        # 1. Max holding period
        if holding_days >= self.max_holding_days:
            logger.debug("exit_time", symbol=position.symbol, holding_days=holding_days)
            return (True, "time")

        # 2. Trend broken (price < SMA_20)
        price = float(ohlcv.get("close", 0) or 0)
        sma_20 = float(indicators.get("sma_20", 0) or 0)
        if sma_20 > 0 and price < sma_20:
            logger.debug(
                f"EXIT (SIGNAL): {position.symbol} | Price ${price:.2f} < SMA20 ${sma_20:.2f}"
            )
            return (True, "signal")

        # 3. ATR-based trailing stop
        # Stop is positioned at (max_favorable_price - ATR * multiplier)
        # We track max_favorable_pct in Position, convert back to price
        atr = Decimal(str(indicators.get("atr_14", 0.0)))

        if atr > 0:
            # Calculate peak price from entry_price and max_favorable_pct
            peak_price = position.entry_price * (
                Decimal("1.0") + position.max_favorable_pct / Decimal("100.0")
            )

            # Trailing stop is ATR distance below peak
            trailing_stop = peak_price - (self.trailing_stop_atr_multiplier * atr)

            # Only trigger if we've made some profit (peak > entry)
            if peak_price > position.entry_price and current_price <= trailing_stop:
                logger.debug(
                    f"EXIT (STOP): {position.symbol} | "
                    f"Trailing stop: ${current_price:.2f} <= ${trailing_stop:.2f} "
                    f"(Peak ${peak_price:.2f} - {self.trailing_stop_atr_multiplier}x ATR)"
                )
                return (True, "stop")

        return (False, "")
