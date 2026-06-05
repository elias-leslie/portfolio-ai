"""Unit tests for fear/greed input processing."""

from __future__ import annotations

import datetime as dt

from app.tasks.market_data.fear_greed_processing import compute_date_indicators


def test_compute_date_indicators_keeps_missing_observed_series_null() -> None:
    target = dt.date(2026, 6, 4)
    prices = [float(100 + index) for index in range(210)]

    result = compute_date_indicators(
        spy_close=prices[-1],
        prices_up_to_date=prices,
        date=target,
        vix_data={},
        hy_spread_dict={dt.date(2026, 6, 3): 2.75},
    )

    assert result is not None
    _sma_200, _rsi_14, vix_close, hy_spread = result
    assert vix_close is None
    assert hy_spread is None
