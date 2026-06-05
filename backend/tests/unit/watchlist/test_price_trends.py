from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
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
        intraday: list[dict[str, Any]] | None = None,
        daily: list[dict[str, Any]] | None = None,
        weekly: list[dict[str, Any]] | None = None,
        vwap: list[dict[str, Any]] | None = None,
        score: list[dict[str, Any]] | None = None,
    ) -> None:
        self.intraday = intraday or []
        self.daily = daily or []
        self.weekly = weekly or []
        self.vwap = vwap or []
        self.score = score or []
        self.calls: list[tuple[str, list[str]]] = []

    def query(self, sql: str, params: list[str]) -> pl.DataFrame:
        self.calls.append((sql, params))
        if "overall_score" in sql:
            return pl.DataFrame(self.score)
        # intraday_bars also uses JOIN LATERAL, so match it before the daily read.
        if "intraday_bars" in sql:
            return pl.DataFrame(self.intraday)
        if "DISTINCT ON" in sql:
            return pl.DataFrame(self.weekly)
        if "latest_vwap" in sql:
            return pl.DataFrame(self.vwap)
        if "JOIN LATERAL" in sql:
            return pl.DataFrame(self.daily)
        return pl.DataFrame([])


def _intraday(symbol: str, closes: list[float]) -> list[dict[str, Any]]:
    # 5-minute bars from 13:30 UTC (= 9:30 ET on this June/EDT session).
    base = datetime(2026, 6, 5, 13, 30, tzinfo=UTC)
    return [
        {"symbol": symbol, "bar_date": base + timedelta(minutes=5 * i), "close": close}
        for i, close in enumerate(closes)
    ]


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
    intraday_closes = [100.0 + i * (2.0 / 11.0) for i in range(12)]  # 100 -> 102 over 12 bars
    daily_closes = [100.0 + i for i in range(5)]  # 100 -> 104 over one trading week
    weekly_closes = [100.0 + i for i in range(52)]  # 100 -> 151 over 52 weeks
    storage = FakeStorage(
        intraday=_intraday("MSFT", intraday_closes),
        daily=_daily("MSFT", daily_closes),
        weekly=_weekly("MSFT", weekly_closes),
    )

    result = build_price_trend_map(storage, ["msft", "MSFT"])

    trends = {t["key"]: t for t in result["MSFT"]}
    assert list(trends) == ["D", "W", "Q", "Y"]

    # D = the current session's intraday closes, sourced from intraday_bars and
    # never partial. Its points keep a time component, unlike the daily dates.
    assert trends["D"]["point_count"] == 12
    assert trends["D"]["end_source"] == "intraday_bars"
    assert trends["D"]["partial"] is False
    assert round(trends["D"]["return_pct"], 2) == 2.0
    assert len(trends["D"]["series"]) == 12
    assert "T" in trends["D"]["series"][0]["date"]

    # W = last 5 daily closes (one trading week).
    assert trends["W"]["point_count"] == 5
    assert round(trends["W"]["return_pct"], 2) == 4.0  # (104-100)/100
    assert trends["W"]["end_source"] == "day_bars"

    # Q/Y slice the same last-close-of-week series.
    assert trends["Q"]["point_count"] == 13  # last quarter
    assert trends["Y"]["point_count"] == 52  # last year
    assert round(trends["Y"]["return_pct"], 2) == 51.0  # (151-100)/100
    assert round(trends["Q"]["return_pct"], 2) == round((151 - 139) / 139 * 100, 2)
    assert all(t["status"] == "available" and not t["partial"] for t in trends.values())


def test_today_trend_falls_back_to_daily_when_intraday_empty() -> None:
    # Pre-open, or a symbol the intraday feeds missed: no intraday bars yet.
    storage = FakeStorage(
        intraday=[],
        daily=_daily("AAPL", [99.0, 100.0, 101.0, 102.0, 103.0]),
        weekly=_weekly("AAPL", [100.0 + i for i in range(52)]),
    )

    trends = {t["key"]: t for t in build_price_trend_map(storage, ["AAPL"])["AAPL"]}

    # D falls back to the last two daily closes; sourced from day_bars, not partial.
    today = trends["D"]
    assert today["end_source"] == "day_bars"
    assert today["status"] == "available"
    assert today["partial"] is False
    assert today["point_count"] == 2
    assert round(today["return_pct"], 2) == round((103 - 102) / 102 * 100, 2)


def test_build_price_trend_map_flags_young_symbol_but_never_today() -> None:
    # Recent IPO mid-first-session: a few intraday bars, one daily close, three weekly.
    storage = FakeStorage(
        intraday=_intraday("DRAM", [40.0, 41.0, 42.0]),
        daily=_daily("DRAM", [42.0]),
        weekly=_weekly("DRAM", [40.0, 41.0, 42.0]),
    )

    trends = {t["key"]: t for t in build_price_trend_map(storage, ["DRAM"])["DRAM"]}

    # Today draws from the live session and is never young-flagged, even on day 1.
    assert trends["D"]["status"] == "available"
    assert trends["D"]["partial"] is False
    assert trends["D"]["point_count"] == 3
    assert trends["D"]["end_source"] == "intraday_bars"

    # W: a single daily close can't draw a week -> insufficient, and W is young-flagged.
    assert trends["W"]["status"] == "insufficient_history"
    assert trends["W"]["partial"] is True
    assert trends["W"]["point_count"] == 1

    # Q/Y: three weekly points -> drawable but short -> available + partial.
    for key in ("Q", "Y"):
        assert trends[key]["status"] == "available"
        assert trends[key]["partial"] is True
        assert trends[key]["point_count"] == 3
        assert round(trends[key]["return_pct"], 2) == 5.0  # (42-40)/40


def test_build_price_trend_map_marks_missing_when_no_bars() -> None:
    storage = FakeStorage(intraday=[], daily=[], weekly=[])

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
