from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import polars as pl

from app.watchlist.price_trends import build_price_trend_map, build_vwap_signal_map


class FakeStorage:
    def __init__(self, ranked_rows: list[dict[str, Any]], latest_rows: list[dict[str, Any]]):
        self.ranked_rows = ranked_rows
        self.latest_rows = latest_rows
        self.calls: list[tuple[str, list[str]]] = []

    def query(self, sql: str, params: list[str]) -> pl.DataFrame:
        self.calls.append((sql, params))
        if "ROW_NUMBER()" in sql:
            return pl.DataFrame(self.ranked_rows)
        return pl.DataFrame(self.latest_rows)


def _ranked_rows(symbol: str) -> list[dict[str, Any]]:
    latest_date = date(2026, 6, 4)
    overrides = {0: 108.0, 1: 100.0, 5: 90.0, 21: 80.0, 63: 70.0}
    return [
        {
            "symbol": symbol,
            "date": latest_date - timedelta(days=index),
            "close": overrides.get(index, 100.0 - index),
            "vwap": 107.0 if index == 0 else None,
            "rn": index + 1,
        }
        for index in range(64)
    ]


def test_build_price_trend_map_uses_cached_quote_and_daily_bars() -> None:
    storage = FakeStorage(_ranked_rows("MSFT"), [])
    quote_map = {
        "MSFT": {
            "price": 110.0,
            "cached_at": datetime(2026, 6, 4, 16, 0, tzinfo=UTC),
        }
    }

    result = build_price_trend_map(storage, ["msft", "MSFT"], quote_map)

    trends = result["MSFT"]
    assert [trend["key"] for trend in trends] == ["D", "W", "M", "Q"]
    assert trends[0]["return_pct"] == 10.0
    assert round(trends[1]["return_pct"], 2) == 22.22
    assert round(trends[2]["return_pct"], 2) == 37.5
    assert round(trends[3]["return_pct"], 2) == 57.14
    assert trends[0]["end_close"] == 110.0
    assert trends[0]["end_source"] == "quote"
    assert trends[0]["end_date"] == "2026-06-04T16:00:00+00:00"
    assert storage.calls[0][1] == ["MSFT"]


def test_build_price_trend_map_marks_insufficient_history() -> None:
    storage = FakeStorage(_ranked_rows("AAPL")[:2], [])

    result = build_price_trend_map(storage, ["AAPL"], {"AAPL": None})

    trends = result["AAPL"]
    assert trends[0]["status"] == "available"
    assert trends[1]["status"] == "insufficient_history"
    assert trends[2]["return_pct"] is None
    assert trends[3]["return_pct"] is None


def test_build_vwap_signal_map_returns_latest_session_distance() -> None:
    latest_rows = [
        {
            "symbol": "MSFT",
            "close_date": date(2026, 6, 4),
            "close": 108.0,
            "vwap_date": date(2026, 6, 4),
            "vwap": 107.0,
        }
    ]
    storage = FakeStorage([], latest_rows)
    quote_map = {"MSFT": {"price": 110.0, "cached_at": "2026-06-04T16:00:00Z"}}

    result = build_vwap_signal_map(storage, ["MSFT"], quote_map)

    signal = result["MSFT"]
    assert signal["status"] == "available"
    assert signal["vwap"] == 107.0
    assert signal["price"] == 110.0
    assert round(signal["distance_pct"], 2) == 2.8
    assert signal["as_of_date"] == "2026-06-04"
    assert signal["close_as_of_date"] == "2026-06-04"
    assert signal["price_source"] == "quote"


def test_build_vwap_signal_map_marks_missing_vwap() -> None:
    latest_rows = [
        {
            "symbol": "MSFT",
            "close_date": date(2026, 6, 4),
            "close": 108.0,
            "vwap_date": None,
            "vwap": None,
        }
    ]
    storage = FakeStorage([], latest_rows)

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "missing"
    assert result["MSFT"]["distance_pct"] is None
    assert result["MSFT"]["price_source"] == "daily_close"


def test_build_vwap_signal_map_treats_nan_vwap_as_missing() -> None:
    latest_rows = [
        {
            "symbol": "MSFT",
            "close_date": date(2026, 6, 4),
            "close": 108.0,
            "vwap_date": date(2026, 6, 4),
            "vwap": float("nan"),
        }
    ]
    storage = FakeStorage([], latest_rows)

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "missing"
    assert result["MSFT"]["vwap"] is None
    assert result["MSFT"]["distance_pct"] is None


def test_build_vwap_signal_map_marks_stale_vwap() -> None:
    latest_rows = [
        {
            "symbol": "MSFT",
            "close_date": date(2026, 6, 4),
            "close": 108.0,
            "vwap_date": date(2026, 6, 3),
            "vwap": 106.0,
        }
    ]
    storage = FakeStorage([], latest_rows)

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "stale"
    assert result["MSFT"]["as_of_date"] == "2026-06-03"
    assert result["MSFT"]["close_as_of_date"] == "2026-06-04"
