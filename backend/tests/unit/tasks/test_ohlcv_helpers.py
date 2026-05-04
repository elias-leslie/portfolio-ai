"""Unit tests for OHLCV ingestion helpers."""

from __future__ import annotations

import datetime as dt

import polars as pl

from app.tasks.ingestion import _ohlcv_helpers


def test_calculate_date_range_ends_at_latest_completed_trading_day(monkeypatch) -> None:
    monkeypatch.setattr(
        _ohlcv_helpers,
        "get_expected_data_date",
        lambda _now: dt.date(2026, 5, 1),
    )

    start_date, end_date = _ohlcv_helpers.calculate_date_range(days=5)

    assert start_date == dt.date(2026, 4, 24)
    assert end_date == dt.date(2026, 5, 1)


def test_prepare_dataframe_drops_weekend_and_incomplete_trading_rows(monkeypatch) -> None:
    monkeypatch.setattr(
        _ohlcv_helpers,
        "get_expected_data_date",
        lambda _now: dt.date(2026, 5, 1),
    )
    monkeypatch.setattr(
        _ohlcv_helpers,
        "is_trading_day",
        lambda value: value.weekday() < 5,
    )
    frame = pl.DataFrame(
        [
            {
                "symbol": "SPY",
                "date": dt.date(2026, 5, 1),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
                "source": "test",
            },
            {
                "symbol": "DX-Y.NYB",
                "date": dt.date(2026, 5, 3),
                "open": 98.0,
                "high": 98.2,
                "low": 97.9,
                "close": 98.1,
                "volume": 0,
                "source": "test",
            },
            {
                "symbol": "^VIX",
                "date": dt.date(2026, 5, 4),
                "open": 17.0,
                "high": 18.0,
                "low": 16.5,
                "close": 17.5,
                "volume": 0,
                "source": "test",
            },
        ]
    )

    prepared, symbols = _ohlcv_helpers.prepare_dataframe(frame, "ingest-test")

    assert prepared["date"].to_list() == [dt.date(2026, 5, 1)]
    assert prepared["symbol"].to_list() == ["SPY"]
    assert symbols == ["SPY"]
