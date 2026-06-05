"""Unit tests for the current-session intraday fetchers + fallback chain."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl

import app.sources.intraday_source as mod
from app.sources.intraday_source import (
    _INTRADAY_SCHEMA,
    _make_record,
    _missing_symbols,
    fetch_intraday_with_fallback,
)

_ET = ZoneInfo("America/New_York")


def _utc(hour: int, minute: int) -> dt.datetime:
    """A 2026-06-05 (EDT) ET wall-clock time expressed as the matching UTC datetime."""
    return dt.datetime(2026, 6, 5, hour, minute, tzinfo=_ET).astimezone(dt.UTC)


def test_make_record_normalizes_regular_session_bar() -> None:
    rec = _make_record("aapl", _utc(9, 30), 100.0, 101.0, 99.5, 100.5, 1000, "yfinance")

    assert rec is not None
    assert rec["symbol"] == "AAPL"
    assert rec["session_date"] == dt.date(2026, 6, 5)
    assert rec["close"] == 100.5
    assert rec["volume"] == 1000
    assert rec["source"] == "yfinance"
    assert rec["ts"].tzinfo is not None


def test_make_record_drops_bars_outside_the_regular_session() -> None:
    # 09:25 ET is pre-open; 16:00 ET is the close boundary (excluded).
    assert _make_record("AAPL", _utc(9, 25), 1, 1, 1, 1.0, 1, "yfinance") is None
    assert _make_record("AAPL", _utc(16, 0), 1, 1, 1, 1.0, 1, "yfinance") is None
    # 15:55 ET is the last regular bar -> kept.
    assert _make_record("AAPL", _utc(15, 55), 1, 1, 1, 1.0, 1, "yfinance") is not None


def test_make_record_drops_nonpositive_or_nan_close() -> None:
    assert _make_record("AAPL", _utc(10, 0), 1, 1, 1, 0.0, 1, "yfinance") is None
    assert _make_record("AAPL", _utc(10, 0), 1, 1, 1, float("nan"), 1, "yfinance") is None


def test_missing_symbols_reports_uncovered_symbols() -> None:
    frame = pl.DataFrame(
        [_make_record("AAPL", _utc(10, 0), 1, 1, 1, 1.0, 1, "yfinance")],
        schema=_INTRADAY_SCHEMA,
    )
    assert _missing_symbols(frame, ["AAPL", "MSFT"]) == ["MSFT"]
    assert _missing_symbols(None, ["AAPL"]) == ["AAPL"]


def test_fetch_intraday_with_fallback_handles_empty_symbols() -> None:
    assert fetch_intraday_with_fallback([]) == (None, {})


def test_fetch_intraday_with_fallback_fills_gaps_down_the_chain(monkeypatch) -> None:
    def _frame_for(symbols: list[str], source: str) -> pl.DataFrame:
        records = [_make_record(s, _utc(10, 0), 1, 1, 1, 10.0, 5, source) for s in symbols]
        return pl.DataFrame([r for r in records if r], schema=_INTRADAY_SCHEMA)

    # yfinance covers AAPL only; twelvedata then covers the remaining MSFT.
    monkeypatch.setattr(mod, "fetch_intraday_yfinance", lambda _: _frame_for(["AAPL"], "yfinance"))
    monkeypatch.setattr(mod, "fetch_intraday_twelvedata", lambda syms: _frame_for(syms, "twelvedata"))
    polygon_called = {"hit": False}

    def _polygon(symbols: list[str]) -> pl.DataFrame | None:
        polygon_called["hit"] = True
        return None

    monkeypatch.setattr(mod, "fetch_intraday_polygon", _polygon)

    frame, counts = fetch_intraday_with_fallback(["AAPL", "MSFT"])

    assert frame is not None
    assert set(frame["symbol"].to_list()) == {"AAPL", "MSFT"}
    assert counts == {"yfinance": 1, "twelvedata": 1}
    # All symbols resolved before the last-resort source, so polygon is never called.
    assert polygon_called["hit"] is False
