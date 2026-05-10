"""Additional backtest strategies for the universe screening sweep.

Each class implements the Strategy Protocol from app.backtest.replay
(should_enter, should_exit). They consume the same indicator dict the
replay engine builds (rsi_14, bbands_20_2, sma_*, ema_*, atr_14,
volume_avg_20, etc.) so they slot into the existing harness without
changes to replay.

Three templates here, picked to cover regimes the trend-following
EnhancedSignalStrategy struggles with:

- MeanReversionStrategy: counter-trend; buys oversold capitulation, sells
  on bounce. Designed to add value in choppy / range-bound regimes.

- VolatilityBreakoutStrategy: rides 20-day high breakouts on volume
  confirmation; trails until stop or close-below-recent-low.

- MomentumWithRegimeStrategy: trend-following gated by a market regime
  filter (defaults to SPY > SPY's SMA-200). Stays in cash when the
  regime is hostile.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest.replay import Position
from app.logging_config import get_logger
from app.storage import PortfolioStorage, get_storage

logger = get_logger(__name__)


def _bbands(indicators: dict[str, Any]) -> dict[str, float] | None:
    bb = indicators.get("bbands_20_2")
    if isinstance(bb, dict):
        return bb
    return None


def _atr(indicators: dict[str, Any]) -> float:
    atr = indicators.get("atr_14")
    return float(atr) if atr is not None else 0.0


@dataclass
class MeanReversionStrategy:
    """Buy oversold capitulation, sell on mean reversion.

    Entry (all required):
    - RSI(14) below ``rsi_oversold`` (default 30)
    - Price below the lower Bollinger band
    - Volume above ``volume_multiplier`` x 20-day average (capitulation)

    Exit (first to trigger):
    - RSI returns above ``rsi_exit`` (default 50)
    - Price closes above BB middle band
    - Stop loss: entry - ``stop_loss_atr_multiplier`` x ATR
    - Max holding period
    """

    rsi_oversold: float = 30.0
    rsi_exit: float = 50.0
    volume_multiplier: float = 1.2
    stop_loss_atr_multiplier: float = 1.5
    max_holding_days: int = 20

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        rsi = indicators.get("rsi_14")
        if rsi is None or rsi >= self.rsi_oversold:
            return False
        bb = _bbands(indicators)
        if bb is None:
            return False
        price = float(ohlcv.get("close", 0.0))
        if price >= bb["lower"]:
            return False
        volume = float(ohlcv.get("volume", 0))
        avg_vol = float(indicators.get("volume_avg_20") or 0.0)
        return not (avg_vol <= 0 or volume < self.volume_multiplier * avg_vol)

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        holding_days = (backtest_date - position.entry_date).days
        if holding_days >= self.max_holding_days:
            return (True, "time")

        current_price = Decimal(str(ohlcv.get("close", 0.0)))
        atr = Decimal(str(_atr(indicators)))
        if atr > 0:
            stop_price = position.entry_price - (Decimal(str(self.stop_loss_atr_multiplier)) * atr)
            if current_price <= stop_price:
                return (True, "stop")

        rsi = indicators.get("rsi_14")
        bb = _bbands(indicators)
        if rsi is not None and rsi >= self.rsi_exit:
            return (True, "signal")
        if bb is not None and float(current_price) >= bb["middle"]:
            return (True, "target")
        return (False, "")


@dataclass
class VolatilityBreakoutStrategy:
    """Buy 20-day high breakouts confirmed by volume.

    Entry (all required):
    - Close at or above 20-day high (price > sma_20 used as proxy when
      no rolling-high indicator; we use sma_20 + 1*ATR as breakout
      threshold for a more conservative trigger)
    - Volume above ``volume_multiplier`` x 20-day average
    - RSI below ``rsi_max`` (avoid extreme overbought)

    Exit (first to trigger):
    - Stop: entry - ``stop_loss_atr_multiplier`` x ATR
    - Target: entry + ``target_atr_multiplier`` x ATR (default 2:1 R:R)
    - Trail: close < EMA-20
    - Max holding period
    """

    breakout_atr_multiplier: float = 1.0
    volume_multiplier: float = 1.5
    rsi_max: float = 75.0
    stop_loss_atr_multiplier: float = 2.0
    target_atr_multiplier: float = 4.0
    max_holding_days: int = 30

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        sma_20 = indicators.get("sma_20")
        atr = _atr(indicators)
        if sma_20 is None or atr <= 0:
            return False
        threshold = float(sma_20) + self.breakout_atr_multiplier * atr
        price = float(ohlcv.get("close", 0.0))
        if price < threshold:
            return False
        volume = float(ohlcv.get("volume", 0))
        avg_vol = float(indicators.get("volume_avg_20") or 0.0)
        if avg_vol <= 0 or volume < self.volume_multiplier * avg_vol:
            return False
        rsi = indicators.get("rsi_14")
        return not (rsi is not None and rsi >= self.rsi_max)

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        holding_days = (backtest_date - position.entry_date).days
        if holding_days >= self.max_holding_days:
            return (True, "time")

        current_price = Decimal(str(ohlcv.get("close", 0.0)))
        atr = Decimal(str(_atr(indicators)))
        if atr > 0:
            stop_price = position.entry_price - (Decimal(str(self.stop_loss_atr_multiplier)) * atr)
            if current_price <= stop_price:
                return (True, "stop")
            target_price = position.entry_price + (Decimal(str(self.target_atr_multiplier)) * atr)
            if current_price >= target_price:
                return (True, "target")

        ema_20 = indicators.get("ema_20")
        if ema_20 is not None and float(current_price) < float(ema_20):
            return (True, "signal")
        return (False, "")


class MomentumWithRegimeStrategy:
    """Trend-following gated by a market regime filter.

    Entry (all required):
    - Price above ``sma_200`` (long-term uptrend)
    - ``ema_20`` above ``sma_50`` (medium-term momentum aligned)
    - RSI above 50 (strength bias)
    - Regime: benchmark price above its own SMA-200 on the same date.
      Defaults to SPY; pre-computed at construction for fast lookup.

    Exit:
    - Trend break: price < EMA-20
    - Regime flip: benchmark drops below its SMA-200
    - Stop loss: entry - ``stop_loss_atr_multiplier`` x ATR
    - Max holding period
    """

    def __init__(
        self,
        regime_symbol: str = "SPY",
        regime_sma_window: int = 200,
        rsi_min: float = 50.0,
        stop_loss_atr_multiplier: float = 2.5,
        max_holding_days: int = 60,
        storage: PortfolioStorage | None = None,
    ) -> None:
        self.regime_symbol = regime_symbol
        self.regime_sma_window = regime_sma_window
        self.rsi_min = rsi_min
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self.max_holding_days = max_holding_days
        self._storage = storage or get_storage()
        self._regime_dates: set[date] = self._build_regime_dates()

    def _build_regime_dates(self) -> set[date]:
        """Pre-compute dates where benchmark price > benchmark SMA-N."""
        df = self._storage.query(
            """
            SELECT date, close FROM day_bars
            WHERE symbol = $1
            ORDER BY date
            """,
            [self.regime_symbol],
        )
        if df.is_empty() or len(df) < self.regime_sma_window:
            logger.warning(
                "regime_filter_insufficient_history",
                symbol=self.regime_symbol,
                rows=len(df),
            )
            return set()
        records = df.to_dicts()
        ok_dates: set[date] = set()
        closes = [float(r["close"]) for r in records]
        for i in range(self.regime_sma_window - 1, len(records)):
            window = closes[i - self.regime_sma_window + 1 : i + 1]
            sma = sum(window) / len(window)
            if closes[i] > sma:
                ok_dates.add(records[i]["date"])
        return ok_dates

    def _regime_ok(self, backtest_date: date) -> bool:
        return backtest_date in self._regime_dates

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        if not self._regime_ok(backtest_date):
            return False
        price = float(ohlcv.get("close", 0.0))
        sma_200 = indicators.get("sma_200")
        ema_20 = indicators.get("ema_20")
        sma_50 = indicators.get("sma_50")
        rsi = indicators.get("rsi_14")
        if sma_200 is None or ema_20 is None or sma_50 is None or rsi is None:
            return False
        if price <= float(sma_200):
            return False
        if float(ema_20) <= float(sma_50):
            return False
        return rsi > self.rsi_min

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        holding_days = (backtest_date - position.entry_date).days
        if holding_days >= self.max_holding_days:
            return (True, "time")

        current_price = Decimal(str(ohlcv.get("close", 0.0)))
        atr = Decimal(str(_atr(indicators)))
        if atr > 0:
            stop_price = position.entry_price - (Decimal(str(self.stop_loss_atr_multiplier)) * atr)
            if current_price <= stop_price:
                return (True, "stop")

        if not self._regime_ok(backtest_date):
            return (True, "signal")

        ema_20 = indicators.get("ema_20")
        if ema_20 is not None and float(current_price) < float(ema_20):
            return (True, "signal")
        return (False, "")
