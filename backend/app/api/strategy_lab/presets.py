from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest.replay import Position


@dataclass(slots=True)
class _SignalDateStrategy:
    signal_dates: set[date]

    def should_enter(
        self,
        symbol: str,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> bool:
        return backtest_date in self.signal_dates

    def should_exit(
        self,
        position: Position,
        backtest_date: date,
        indicators: dict[str, Any],
        ohlcv: dict[str, float],
    ) -> tuple[bool, str]:
        return (False, "")


class PullbackAccumulatorBacktestStrategy(_SignalDateStrategy):
    pass


class BreakoutConfirmationBacktestStrategy(_SignalDateStrategy):
    pass


def compute_pullback_signal(price: float, rolling_30_high: float | None, sma_200: float | None) -> bool:
    if rolling_30_high is None or sma_200 is None:
        return False
    return price <= (rolling_30_high * 0.92) and price >= sma_200



def compute_breakout_signal(price: float, rolling_30_high: float | None, sma_50: float | None, sma_200: float | None) -> bool:
    if rolling_30_high is None or sma_50 is None or sma_200 is None:
        return False
    return price >= rolling_30_high and price > sma_50 >= sma_200


FIXED_INITIAL_CAPITAL = Decimal("50000")
