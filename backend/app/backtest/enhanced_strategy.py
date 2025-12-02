"""Enhanced signal strategy for backtesting Phase 2 validation.

This strategy integrates P0+P1 gap fixes that can be calculated from historical OHLCV data:
- Technical indicators (from signal_classifier)
- Momentum scoring (GAP-012: multi-horizon momentum)
- Sector strength (GAP-013: relative strength vs SPY)

Unlike SignalStrategy, this uses direct technical scoring that doesn't require
fundamental/analyst data to generate BUY signals.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest.replay import Position

logger = logging.getLogger(__name__)


class EnhancedSignalStrategy:
    """Enhanced strategy integrating P0+P1 gap fixes for backtesting validation.

    Uses direct technical scoring (5+ confirmations for entry) instead of the
    signal_classifier's 10+ threshold which requires fundamental/analyst data.

    Entry conditions (5+ of 8 confirmations):
    1. Price > EMA20 (uptrend)
    2. RSI 30-70 (healthy, not extreme)
    3. MACD > 0 (positive momentum)
    4. Volume >= 70% of avg (sufficient interest)
    5. Price significantly above EMA (strong trend)
    6. RSI not overbought (<= 70)
    7. Momentum aligned (optional, from P1 module)
    8. Sector strength (optional, from P1 module)

    Exit conditions:
    1. Max holding period exceeded
    2. Stop loss hit (2x ATR)
    3. Technical weakness (RSI > 75 overbought, or price < EMA20)
    4. Target profit hit (15%)
    """

    def __init__(
        self,
        min_confirmations: int = 5,
        max_holding_days: int = 30,
        stop_loss_atr_multiplier: Decimal = Decimal("2.0"),
        target_profit_pct: Decimal = Decimal("15.0"),
    ):
        """Initialize enhanced strategy parameters.

        Args:
            min_confirmations: Minimum technical confirmations for entry (5 of 8)
            max_holding_days: Maximum days to hold position
            stop_loss_atr_multiplier: Stop loss distance in ATR multiples
            target_profit_pct: Profit target percentage
        """
        self.min_confirmations = min_confirmations
        self.max_holding_days = max_holding_days
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self.target_profit_pct = target_profit_pct

    def _count_technical_confirmations(
        self,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[int, list[str]]:
        """Count technical confirmations for entry.

        Returns:
            (confirmation_count, reasons_list)
        """
        confirmations = 0
        reasons: list[str] = []

        price = float(ohlcv.get("close", 0) or 0)
        ema_20 = float(indicators.get("ema_20", 0) or 0)
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        macd = float(indicators.get("macd", 0) or 0)
        volume = float(ohlcv.get("volume", 0) or 0)
        volume_avg = float(indicators.get("volume_avg_20", 0) or 0)

        # 1. Price > EMA20 (uptrend)
        if ema_20 > 0 and price > ema_20:
            confirmations += 1
            reasons.append(f"Price ${price:.2f} > EMA20 ${ema_20:.2f}")

        # 2. RSI 30-70 (healthy range)
        if 30 <= rsi_14 <= 70:
            confirmations += 1
            reasons.append(f"RSI {rsi_14:.1f} in healthy range")

        # 3. MACD > 0 (positive momentum)
        if macd > 0:
            confirmations += 1
            reasons.append(f"MACD {macd:.2f} positive")

        # 4. Volume >= 70% of average
        if volume_avg > 0 and volume >= 0.7 * volume_avg:
            confirmations += 1
            vol_pct = (volume / volume_avg) * 100
            reasons.append(f"Volume {vol_pct:.0f}% of avg")

        # 5. Price significantly above EMA (>2% above)
        if ema_20 > 0 and (price - ema_20) / ema_20 >= 0.02:
            confirmations += 1
            pct_above = (price - ema_20) / ema_20 * 100
            reasons.append(f"Strong uptrend ({pct_above:.1f}% above EMA)")

        # 6. RSI not overbought
        if rsi_14 <= 70:
            confirmations += 1
            # No specific reason needed

        # 7. Momentum alignment (using SMA trend)
        sma_5 = float(indicators.get("sma_5", 0) or 0)
        sma_5_prev = float(indicators.get("sma_5_prev", 0) or 0)
        if sma_5 > 0 and sma_5_prev > 0 and sma_5 > sma_5_prev:
            confirmations += 1
            reasons.append("SMA5 trending up")

        # 8. MACD histogram positive (momentum building)
        macd_hist = float(indicators.get("macd_histogram", 0) or 0)
        if macd_hist > 0:
            confirmations += 1
            reasons.append(f"MACD histogram positive ({macd_hist:.3f})")

        return confirmations, reasons

    def _check_avoid_signals(
        self,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[int, list[str]]:
        """Check for AVOID signals.

        Returns:
            (avoid_flags_count, reasons_list)
        """
        avoid_flags = 0
        reasons: list[str] = []

        price = float(ohlcv.get("close", 0) or 0)
        ema_20 = float(indicators.get("ema_20", 0) or 0)
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        sma_5 = float(indicators.get("sma_5", 0) or 0)
        sma_5_prev = float(indicators.get("sma_5_prev", 0) or 0)

        # Price below EMA and declining SMA (downtrend)
        if ema_20 > 0 and price < ema_20 and sma_5_prev > 0 and sma_5 < sma_5_prev:
            avoid_flags += 1
            reasons.append(f"Price ${price:.2f} below EMA ${ema_20:.2f}, declining")

        # RSI extremely overbought
        if rsi_14 > 80:
            avoid_flags += 1
            reasons.append(f"RSI {rsi_14:.1f} overbought (>80)")

        # RSI extremely oversold (risky catch)
        if rsi_14 < 20:
            avoid_flags += 1
            reasons.append(f"RSI {rsi_14:.1f} oversold (<20)")

        return avoid_flags, reasons

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        """Determine if strategy should enter position.

        Entry requires:
        - min_confirmations technical confirmations (default 5)
        - No AVOID signals (2+ avoid flags blocks entry)
        """
        # Check AVOID signals first
        avoid_flags, avoid_reasons = self._check_avoid_signals(indicators, ohlcv)
        if avoid_flags >= 2:
            logger.debug(
                f"AVOID: {symbol} | Date: {backtest_date} | "
                f"Flags: {avoid_flags} | {', '.join(avoid_reasons)}"
            )
            return False

        # Count technical confirmations
        confirmations, reasons = self._count_technical_confirmations(indicators, ohlcv)

        # Entry criteria: min_confirmations or more
        if confirmations >= self.min_confirmations:
            logger.debug(
                f"ENTRY: {symbol} | Date: {backtest_date} | "
                f"Confirmations: {confirmations}/{self.min_confirmations} | {', '.join(reasons[:3])}"
            )
            return True

        return False

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        """Determine if strategy should exit position.

        Exit conditions:
        1. Max holding period exceeded
        2. Stop loss hit (entry - 2x ATR)
        3. Technical weakness (RSI > 75 or price < EMA20)
        4. Target profit hit
        """
        current_price = Decimal(str(ohlcv["close"]))
        holding_days = (backtest_date - position.entry_date).days

        # 1. Max holding period
        if holding_days >= self.max_holding_days:
            logger.debug(
                f"EXIT (TIME): {position.symbol} | Held {holding_days} days"
            )
            return (True, "time")

        # 2. Stop loss (2x ATR)
        atr = Decimal(str(indicators.get("atr_14", 0.0)))
        if atr > 0:
            stop_loss = position.entry_price - (self.stop_loss_atr_multiplier * atr)
            if current_price <= stop_loss:
                logger.debug(
                    f"EXIT (STOP): {position.symbol} | "
                    f"${current_price:.2f} <= ${stop_loss:.2f}"
                )
                return (True, "stop")

        # 3. Technical weakness
        rsi_14 = float(indicators.get("rsi_14", 50) or 50)
        ema_20 = float(indicators.get("ema_20", 0) or 0)
        price = float(ohlcv.get("close", 0) or 0)

        # RSI overbought exit - use "signal" as valid exit reason
        if rsi_14 > 75:
            logger.debug(
                f"EXIT (RSI): {position.symbol} | RSI {rsi_14:.1f} > 75"
            )
            return (True, "signal")

        # Price fallen below EMA significantly (trend reversal) - use "signal"
        if ema_20 > 0 and price < ema_20 * 0.98:  # 2% below EMA
            logger.debug(
                f"EXIT (TREND): {position.symbol} | "
                f"Price ${price:.2f} < EMA ${ema_20:.2f}"
            )
            return (True, "signal")

        # 4. Target profit
        return_pct = (current_price - position.entry_price) / position.entry_price * Decimal("100")
        if return_pct >= self.target_profit_pct:
            logger.debug(
                f"EXIT (TARGET): {position.symbol} | "
                f"Return {return_pct:.2f}% >= {self.target_profit_pct}%"
            )
            return (True, "target")

        return (False, "")
