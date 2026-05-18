"""Cross-run cache tests for the committee fan-out cost guard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.agents.committee import cache


class _FakeConn:
    def __init__(self, rows_by_sql: dict[str, object | None]):
        self._rows = rows_by_sql

    def execute(self, sql: str, params=None) -> _FakeConn:
        # Route by which table the statement targets.
        if "committee_runs" in sql:
            self._last = self._rows.get("committee_runs")
        elif "signal_macro_snapshots" in sql:
            self._last = self._rows.get("signal_macro_snapshots")
        else:
            self._last = None
        return self

    def fetchone(self) -> object | None:
        return self._last


class _FakeManager:
    def __init__(self, conn: _FakeConn):
        self._conn = conn

    def connection(self):
        class _Ctx:
            def __init__(self, c):
                self._c = c

            def __enter__(self_inner):  # noqa: N805
                return self_inner._c

            def __exit__(self_inner, *exc):  # noqa: N805
                return False

        return _Ctx(self._conn)


def _patch_db(rows: dict[str, object | None]):
    return patch.object(
        cache, "get_connection_manager", MagicMock(return_value=_FakeManager(_FakeConn(rows)))
    )


def test_no_prior_run_returns_should_run_true() -> None:
    with _patch_db({"committee_runs": None}):
        decision = cache.should_run("AAPL", current_zone="FULL_DEPLOY")
    assert decision.should_run is True
    assert decision.reason == "no_prior_run"


def test_recent_same_zone_blocks_run() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    last_completed = now - timedelta(hours=2)
    rows = {
        "committee_runs": ("00000000-0000-0000-0000-000000000001", last_completed, "scanner_fanout"),
        "signal_macro_snapshots": ("FULL_DEPLOY",),
    }
    with _patch_db(rows):
        decision = cache.should_run("AAPL", current_zone="FULL_DEPLOY", now=now)
    assert decision.should_run is False
    assert decision.reason == "fresh_within_ttl"
    assert decision.last_zone == "FULL_DEPLOY"


def test_expired_prior_run_allows_rerun() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    last_completed = now - timedelta(hours=30)
    rows = {
        "committee_runs": ("00000000-0000-0000-0000-000000000001", last_completed, "scanner_fanout"),
        "signal_macro_snapshots": ("FULL_DEPLOY",),
    }
    with _patch_db(rows):
        decision = cache.should_run("AAPL", current_zone="FULL_DEPLOY", now=now)
    assert decision.should_run is True
    assert decision.reason == "prior_run_expired"


def test_zone_shift_invalidates_cache() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    last_completed = now - timedelta(hours=2)
    rows = {
        "committee_runs": ("00000000-0000-0000-0000-000000000001", last_completed, "scanner_fanout"),
        "signal_macro_snapshots": ("REDUCED",),
    }
    with _patch_db(rows):
        decision = cache.should_run("AAPL", current_zone="FULL_DEPLOY", now=now)
    assert decision.should_run is True
    assert decision.reason == "zone_shifted"
    assert decision.last_zone == "REDUCED"


def test_empty_symbol_returns_false() -> None:
    decision = cache.should_run("   ", current_zone="FULL_DEPLOY")
    assert decision.should_run is False
    assert decision.reason == "empty_symbol"


def test_naive_datetime_treated_as_utc() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    naive = (now - timedelta(hours=2)).replace(tzinfo=None)
    rows = {
        "committee_runs": ("00000000-0000-0000-0000-000000000001", naive, "scanner_fanout"),
        "signal_macro_snapshots": ("FULL_DEPLOY",),
    }
    with _patch_db(rows):
        decision = cache.should_run("AAPL", current_zone="FULL_DEPLOY", now=now)
    assert decision.should_run is False
    assert decision.reason == "fresh_within_ttl"
