"""Regression tests for covariance storage query parameters."""

from __future__ import annotations

import polars as pl

from app.analytics.covariance_calc import calculate_daily_returns
from app.analytics.covariance_storage import get_covariance_matrix


class CapturingStorage:
    def __init__(self) -> None:
        self.query_text = ""
        self.params: list[object] = []

    def query(self, sql: str, params: list[object] | None = None) -> pl.DataFrame:
        self.query_text = sql
        self.params = params or []
        return pl.DataFrame()


def test_daily_returns_uses_symbol_params_before_lookback_param() -> None:
    storage = CapturingStorage()

    calculate_daily_returns(storage, ["VTI", "TSLA"], lookback_days=252)

    assert "WHERE symbol IN ($1, $2)" in storage.query_text
    assert "make_interval(days => $3)" in storage.query_text
    assert storage.params == ["VTI", "TSLA", 252]


def test_covariance_matrix_uses_distinct_symbol_params_for_both_columns() -> None:
    storage = CapturingStorage()

    get_covariance_matrix(storage, ["VTI", "TSLA"])

    assert "WHERE symbol1 IN ($1, $2)" in storage.query_text
    assert "AND symbol2 IN ($3, $4)" in storage.query_text
    assert "AND calculated_at >= $5" in storage.query_text
    assert storage.params[:4] == ["VTI", "TSLA", "VTI", "TSLA"]
