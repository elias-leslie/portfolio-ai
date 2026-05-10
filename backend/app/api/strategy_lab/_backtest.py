from __future__ import annotations

from datetime import date
from typing import Any

from app.backtest.replay import InsufficientDataError

from ._facts import _fetch_day_bars, _float_or_none, _rolling_high, _storage
from ._text import INSUFFICIENT_HISTORY_TEXT, STALE_HELPER_TEXT
from .models import (
    StrategyLabBacktestPoint,
    StrategyLabBacktestSnapshot,
    StrategyLabUnavailableItem,
)
from .presets import compute_breakout_signal, compute_pullback_signal


def _backtest_quote_unavailable() -> StrategyLabBacktestSnapshot:
    return StrategyLabBacktestSnapshot(
        status="quote_unavailable",
        lookback_days=None,
        total_return_pct=None,
        buy_hold_return_pct=None,
        excess_return_pct=None,
        max_drawdown_pct=None,
        trade_count=0,
        equity_curve=[],
        helper_text=STALE_HELPER_TEXT,
    )


def _backtest_insufficient_history(
    *,
    lookback_days: int | None,
    error: InsufficientDataError | None = None,
) -> StrategyLabBacktestSnapshot:
    return StrategyLabBacktestSnapshot(
        status="insufficient_history",
        lookback_days=lookback_days,
        requested_start_date=error.requested_start.isoformat() if error else None,
        requested_end_date=error.requested_end.isoformat() if error else None,
        available_start_date=error.available_start.isoformat() if error and error.available_start else None,
        available_end_date=error.available_end.isoformat() if error and error.available_end else None,
        trade_count=0,
        equity_curve=[],
        helper_text=INSUFFICIENT_HISTORY_TEXT,
    )


def _unavailable_from_snapshot(symbol: str, snapshot: StrategyLabBacktestSnapshot) -> StrategyLabUnavailableItem:
    return StrategyLabUnavailableItem(
        symbol=symbol,
        reason="insufficient_history",
        message=snapshot.helper_text or INSUFFICIENT_HISTORY_TEXT,
        requested_start_date=snapshot.requested_start_date,
        requested_end_date=snapshot.requested_end_date,
        available_start_date=snapshot.available_start_date,
        available_end_date=snapshot.available_end_date,
        lookback_days=snapshot.lookback_days,
    )


def _unavailable_from_error(symbol: str, error: Exception) -> StrategyLabUnavailableItem:
    if isinstance(error, InsufficientDataError):
        return StrategyLabUnavailableItem(
            symbol=symbol,
            reason="insufficient_history",
            message=INSUFFICIENT_HISTORY_TEXT,
            requested_start_date=error.requested_start.isoformat(),
            requested_end_date=error.requested_end.isoformat(),
            available_start_date=error.available_start.isoformat() if error.available_start else None,
            available_end_date=error.available_end.isoformat() if error.available_end else None,
            lookback_days=None,
        )
    return StrategyLabUnavailableItem(
        symbol=symbol,
        reason="evaluation_error",
        message="Strategy Lab could not evaluate this symbol right now.",
    )


def _sample_equity_curve(points: list[Any]) -> list[StrategyLabBacktestPoint]:
    if len(points) <= 200:
        selected = points
    else:
        step = (len(points) - 1) / 199
        indexes = sorted({round(i * step) for i in range(200)})
        selected = [points[i] for i in indexes]
    return [
        StrategyLabBacktestPoint(date=point.date.isoformat(), equity=round(float(point.equity), 2))
        for point in selected
    ]


def _build_signal_dates(symbol: str, template: str, end_date: date) -> tuple[set[date], int]:
    rows = _fetch_day_bars(symbol, end_date, limit=1500)
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    if len(closes) < 252:
        return set(), len(closes)
    signal_dates: set[date] = set()
    for idx, row in enumerate(rows):
        current_price = float(row["close"])
        prefix = closes[: idx + 1]
        rolling_30 = _rolling_high(prefix, 30)
        sma_50 = _float_or_none(prefix, 50)
        sma_200 = _float_or_none(prefix, 200)
        if template == "pullback_accumulator":
            if compute_pullback_signal(current_price, rolling_30, sma_200):
                signal_dates.add(row["date"])
        elif compute_breakout_signal(current_price, rolling_30, sma_50, sma_200):
            signal_dates.add(row["date"])
    return signal_dates, len(closes)


def _buy_hold_return(symbol: str, start_date: date, end_date: date) -> float | None:
    df = _storage().query(
        """
        SELECT date, close
        FROM day_bars
        WHERE symbol = ?
          AND date >= ?
          AND date <= ?
        ORDER BY date ASC
        """,
        [symbol, start_date.isoformat(), end_date.isoformat()],
    )
    if df.is_empty() or len(df) < 2:
        return None
    rows = df.to_dicts()
    start = float(rows[0]["close"])
    end = float(rows[-1]["close"])
    if start <= 0:
        return None
    return round(((end - start) / start) * 100, 2)
