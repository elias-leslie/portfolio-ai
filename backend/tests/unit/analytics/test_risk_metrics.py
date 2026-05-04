"""Unit tests for risk metric data access."""

from __future__ import annotations

import datetime as dt
from typing import Any

import polars as pl

from app.analytics.risk_metrics import get_daily_returns


class _FakeStorage:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any] | None]] = []

    def query(self, sql: str, params: list[Any] | None = None) -> pl.DataFrame:
        self.calls.append((sql, params))
        return pl.DataFrame(
            [
                {"date": dt.date(2026, 5, 1), "close": 100.0},
                {"date": dt.date(2026, 5, 4), "close": 101.0},
            ]
        )


def test_get_daily_returns_binds_lookback_outside_interval_literal() -> None:
    storage = _FakeStorage()

    returns = get_daily_returns(storage, "SPY", lookback_days=90)

    assert returns == [(dt.date(2026, 5, 4), 0.01)]
    sql, params = storage.calls[0]
    assert "%s * INTERVAL '1 day'" in sql
    assert "INTERVAL '%s days'" not in sql
    assert params == ["SPY", 90]
