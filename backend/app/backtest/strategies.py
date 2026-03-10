"""
Strategy implementations for backtesting.

Phase A MVP: SignalStrategy (wraps signal_classifier.py for BUY/HOLD/AVOID logic)
Phase B: Custom strategies with parameter optimization and walk-forward validation
"""

import logging
from datetime import date
from decimal import Decimal

from app.backtest.replay import Position
from app.watchlist.models import SignalType
from app.watchlist.signal_classifier import classify_signal

logger = logging.getLogger(__name__)


class SignalStrategy:
    """Signal-based strategy using existing signal_classifier.py logic.

    Entry conditions:
    - classify_signal() returns BUY with strength >= min_signal_strength
    - Sufficient cash to enter position

    Exit conditions:
    - Target hit (from signal classification profit target)
    - Stop loss hit (entry_price - stop_loss_atr_multiplier * ATR)
    - AVOID signal (strategy invalidated)
    - Max holding period exceeded

    Phase A MVP limitations:
    - No news sentiment (only 8 days of historical news)
    - No company health ratings (not historical)
    - Technical indicators only (RSI, MACD, EMA, volume)
    """

    def __init__(
        self,
        min_signal_strength: int = 7,
        max_holding_days: int = 60,
        stop_loss_atr_multiplier: Decimal = Decimal("2.0"),
        fundamental_data: dict[str, object] | None = None,
    ):
        """Initialize strategy parameters.

        Args:
            min_signal_strength: Minimum signal strength (1-10) to enter position
            max_holding_days: Maximum days to hold position before force exit
            stop_loss_atr_multiplier: Stop loss distance in ATR multiples
            fundamental_data: Real fundamental data from ResearchInsights including:
                - company_health: Company health rating
                - news_sentiment: News sentiment score (-1 to 1)
                - profit_margin: Profit margin as decimal
                - revenue_growth: Revenue growth as decimal
                - debt_to_equity: Debt-to-equity ratio
                - recommendation_mean: Analyst recommendation (1-5)
                - analyst_buy_pct: Percentage of analysts with buy rating (0-1)
        """
        self.min_signal_strength = min_signal_strength
        self.max_holding_days = max_holding_days
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self.fundamental_data = fundamental_data or {}

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, float],
        ohlcv: dict[str, float],
    ) -> bool:
        """Determine if strategy should enter position.

        Args:
            symbol: Stock symbol
            backtest_date: Current backtest date
            indicators: Technical indicators (RSI, MACD, EMA, etc.)
            ohlcv: OHLCV data for current date

        Returns:
            True if should enter position
        """
        # Build input dict for classify_signal (expects single dict with all values)
        # Use real fundamental data if provided via self.fundamental_data, else None
        signal_inputs: dict[str, object] = {
            "price": float(ohlcv["close"]),
            "ema_20": indicators.get("ema_20", 0.0),
            "sma_5": indicators.get("sma_5", 0.0),
            "sma_5_prev": indicators.get("sma_5_prev", 0.0),
            "rsi_14": indicators.get("rsi_14", 50.0),
            "macd": indicators.get("macd", 0.0),
            "volume": float(ohlcv.get("volume", 0)),
            "volume_avg_20": indicators.get("volume_avg_20", 0.0),
            # Use real fundamental data if available
            "company_health": self.fundamental_data.get("company_health")
            if self.fundamental_data
            else None,
            "news_sentiment": self.fundamental_data.get("news_sentiment")
            if self.fundamental_data
            else None,
            "earnings_days_away": None,
            "profit_margin": self.fundamental_data.get("profit_margin")
            if self.fundamental_data
            else None,
            "revenue_growth": self.fundamental_data.get("revenue_growth")
            if self.fundamental_data
            else None,
            "debt_to_equity": self.fundamental_data.get("debt_to_equity")
            if self.fundamental_data
            else None,
            "recommendation_mean": self.fundamental_data.get("recommendation_mean")
            if self.fundamental_data
            else None,
            "analyst_buy_pct": self.fundamental_data.get("analyst_buy_pct")
            if self.fundamental_data
            else None,
        }

        # Classify signal using existing logic
        signal = classify_signal(signal_inputs)

        # Entry criteria: BUY signal with sufficient strength
        if (
            signal.signal_type == SignalType.BUY
            and signal.strength.value >= self.min_signal_strength
        ):
            logger.debug(
                f"ENTRY SIGNAL: {symbol} | Date: {backtest_date} | "
                f"Strength: {signal.strength}/10 | Reasons: {', '.join(signal.reasons)}"
            )
            return True

        return False

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, float],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        """Determine if strategy should exit position.

        Exit conditions checked in order:
        1. Max holding period exceeded → "time"
        2. Stop loss hit → "stop"
        3. AVOID signal (strategy invalidated) → "signal"
        4. Target profit hit → "target"

        Args:
            position: Current open position
            backtest_date: Current backtest date
            indicators: Technical indicators
            ohlcv: OHLCV data for current date

        Returns:
            (should_exit, exit_reason)
        """
        current_price = Decimal(str(ohlcv["close"]))
        holding_days = (backtest_date - position.entry_date).days

        # 1. Check max holding period
        if holding_days >= self.max_holding_days:
            logger.debug(
                f"EXIT (TIME): {position.symbol} | Held {holding_days} days (max: {self.max_holding_days})"
            )
            return (True, "time")

        # 2. Check stop loss (entry_price - 2 * ATR)
        atr = Decimal(str(indicators.get("atr_14", 0.0)))
        if atr > 0:
            stop_loss_price = position.entry_price - (self.stop_loss_atr_multiplier * atr)

            if current_price <= stop_loss_price:
                logger.debug(
                    f"EXIT (STOP): {position.symbol} | Price: ${current_price:.2f} <= Stop: ${stop_loss_price:.2f}"
                )
                return (True, "stop")

        # 3. Check for AVOID signal (strategy invalidated)
        signal_inputs = {
            "price": float(current_price),
            "ema_20": indicators.get("ema_20", 0.0),
            "sma_5": indicators.get("sma_5", 0.0),
            "sma_5_prev": indicators.get("sma_5_prev", 0.0),
            "rsi_14": indicators.get("rsi_14", 50.0),
            "macd": indicators.get("macd", 0.0),
            "volume": float(ohlcv.get("volume", 0)),
            "volume_avg_20": indicators.get("volume_avg_20", 0.0),
            # Use real fundamental data if available
            "company_health": self.fundamental_data.get("company_health"),
            "news_sentiment": self.fundamental_data.get("news_sentiment"),
            "earnings_days_away": None,
        }

        signal = classify_signal(signal_inputs)

        if signal.signal_type == SignalType.AVOID:
            logger.debug(
                f"EXIT (SIGNAL): {position.symbol} | AVOID signal | "
                f"Reasons: {', '.join(signal.reasons)}"
            )
            return (True, "signal")

        # 4. Check profit target (from signal classification)
        # signal_classifier doesn't provide explicit target price, so we use a simple % gain
        # Phase B: Use more sophisticated target price calculation
        target_return_pct = Decimal("10.0")  # 10% profit target (MVP heuristic)
        current_return_pct = Decimal(
            str((current_price - position.entry_price) / position.entry_price * Decimal("100.0"))
        )

        if current_return_pct >= target_return_pct:
            logger.debug(
                f"EXIT (TARGET): {position.symbol} | Return: {current_return_pct:.2f}% >= Target: {target_return_pct:.2f}%"
            )
            return (True, "target")

        # No exit conditions met
        return (False, "")
