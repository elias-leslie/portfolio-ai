"""Tests for the L3 committee fan-out kernel.

Exercises the gate-zone short-circuit, cache filtering, rate cap, and
the ``source='scanner_fanout' + scanner_rank`` tagging via mocked
repositories. The asyncio dispatch step is short-circuited by *not*
passing a loop — the kernel records planned spawns instead.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch
from uuid import uuid4

from app.agents.committee import cache as cache_mod
from app.workflows import committee_fanout as fanout_mod


def _scanner_row(symbol: str, rank: int) -> dict:
    return {
        "symbol": symbol,
        "rank": rank,
        "composite_pct": 100.0 - rank,
        "factor_coverage": 1.0,
    }


def test_defensive_zone_short_circuits() -> None:
    run_id = uuid4()
    latest = {
        "run_id": str(run_id),
        "run_date": "2026-05-17",
        "gate_zone": "DEFENSIVE",
        "universe_size": 504,
        "scored_count": 0,
        "skip_reason": "gate_defensive",
    }
    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=latest), \
         patch.object(fanout_mod.scanner_repo, "get_scores_for_run") as get_scores, \
         patch.object(fanout_mod.committee_store, "create_run") as create_run:
        out = fanout_mod.run_fanout(top_n=10, max_daily=10)
    assert out.skip_reason == "gate_defensive"
    assert out.spawned == []
    get_scores.assert_not_called()
    create_run.assert_not_called()


def test_no_scanner_run_returns_skip() -> None:
    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=None):
        out = fanout_mod.run_fanout(top_n=10, max_daily=10)
    assert out.skip_reason == "no_scanner_run"
    assert out.spawned == []


def test_cache_hits_skip_individual_symbols() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    run_id = uuid4()
    latest = {
        "run_id": str(run_id),
        "run_date": "2026-05-17",
        "gate_zone": "FULL_DEPLOY",
        "universe_size": 504,
        "scored_count": 5,
        "skip_reason": None,
    }
    scores = [_scanner_row("AAA", 1), _scanner_row("BBB", 2), _scanner_row("CCC", 3)]
    created: list[dict] = []

    def fake_create_run(**kw):
        created.append(kw)
        return f"run-{kw['symbol']}"

    def fake_should_run(ticker: str, *, current_zone: str, now=None):
        # BBB is cached fresh; AAA and CCC are eligible.
        if ticker == "BBB":
            return cache_mod.CacheDecision(should_run=False, reason="fresh_within_ttl",
                                           last_run_id="prev-bbb")
        return cache_mod.CacheDecision(should_run=True, reason="no_prior_run")

    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=latest), \
         patch.object(fanout_mod.scanner_repo, "get_scores_for_run", return_value=scores), \
         patch.object(fanout_mod, "_count_fanout_today", return_value=0), \
         patch.object(fanout_mod.cache, "should_run", side_effect=fake_should_run), \
         patch.object(fanout_mod.committee_store, "create_run", side_effect=fake_create_run):
        out = fanout_mod.run_fanout(top_n=10, max_daily=10, now=now)

    spawned_syms = [s["symbol"] for s in out.spawned]
    skipped_syms = [s["symbol"] for s in out.skipped]
    assert "AAA" in spawned_syms and "CCC" in spawned_syms
    assert "BBB" in skipped_syms
    assert any(s["reason"] == "fresh_within_ttl" for s in out.skipped)
    # Tagging: each spawn carries source=scanner_fanout + the rank
    assert all(kw["source"] == "scanner_fanout" for kw in created)
    ranks = {kw["symbol"]: kw["scanner_rank"] for kw in created}
    assert ranks == {"AAA": 1, "CCC": 3}


def test_rate_cap_short_circuits_when_budget_already_exhausted() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    run_id = uuid4()
    latest = {
        "run_id": str(run_id),
        "run_date": "2026-05-17",
        "gate_zone": "FULL_DEPLOY",
        "universe_size": 504,
        "scored_count": 5,
        "skip_reason": None,
    }
    scores = [_scanner_row(f"S{i}", i + 1) for i in range(5)]
    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=latest), \
         patch.object(fanout_mod.scanner_repo, "get_scores_for_run", return_value=scores), \
         patch.object(fanout_mod, "_count_fanout_today", return_value=10), \
         patch.object(fanout_mod.cache, "should_run") as should_run_mock, \
         patch.object(fanout_mod.committee_store, "create_run") as create_run:
        out = fanout_mod.run_fanout(top_n=10, max_daily=10, now=now)
    assert out.skip_reason == "max_daily_reached"
    assert out.spawned == []
    assert {s["symbol"] for s in out.skipped} == {f"S{i}" for i in range(5)}
    should_run_mock.assert_not_called()
    create_run.assert_not_called()


def test_rate_cap_trims_to_remaining_budget() -> None:
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    run_id = uuid4()
    latest = {
        "run_id": str(run_id),
        "run_date": "2026-05-17",
        "gate_zone": "FULL_DEPLOY",
        "universe_size": 504,
        "scored_count": 5,
        "skip_reason": None,
    }
    scores = [_scanner_row(f"S{i}", i + 1) for i in range(5)]
    created: list[dict] = []

    def fake_create_run(**kw):
        created.append(kw)
        return f"run-{kw['symbol']}"

    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=latest), \
         patch.object(fanout_mod.scanner_repo, "get_scores_for_run", return_value=scores), \
         patch.object(fanout_mod, "_count_fanout_today", return_value=8), \
         patch.object(fanout_mod.cache, "should_run",
                      return_value=cache_mod.CacheDecision(should_run=True, reason="no_prior_run")), \
         patch.object(fanout_mod.committee_store, "create_run", side_effect=fake_create_run):
        out = fanout_mod.run_fanout(top_n=10, max_daily=10, now=now)
    # Budget = 10 - 8 = 2 spawns allowed.
    assert len(out.spawned) == 2
    assert [s["symbol"] for s in out.spawned] == ["S0", "S1"]
    assert all(s["reason"] == "max_daily_reached" for s in out.skipped)
    assert [s["symbol"] for s in out.skipped] == ["S2", "S3", "S4"]
    assert len(created) == 2


def test_no_loop_means_runs_recorded_but_not_dispatched() -> None:
    """Without a running loop, spawns are tagged but no asyncio tasks fire."""
    now = datetime(2026, 5, 17, 18, 0, tzinfo=UTC)
    run_id = uuid4()
    latest = {
        "run_id": str(run_id),
        "run_date": "2026-05-17",
        "gate_zone": "FULL_DEPLOY",
        "universe_size": 504,
        "scored_count": 1,
        "skip_reason": None,
    }
    scores = [_scanner_row("AAA", 1)]
    with patch.object(fanout_mod.scanner_repo, "get_latest_run", return_value=latest), \
         patch.object(fanout_mod.scanner_repo, "get_scores_for_run", return_value=scores), \
         patch.object(fanout_mod, "_count_fanout_today", return_value=0), \
         patch.object(fanout_mod.cache, "should_run",
                      return_value=cache_mod.CacheDecision(should_run=True, reason="no_prior_run")), \
         patch.object(fanout_mod.committee_store, "create_run", return_value="run-AAA"):
        out = fanout_mod.run_fanout(top_n=10, max_daily=10, now=now)
    assert [s["symbol"] for s in out.spawned] == ["AAA"]
