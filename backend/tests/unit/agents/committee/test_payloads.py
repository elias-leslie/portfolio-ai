"""Tests for the per-symbol payload fetchers."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from app.agents.committee import payloads

# ---------- in-memory connection fake ----------


class _FakeCursor:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows_by_table = rows_by_table
        self._next: Any = None

    def execute(self, sql: str, _params: Any = None) -> _FakeCursor:
        sql_lower = sql.lower()
        if "from technical_indicators" in sql_lower:
            self._next = self._rows_by_table.get("technical_indicators")
        elif "from day_bars" in sql_lower:
            self._next = self._rows_by_table.get("day_bars")
        elif "from valuation_metrics" in sql_lower:
            self._next = self._rows_by_table.get("valuation_metrics")
        elif "from cash_flow_metrics" in sql_lower:
            self._next = self._rows_by_table.get("cash_flow_metrics")
        elif "from financial_health_scores" in sql_lower:
            self._next = self._rows_by_table.get("financial_health_scores")
        elif "from symbols" in sql_lower:
            self._next = self._rows_by_table.get("symbols")
        elif "from earnings_surprises" in sql_lower:
            self._next = self._rows_by_table.get("earnings_surprises")
        elif "from watchlist_snapshots" in sql_lower:
            self._next = self._rows_by_table.get("watchlist_snapshots")
        elif "from news_cache" in sql_lower:
            self._next = self._rows_by_table.get("news_cache")
        elif "from portfolio_positions" in sql_lower:
            self._next = self._rows_by_table.get("portfolio_positions")
        elif "from portfolio_accounts" in sql_lower:
            self._next = self._rows_by_table.get("portfolio_accounts")
        else:
            raise AssertionError(f"unexpected query: {sql}")
        return self

    def fetchone(self) -> Any:
        rows = self._next
        if isinstance(rows, list):
            return rows[0] if rows else None
        return rows

    def fetchall(self) -> Any:
        rows = self._next
        if rows is None:
            return []
        if isinstance(rows, list):
            return rows
        return [rows]


class _FakeConn:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows = rows_by_table

    def execute(self, sql: str, params: Any = None) -> _FakeCursor:
        cur = _FakeCursor(self._rows)
        return cur.execute(sql, params)


class _FakeConnCtx:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def __enter__(self) -> _FakeConn:
        return self._conn

    def __exit__(self, *_exc: Any) -> bool:
        return False


class _FakeConnectionManager:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows = rows_by_table

    def connection(self) -> _FakeConnCtx:
        return _FakeConnCtx(_FakeConn(self._rows))


def _install_fake_cm(
    monkeypatch: pytest.MonkeyPatch, rows_by_table: dict[str, Any]
) -> None:
    cm = _FakeConnectionManager(rows_by_table)
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: cm)


# ---------- fixtures ----------


_LATEST_DATE = dt.date(2026, 5, 18)
_CALCULATED_AT = dt.datetime(2026, 5, 18, 21, 30, tzinfo=dt.UTC)


def _make_indicator_row(
    *,
    date: dt.date,
    rsi_14: float = 60.0,
    macd: float = 1.5,
    sma_50: float = 200.0,
    sma_200: float = 180.0,
    atr_14: float = 4.2,
    bb_lower: float = 190.0,
    bb_upper: float = 210.0,
) -> tuple[Any, ...]:
    # Order must match payloads._TECHNICAL_COLUMNS exactly.
    return (
        date,
        _CALCULATED_AT,
        rsi_14,
        macd,
        macd - 0.2,  # macd_signal
        0.3,  # macd_histogram
        bb_upper,
        (bb_upper + bb_lower) / 2,
        bb_lower,
        201.0,  # sma_5
        199.0,  # sma_20
        sma_50,
        sma_200,
        198.0,  # ema_20
        197.0,  # ema_50
        185.0,  # ema_200
        atr_14,
        80.0,  # stoch_k
        78.0,  # stoch_d
    )


# ---------- tests ----------


def test_fetch_technical_indicators_returns_all_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The technical analyst prompt cites these by name; all must be present."""
    rows = [
        _make_indicator_row(date=_LATEST_DATE, sma_50=200.0, sma_200=180.0),
        _make_indicator_row(date=dt.date(2026, 5, 11), sma_50=190.0, sma_200=175.0),
    ]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (205.0,)},
    )

    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None

    required = {
        "date",
        "calculated_at",
        "rsi_14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "sma_5",
        "sma_20",
        "sma_50",
        "sma_200",
        "ema_20",
        "ema_50",
        "ema_200",
        "atr_14",
        "stoch_k",
        "stoch_d",
        "latest_close",
        "ma_slope_50_pct",
        "ma_slope_200_pct",
        "price_vs_sma_50_pct",
        "price_vs_sma_200_pct",
        "rsi_zone",
        "bb_pct_b",
    }
    assert required.issubset(payload.keys()), required - payload.keys()


def test_fetch_technical_indicators_derives_slope_and_zone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        _make_indicator_row(date=_LATEST_DATE, sma_50=210.0, sma_200=180.0, rsi_14=75.0),
        _make_indicator_row(date=dt.date(2026, 5, 11), sma_50=200.0, sma_200=170.0),
    ]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (220.0,)},
    )

    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["ma_slope_50_pct"] == pytest.approx(5.0)
    assert payload["ma_slope_200_pct"] == pytest.approx((10 / 170) * 100)
    assert payload["price_vs_sma_50_pct"] == pytest.approx((10 / 210) * 100)
    assert payload["rsi_zone"] == "overbought"
    assert payload["bb_pct_b"] == pytest.approx(1.5)


def test_fetch_technical_indicators_returns_none_when_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, {"technical_indicators": [], "day_bars": None})
    assert payloads.fetch_technical_indicators("NVDA") is None


def test_fetch_technical_indicators_handles_missing_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_make_indicator_row(date=_LATEST_DATE)]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": None},
    )
    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["latest_close"] is None
    assert payload["price_vs_sma_50_pct"] is None
    assert payload["bb_pct_b"] is None


def test_fetch_technical_indicators_rsi_zone_oversold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [_make_indicator_row(date=_LATEST_DATE, rsi_14=22.0)]
    _install_fake_cm(
        monkeypatch,
        {"technical_indicators": rows, "day_bars": (180.0,)},
    )
    payload = payloads.fetch_technical_indicators("NVDA")
    assert payload is not None
    assert payload["rsi_zone"] == "oversold"


def test_fetch_technical_indicators_returns_none_on_query_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ExplodingConn:
        def execute(self, *_a: Any, **_k: Any) -> Any:
            raise RuntimeError("db down")

    class _ExplodingCtx:
        def __enter__(self) -> _ExplodingConn:
            return _ExplodingConn()

        def __exit__(self, *_e: Any) -> bool:
            return False

    class _ExplodingCM:
        def connection(self) -> _ExplodingCtx:
            return _ExplodingCtx()

    exploder = _ExplodingCM()
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: exploder)
    assert payloads.fetch_technical_indicators("NVDA") is None


def test_fetch_technical_indicators_empty_symbol_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payloads, "get_connection_manager", lambda: None)
    assert payloads.fetch_technical_indicators("") is None
    assert payloads.fetch_technical_indicators("   ") is None
