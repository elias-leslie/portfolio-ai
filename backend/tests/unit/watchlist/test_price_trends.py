from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import polars as pl

from app.watchlist.price_trends import (
    build_price_trend_map,
    build_score_series_map,
    build_vwap_signal_map,
)


class FakeStorage:
    """Routes each batched query to a canned result set by a distinctive SQL marker."""

    def __init__(
        self,
        *,
        daily: list[dict[str, Any]] | None = None,
        weekly: list[dict[str, Any]] | None = None,
        vwap: list[dict[str, Any]] | None = None,
        score: list[dict[str, Any]] | None = None,
    ) -> None:
        self.daily = daily or []
        self.weekly = weekly or []
        self.vwap = vwap or []
        self.score = score or []
        self.calls: list[tuple[str, list[str]]] = []

    def query(self, sql: str, params: list[str]) -> pl.DataFrame:
        self.calls.append((sql, params))
        if "overall_score" in sql:
            return pl.DataFrame(self.score)
        if "DISTINCT ON" in sql:
            return pl.DataFrame(self.weekly)
        if "latest_vwap" in sql:
            return pl.DataFrame(self.vwap)
        if "JOIN LATERAL" in sql:
            return pl.DataFrame(self.daily)
        return pl.DataFrame([])


def _daily(symbol: str, closes: list[float]) -> list[dict[str, Any]]:
    base = date(2026, 6, 4) - timedelta(days=len(closes) - 1)
    return [
        {"symbol": symbol, "bar_date": base + timedelta(days=i), "close": close}
        for i, close in enumerate(closes)
    ]


def _weekly(symbol: str, closes: list[float]) -> list[dict[str, Any]]:
    base = date(2026, 6, 1) - timedelta(weeks=len(closes) - 1)
    return [
        {"symbol": symbol, "bar_date": base + timedelta(weeks=i), "close": close}
        for i, close in enumerate(closes)
    ]


def test_build_price_trend_map_builds_series_per_window() -> None:
    daily_closes = [100.0 + i * (10.0 / 21.0) for i in range(22)]  # 100 -> 110 over 22 sessions
    weekly_closes = [100.0 + i for i in range(52)]  # 100 -> 151 over 52 weeks
    storage = FakeStorage(
        daily=_daily("MSFT", daily_closes),
        weekly=_weekly("MSFT", weekly_closes),
    )

    result = build_price_trend_map(storage, ["msft", "MSFT"])

    trends = {t["key"]: t for t in result["MSFT"]}
    assert list(trends) == ["D", "W", "Q", "Y"]

    # Daily 1M view = last 22 daily closes.
    assert trends["D"]["point_count"] == 22
    assert round(trends["D"]["return_pct"], 2) == 10.0
    assert len(trends["D"]["series"]) == 22
    assert trends["D"]["series"][-1]["close"] == daily_closes[-1]
    assert trends["D"]["series"][0]["date"] is not None

    # Weekly windows slice the same last-close-of-week series.
    assert trends["W"]["point_count"] == 13  # last 13 weeks (3M)
    assert trends["Q"]["point_count"] == 26  # last 26 weeks (6M)
    assert trends["Y"]["point_count"] == 52  # last 52 weeks (1Y)
    assert round(trends["Y"]["return_pct"], 2) == 51.0  # (151-100)/100
    assert round(trends["Q"]["return_pct"], 2) == round((151 - 126) / 126 * 100, 2)
    assert all(t["status"] == "available" and not t["partial"] for t in trends.values())
    assert all(t["end_source"] == "day_bars" for t in trends.values())


def test_build_price_trend_map_flags_young_symbol_as_partial() -> None:
    # Recent IPO: one daily bar, three weekly bars.
    storage = FakeStorage(
        daily=_daily("DRAM", [42.0]),
        weekly=_weekly("DRAM", [40.0, 41.0, 42.0]),
    )

    trends = {t["key"]: t for t in build_price_trend_map(storage, ["DRAM"])["DRAM"]}

    # Single daily point: can't draw a return, flagged insufficient + partial.
    assert trends["D"]["status"] == "insufficient_history"
    assert trends["D"]["partial"] is True
    assert trends["D"]["return_pct"] is None
    assert trends["D"]["point_count"] == 1

    # Three weekly points: drawable but short -> available + partial across W/Q/Y.
    for key in ("W", "Q", "Y"):
        assert trends[key]["status"] == "available"
        assert trends[key]["partial"] is True
        assert trends[key]["point_count"] == 3
        assert round(trends[key]["return_pct"], 2) == 5.0  # (42-40)/40


