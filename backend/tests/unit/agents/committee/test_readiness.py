"""Tests for the committee data-readiness gate.

Each ``_check_*`` helper inside ``readiness`` runs one SQL query
against the connection manager. Tests monkeypatch the connection
manager with an in-memory fake whose ``execute`` returns a stubbed
``fetchone``. This pins the per-check policy without standing up a
real DB.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from app.agents.committee import readiness

# ---------- in-memory connection fake ----------


class _FakeCursor:
    def __init__(self, rows_by_table: dict[str, Any]):
        self._rows = rows_by_table
        self._next: Any = None

    def execute(self, sql: str, _params: Any = None) -> _FakeCursor:
        sql_lower = sql.lower()
        if "from day_bars" in sql_lower:
            self._next = self._rows.get("day_bars")
        elif "from technical_indicators" in sql_lower:
            self._next = self._rows.get("technical_indicators")
        elif "from watchlist_snapshots" in sql_lower:
            self._next = self._rows.get("watchlist_snapshots")
        elif "from news_cache" in sql_lower:
            self._next = self._rows.get("news_cache")
        else:
            raise AssertionError(f"unexpected query: {sql}")
        return self

    def fetchone(self) -> Any:
        return self._next


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
    monkeypatch.setattr(readiness, "get_connection_manager", lambda: cm)


# ---------- fixture rows ----------


_NOW = dt.datetime(2026, 5, 18, 14, 0, tzinfo=dt.UTC)
_FRESH_DATE = dt.date(2026, 5, 18)
_STALE_DATE = dt.date(2026, 4, 1)


def _fresh_ohlcv_row(close: float = 200.0) -> tuple[dt.date, float]:
    return (_FRESH_DATE, close)


def _fresh_indicator_row() -> tuple[Any, ...]:
    # Order must match readiness._INDICATOR_REQUIRED_FIELDS: rsi_14, macd, atr_14, sma_50, sma_200
    return (_FRESH_DATE, 55.0, 1.2, 3.4, 195.0, 180.0)


def _fresh_watchlist_row() -> tuple[Any, ...]:
    fetched = _NOW - dt.timedelta(hours=1)
    return (fetched, False, 70.0, 78.0)


def _news_count_row(count: int = 5, hours_ago: float = 6.0) -> tuple[int, dt.datetime]:
    last_pub = _NOW - dt.timedelta(hours=hours_ago)
    return (count, last_pub)


def _all_fresh_rows() -> dict[str, Any]:
    return {
        "day_bars": _fresh_ohlcv_row(),
        "technical_indicators": _fresh_indicator_row(),
        "watchlist_snapshots": _fresh_watchlist_row(),
        "news_cache": _news_count_row(),
    }


# ---------- tests ----------


def test_check_committee_readiness_ok_when_all_data_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, _all_fresh_rows())
    report = readiness.check_committee_readiness("NVDA", now=_NOW)
    assert report.ok is True
    assert report.symbol == "NVDA"
    assert report.blocking_issues == ()


def test_blocks_when_ohlcv_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["day_bars"] = None
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert report.ok is False
    checks = {i.check for i in report.blocking_issues}
    assert "ohlcv_missing" in checks


def test_blocks_when_ohlcv_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["day_bars"] = (_STALE_DATE, 200.0)
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert report.ok is False
    assert any(i.check == "ohlcv_stale" for i in report.blocking_issues)


def test_blocks_when_ohlcv_close_is_null(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["day_bars"] = (_FRESH_DATE, None)
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(i.check == "ohlcv_no_price" for i in report.blocking_issues)
    assert report.ok is False


def test_blocks_when_indicator_row_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["technical_indicators"] = None
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(i.check == "indicators_missing" for i in report.blocking_issues)


def test_blocks_when_indicators_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    # ATR is null — analyst can't size stops without it.
    rows["technical_indicators"] = (_FRESH_DATE, 55.0, 1.2, None, 195.0, 180.0)
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    blocking = [i for i in report.blocking_issues if i.check == "indicators_incomplete"]
    assert blocking
    assert "atr_14" in blocking[0].detail


def test_blocks_when_watchlist_snapshot_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    rows["watchlist_snapshots"] = None
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(
        i.check == "watchlist_snapshot_missing" for i in report.blocking_issues
    )


def test_warns_when_is_stale_flag_set_but_fresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    fetched = _NOW - dt.timedelta(hours=1)
    # Snapshot is fresh by age (1h < 6h block) but flag is set.
    rows["watchlist_snapshots"] = (fetched, True, 70.0, 78.0)
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert report.ok is True
    assert any(
        i.check == "watchlist_is_stale_flag" for i in report.warning_issues
    )


def test_blocks_when_watchlist_snapshot_aged_past_block_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    rows["watchlist_snapshots"] = (
        _NOW - dt.timedelta(hours=12),
        False,
        70.0,
        78.0,
    )
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(
        i.check == "watchlist_snapshot_stale" for i in report.blocking_issues
    )


def test_blocks_when_watchlist_snapshot_aged_past_critical_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    rows["watchlist_snapshots"] = (
        _NOW - dt.timedelta(hours=72),
        False,
        70.0,
        78.0,
    )
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(
        i.check == "watchlist_snapshot_critical" for i in report.blocking_issues
    )


def test_blocks_when_no_news_in_window(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["news_cache"] = (0, None)
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert any(i.check == "news_empty" for i in report.blocking_issues)


def test_warns_when_news_sparse_and_old(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _all_fresh_rows()
    rows["news_cache"] = (1, _NOW - dt.timedelta(hours=120))
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    assert report.ok is True
    assert any(i.check == "news_sparse" for i in report.warning_issues)


def test_collects_every_issue_not_just_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symbol with multiple problems should surface all of them at once.

    Forcing the caller to retry-and-discover each issue serially would
    waste both LLM credit and user attention.
    """
    rows = {
        "day_bars": None,
        "technical_indicators": None,
        "watchlist_snapshots": None,
        "news_cache": (0, None),
    }
    _install_fake_cm(monkeypatch, rows)
    report = readiness.check_committee_readiness("FOO", now=_NOW)
    checks = {i.check for i in report.blocking_issues}
    assert {
        "ohlcv_missing",
        "indicators_missing",
        "watchlist_snapshot_missing",
        "news_empty",
    } <= checks


def test_assert_committee_ready_raises_on_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = _all_fresh_rows()
    rows["news_cache"] = (0, None)
    _install_fake_cm(monkeypatch, rows)
    with pytest.raises(readiness.CommitteeDataUnreadyError) as excinfo:
        readiness.assert_committee_ready("FOO", now=_NOW)
    assert "news_empty" in str(excinfo.value)
    assert excinfo.value.report.ok is False


def test_assert_committee_ready_returns_report_on_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_cm(monkeypatch, _all_fresh_rows())
    report = readiness.assert_committee_ready("nvda", now=_NOW)
    assert report.ok is True
    assert report.symbol == "NVDA"


def test_empty_symbol_blocks_without_querying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom() -> Any:
        raise AssertionError("should not query DB for empty symbol")

    monkeypatch.setattr(readiness, "get_connection_manager", _boom)
    report = readiness.check_committee_readiness("   ")
    assert report.ok is False
    assert report.blocking_issues[0].check == "symbol_invalid"
