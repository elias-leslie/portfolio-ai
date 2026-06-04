from __future__ import annotations

from contextlib import contextmanager
from datetime import date

from app.macro_gate.signals import fear_greed_components as fgc


class _FakeResult:
    def __init__(self, row: tuple | None) -> None:
        self._row = row

    def fetchone(self) -> tuple | None:
        return self._row


class _FakeConn:
    """Routes the three queries in ``_build`` by inspecting the SQL text."""

    def __init__(self, latest_row: tuple | None, vix_row: tuple | None, hy_row: tuple | None) -> None:
        self._latest_row = latest_row
        self._vix_row = vix_row
        self._hy_row = hy_row

    def execute(self, sql: str, params: list | None = None) -> _FakeResult:
        if "vix_close IS NOT NULL" in sql:
            return _FakeResult(self._vix_row)
        if "hy_spread IS NOT NULL" in sql:
            return _FakeResult(self._hy_row)
        return _FakeResult(self._latest_row)


class _FakeStorage:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    @contextmanager
    def connection(self):
        yield self._conn


def _patch_storage(monkeypatch, conn: _FakeConn) -> None:
    monkeypatch.setattr(fgc, "get_storage", lambda: _FakeStorage(conn))


def test_fetch_latest_carries_forward_vix_and_hy_on_holiday(monkeypatch) -> None:
    # Latest row is a put/call-only skeleton inserted on a market holiday
    # (Memorial Day, Mon 2026-05-25); VIX and HY last printed on the prior
    # trading day (Fri 2026-05-22).
    conn = _FakeConn(
        latest_row=(date(2026, 5, 25), 1.4615, None),
        vix_row=(16.7, date(2026, 5, 22)),
        hy_row=(2.74, date(2026, 5, 22)),
    )
    _patch_storage(monkeypatch, conn)

    components = fgc.fetch_latest()

    assert components is not None
    assert components.as_of == date(2026, 5, 25)
    assert components.put_call_ratio == 1.4615
    # VIX is intraday: yesterday's close is not a current quote, so the
    # carried-forward daily close is flagged stale.
    assert components.vix_close == 16.7
    assert components.vix_as_of == date(2026, 5, 22)
    assert components.vix_stale is True
    # HY OAS is T+1 daily: Friday's print on a Monday holiday is within cadence,
    # not stale. Labelling it STALE every day was the bug this fixes.
    assert components.hy_spread == 2.74
    assert components.hy_spread_as_of == date(2026, 5, 22)
    assert components.hy_spread_stale is False


def test_fetch_latest_flags_genuinely_stuck_credit(monkeypatch) -> None:
    # HY trails the most recent trading day by more than its T+1 cadence
    # (latest row Thu 2026-05-28; HY last printed Fri 2026-05-22 -> 4 trading
    # days behind) -> genuinely stale, not just within-cadence lag.
    conn = _FakeConn(
        latest_row=(date(2026, 5, 28), 0.97, 60.0),
        vix_row=(17.0, date(2026, 5, 28)),
        hy_row=(2.74, date(2026, 5, 22)),
    )
    _patch_storage(monkeypatch, conn)

    components = fgc.fetch_latest()

    assert components is not None
    assert components.hy_spread_as_of == date(2026, 5, 22)
    assert components.hy_spread_stale is True


def test_fetch_latest_credit_within_t_plus_one_is_fresh(monkeypatch) -> None:
    # Normal weekday: latest row Thu 2026-05-28, HY printed Wed 2026-05-27
    # (Thursday morning still carries Wednesday's T+1 value) -> within cadence.
    conn = _FakeConn(
        latest_row=(date(2026, 5, 28), 0.97, 60.0),
        vix_row=(17.0, date(2026, 5, 28)),
        hy_row=(2.74, date(2026, 5, 27)),
    )
    _patch_storage(monkeypatch, conn)

    components = fgc.fetch_latest()

    assert components is not None
    assert components.hy_spread_as_of == date(2026, 5, 27)
    assert components.hy_spread_stale is False


def test_fetch_latest_marks_fresh_on_trading_day(monkeypatch) -> None:
    # On a trading day every series prints for the same date: nothing is stale.
    conn = _FakeConn(
        latest_row=(date(2026, 5, 26), 0.97, 63.6),
        vix_row=(17.01, date(2026, 5, 26)),
        hy_row=(2.74, date(2026, 5, 26)),
    )
    _patch_storage(monkeypatch, conn)

    components = fgc.fetch_latest()

    assert components is not None
    assert components.vix_close == 17.01
    assert components.vix_stale is False
    assert components.hy_spread_stale is False
    assert components.breadth_pct == 63.6


def test_fetch_latest_returns_none_when_table_empty(monkeypatch) -> None:
    conn = _FakeConn(latest_row=None, vix_row=None, hy_row=None)
    _patch_storage(monkeypatch, conn)

    assert fgc.fetch_latest() is None


def test_fetch_latest_handles_no_prior_vix(monkeypatch) -> None:
    # Cold start: a row exists but VIX/HY have never printed.
    conn = _FakeConn(
        latest_row=(date(2026, 5, 25), 1.1, None),
        vix_row=None,
        hy_row=None,
    )
    _patch_storage(monkeypatch, conn)

    components = fgc.fetch_latest()

    assert components is not None
    assert components.vix_close is None
    assert components.vix_as_of is None
    assert components.vix_stale is False
    assert components.hy_spread is None