def test_build_price_trend_map_marks_missing_when_no_bars() -> None:
    storage = FakeStorage(daily=[], weekly=[])

    trends = build_price_trend_map(storage, ["NONE"])["NONE"]

    assert all(t["status"] == "missing" for t in trends)
    assert all(t["series"] == [] for t in trends)
    assert all(t["return_pct"] is None for t in trends)


def test_build_score_series_map_aggregates_daily_overall_scores() -> None:
    storage = FakeStorage(
        score=[
            {"item_id": "item-1", "day": date(2026, 6, 2), "overall": 55.0},
            {"item_id": "item-1", "day": date(2026, 6, 3), "overall": 58.0},
            {"item_id": "item-1", "day": date(2026, 6, 4), "overall": 61.0},
        ]
    )

    result = build_score_series_map(storage, ["item-1", "item-2"])

    series = result["item-1"]
    assert series["status"] == "available"
    assert series["point_count"] == 3
    assert series["current"] == 61.0
    assert series["series"][0] == {"date": "2026-06-02", "value": 55.0}

    # Item with no snapshots returns an empty, missing series.
    assert result["item-2"]["status"] == "missing"
    assert result["item-2"]["current"] is None
    assert result["item-2"]["series"] == []


def test_build_vwap_signal_map_returns_latest_session_distance() -> None:
    storage = FakeStorage(
        vwap=[
            {
                "symbol": "MSFT",
                "close_date": date(2026, 6, 4),
                "close": 108.0,
                "vwap_date": date(2026, 6, 4),
                "vwap": 107.0,
            }
        ]
    )
    quote_map = {"MSFT": {"price": 110.0, "cached_at": "2026-06-04T16:00:00Z"}}

    signal = build_vwap_signal_map(storage, ["MSFT"], quote_map)["MSFT"]

    assert signal["status"] == "available"
    assert signal["vwap"] == 107.0
    assert signal["price"] == 110.0
    assert round(signal["distance_pct"], 2) == 2.8
    assert signal["as_of_date"] == "2026-06-04"
    assert signal["close_as_of_date"] == "2026-06-04"
    assert signal["price_source"] == "quote"


def test_build_vwap_signal_map_marks_missing_vwap() -> None:
    storage = FakeStorage(
        vwap=[
            {
                "symbol": "MSFT",
                "close_date": date(2026, 6, 4),
                "close": 108.0,
                "vwap_date": None,
                "vwap": None,
            }
        ]
    )

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "missing"
    assert result["MSFT"]["distance_pct"] is None
    assert result["MSFT"]["price_source"] == "daily_close"


def test_build_vwap_signal_map_treats_nan_vwap_as_missing() -> None:
    storage = FakeStorage(
        vwap=[
            {
                "symbol": "MSFT",
                "close_date": date(2026, 6, 4),
                "close": 108.0,
                "vwap_date": date(2026, 6, 4),
                "vwap": float("nan"),
            }
        ]
    )

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "missing"
    assert result["MSFT"]["vwap"] is None
    assert result["MSFT"]["distance_pct"] is None


def test_build_vwap_signal_map_marks_stale_vwap() -> None:
    storage = FakeStorage(
        vwap=[
            {
                "symbol": "MSFT",
                "close_date": date(2026, 6, 4),
                "close": 108.0,
                "vwap_date": date(2026, 6, 3),
                "vwap": 106.0,
            }
        ]
    )

    result = build_vwap_signal_map(storage, ["MSFT"], {"MSFT": None})

    assert result["MSFT"]["status"] == "stale"
    assert result["MSFT"]["as_of_date"] == "2026-06-03"
    assert result["MSFT"]["close_as_of_date"] == "2026-06-04"
