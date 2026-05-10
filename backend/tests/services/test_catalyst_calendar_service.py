"""Unit tests for CatalystCalendarService (F4).

These tests stub the storage connection and the per-kind cache
helpers; the goal is to nail the merge / sort / window-clipping
semantics, not exercise the underlying yfinance / FOMC plumbing.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.catalyst_calendar_service import (
    CatalystCalendarService,
    _coerce_date,
    _to_catalyst,
)


class _StubConn:
    """Tiny ``connection()`` context that returns canned rows."""

    def __init__(
        self,
        positions: list[str] | None = None,
        watchlist: list[str] | None = None,
        fomc_rows: list[tuple[Any, str, str]] | None = None,
    ) -> None:
        self._positions = positions or []
        self._watchlist = watchlist or []
        self._fomc = fomc_rows or []
        self.commit = MagicMock()

    def execute(self, sql: str, params: Any = None) -> Any:
        normalized = " ".join(sql.split()).lower()
        if "from portfolio_positions" in normalized:
            rows = [(s,) for s in self._positions]
        elif "from watchlist_items" in normalized:
            rows = [(s,) for s in self._watchlist]
        elif "from fomc_meetings" in normalized:
            rows = list(self._fomc)
        else:  # pragma: no cover - test should exercise known paths
            raise AssertionError(f"unexpected SQL: {sql}")
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        return cursor


class _StubStorage:
    def __init__(self, conn: _StubConn) -> None:
        self._conn = conn

    def connection(self) -> Any:
        class _Ctx:
            def __init__(self, conn: _StubConn) -> None:
                self._conn = conn

            def __enter__(self) -> _StubConn:
                return self._conn

            def __exit__(self, *_: Any) -> None:
                pass

        return _Ctx(self._conn)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def test_to_catalyst_clips_outside_window() -> None:
    anchor = date(2026, 5, 9)
    cutoff = date(2026, 5, 23)
    too_far = _to_catalyst("AAPL", "earnings", datetime(2026, 6, 30), anchor, cutoff)
    assert too_far is None
    in_window = _to_catalyst("AAPL", "earnings", datetime(2026, 5, 15), anchor, cutoff)
    assert in_window is not None
    assert in_window.symbol == "AAPL"
    assert in_window.kind == "earnings"
    assert in_window.days_until == 6


def test_coerce_date_accepts_date_datetime_str() -> None:
    assert _coerce_date(date(2026, 5, 9)) == date(2026, 5, 9)
    assert _coerce_date(datetime(2026, 5, 9, 13, 0)) == date(2026, 5, 9)
    assert _coerce_date("2026-05-09") == date(2026, 5, 9)
    assert _coerce_date("not-a-date") is None
    assert _coerce_date(None) is None


# ----------------------------------------------------------------------
# universe resolution
# ----------------------------------------------------------------------


def test_explicit_symbol_universe_overrides_storage() -> None:
    conn = _StubConn(positions=["AAPL"], watchlist=["MSFT"])
    service = CatalystCalendarService(_StubStorage(conn))
    universe = service._resolve_symbol_universe(
        ["nvda", "AAPL", " "], include_watchlist=True
    )
    assert universe == ["NVDA", "AAPL"]


def test_default_universe_unions_portfolio_and_watchlist() -> None:
    conn = _StubConn(positions=["AAPL", "MSFT"], watchlist=["MSFT", "GOOGL"])
    service = CatalystCalendarService(_StubStorage(conn))
    universe = service._resolve_symbol_universe(None, include_watchlist=True)
    # Portfolio first; deduped against watchlist.
    assert universe == ["AAPL", "MSFT", "GOOGL"]


def test_default_universe_excludes_watchlist_when_disabled() -> None:
    conn = _StubConn(positions=["AAPL"], watchlist=["GOOGL"])
    service = CatalystCalendarService(_StubStorage(conn))
    assert service._resolve_symbol_universe(None, include_watchlist=False) == ["AAPL"]


# ----------------------------------------------------------------------
# upcoming() integration over stubbed sources
# ----------------------------------------------------------------------


def _earnings_lookup(canned: dict[str, datetime | None]):
    def _impl(_conn: Any, symbol: str, ttl_days: int = 30) -> datetime | None:
        del ttl_days
        return canned.get(symbol)

    return _impl


def _exdiv_lookup(canned: dict[str, datetime | None]):
    def _impl(_conn: Any, symbol: str, ttl_days: int = 30) -> datetime | None:
        del ttl_days
        return canned.get(symbol)

    return _impl


def test_upcoming_merges_kinds_and_sorts_by_date() -> None:
    today = date(2026, 5, 9)
    earnings = {"AAPL": datetime(2026, 5, 18), "MSFT": datetime(2026, 7, 1)}
    exdiv = {"AAPL": datetime(2026, 5, 12)}
    fomc_rows = [(date(2026, 5, 14), "press_conference", "federalreserve.gov")]
    conn = _StubConn(
        positions=["AAPL", "MSFT"], watchlist=[], fomc_rows=fomc_rows
    )
    service = CatalystCalendarService(_StubStorage(conn))
    with (
        patch(
            "app.services.catalyst_calendar_service.fetch_earnings_date_cached",
            side_effect=_earnings_lookup(earnings),
        ),
        patch(
            "app.services.catalyst_calendar_service.fetch_ex_dividend_date_cached",
            side_effect=_exdiv_lookup(exdiv),
        ),
    ):
        rows = service.upcoming(None, days=14, today=today)

    assert [(r.symbol, r.kind, r.date) for r in rows] == [
        ("AAPL", "ex_dividend", date(2026, 5, 12)),
        ("", "fomc", date(2026, 5, 14)),
        ("AAPL", "earnings", date(2026, 5, 18)),
    ]
    # MSFT earnings was outside the 14-day window — must be clipped.
    assert all(r.symbol != "MSFT" for r in rows)


def test_upcoming_respects_kinds_filter() -> None:
    today = date(2026, 5, 9)
    earnings = {"AAPL": datetime(2026, 5, 12)}
    exdiv = {"AAPL": datetime(2026, 5, 15)}
    conn = _StubConn(
        positions=["AAPL"],
        fomc_rows=[(date(2026, 5, 14), "regular", "federalreserve.gov")],
    )
    service = CatalystCalendarService(_StubStorage(conn))
    with (
        patch(
            "app.services.catalyst_calendar_service.fetch_earnings_date_cached",
            side_effect=_earnings_lookup(earnings),
        ),
        patch(
            "app.services.catalyst_calendar_service.fetch_ex_dividend_date_cached",
            side_effect=_exdiv_lookup(exdiv),
        ),
    ):
        rows = service.upcoming(
            None, days=10, today=today, kinds=["earnings", "fomc"]
        )

    kinds = {r.kind for r in rows}
    assert kinds == {"earnings", "fomc"}


def test_upcoming_caps_limit_and_days_defensively() -> None:
    today = date(2026, 5, 9)
    conn = _StubConn(positions=["AAPL"])
    service = CatalystCalendarService(_StubStorage(conn))
    with (
        patch(
            "app.services.catalyst_calendar_service.fetch_earnings_date_cached",
            side_effect=_earnings_lookup({"AAPL": datetime(2026, 5, 10)}),
        ),
        patch(
            "app.services.catalyst_calendar_service.fetch_ex_dividend_date_cached",
            side_effect=_exdiv_lookup({}),
        ),
    ):
        rows = service.upcoming(None, days=10_000, limit=10_000, today=today)
    # Only the AAPL earnings within tomorrow should land — bounds didn't
    # blow the query out.
    assert len(rows) == 1
    assert rows[0].symbol == "AAPL"


def test_upcoming_returns_empty_when_universe_is_empty() -> None:
    conn = _StubConn(positions=[], watchlist=[])
    service = CatalystCalendarService(_StubStorage(conn))
    with (
        patch(
            "app.services.catalyst_calendar_service.fetch_earnings_date_cached",
            side_effect=_earnings_lookup({}),
        ),
        patch(
            "app.services.catalyst_calendar_service.fetch_ex_dividend_date_cached",
            side_effect=_exdiv_lookup({}),
        ),
    ):
        rows = service.upcoming(None, today=date(2026, 5, 9))
    assert rows == []


_ = pytest
