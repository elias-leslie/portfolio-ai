"""Unit tests for OHLCV ingestion helpers."""

from __future__ import annotations

import datetime as dt

import polars as pl

from app.sources.base import DatasetRequest
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


def test_fetch_watchlist_vwap_data_handles_mixed_vendor_schemas() -> None:
    """FMP and Polygon VWAP frames have different optional columns."""

    class _Source:
        def __init__(self, name: str, frame: pl.DataFrame) -> None:
            self.name = name
            self._frame = frame

        def fetch_day_bars(self, _request: DatasetRequest) -> pl.DataFrame:
            return self._frame

    class _Fetcher:
        def __init__(self) -> None:
            self.metrics_manager = _Metrics()

        def get_sources_for_dataset(self, _dataset: str) -> list[_Source]:
            return [
                _Source(
                    "fmp",
                    pl.DataFrame(
                        [
                            {
                                "symbol": "AAPL",
                                "date": dt.date(2026, 5, 1),
                                "open": 100.0,
                                "high": 101.0,
                                "low": 99.0,
                                "close": 100.5,
                                "volume": 1000,
                                "vwap": 100.2,
                                "source": "fmp",
                            }
                        ]
                    ),
                ),
                _Source(
                    "polygon",
                    pl.DataFrame(
                        [
                            {
                                "symbol": "MSFT",
                                "date": dt.date(2026, 5, 1),
                                "open": 200.0,
                                "high": 202.0,
                                "low": 199.0,
                                "close": 201.0,
                                "volume": 2000,
                                "vwap": 200.5,
                                "trade_count": 120,
                                "source": "polygon",
                            }
                        ]
                    ),
                ),
            ]

    class _Metrics:
        def __init__(self) -> None:
            self.successes: list[str] = []

        def record_success(self, source_name: str, _latency_ms: int) -> None:
            self.successes.append(source_name)

        def record_failure(self, _source_name: str, _error: Exception) -> None:
            raise AssertionError("unexpected failure")

    fetcher = _Fetcher()
    request = DatasetRequest(
        dataset="day",
        profile="vwap",
        symbols=["AAPL", "MSFT"],
        start=dt.date(2026, 5, 1),
        end=dt.date(2026, 5, 1),
        timezone="UTC",
    )

    result, error_count, errors = _ohlcv_helpers.fetch_watchlist_vwap_data(fetcher, request)

    assert error_count == 0
    assert errors == {}
    assert fetcher.metrics_manager.successes == ["fmp", "polygon"]
    assert result is not None
    assert result.height == 2
    assert "trade_count" in result.columns
    assert set(result["symbol"].to_list()) == {"AAPL", "MSFT"}
