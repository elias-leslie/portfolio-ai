"""Unified signals API contract tests.

Exercise /api/signals/{blended,rank-deltas,symbol/{ticker}} with the
repository and committee-store reads mocked at the module boundary
inside ``app.api.signals_routes``. No DB.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.signals_routes import router as signals_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(signals_router)
    return TestClient(app)


def _latest_run() -> dict[str, Any]:
    return {
        "run_id": "00000000-0000-0000-0000-000000000001",
        "run_date": "2026-05-17",
        "gate_zone": "FULL_DEPLOY",
        "gate_score": 78.5,
        "universe_size": 504,
        "scored_count": 4,
        "skip_reason": None,
        "started_at": "2026-05-17T22:30:00Z",
        "completed_at": "2026-05-17T22:31:00Z",
    }


def _scores() -> list[dict[str, Any]]:
    return [
        {"symbol": "AAA", "rank": 1, "composite_pct": 90.0, "factor_coverage": 1.0},
        {"symbol": "BBB", "rank": 2, "composite_pct": 80.0, "factor_coverage": 1.0},
        {"symbol": "CCC", "rank": 3, "composite_pct": 70.0, "factor_coverage": 1.0},
        {"symbol": "DDD", "rank": 4, "composite_pct": 60.0, "factor_coverage": 1.0},
    ]


def test_blended_route_returns_committee_promoted_row() -> None:
    committee = {
        "DDD": {
            "run_id": "run-ddd",
            "symbol": "DDD",
            "status": "complete",
            "action": "buy",
            "confidence": 1.0,
            "source": "scanner_fanout",
            "scanner_rank": 4,
            "completed_at": "2026-05-17T22:45:00Z",
        }
    }
    with patch("app.api.signals_routes.scanner_repo.get_latest_run", return_value=_latest_run()), \
         patch("app.api.signals_routes.scanner_repo.get_scores_for_run", return_value=_scores()), \
         patch("app.api.signals_routes.committee_store.get_latest_completed_by_symbol",
               return_value=committee):
        client = _build_client()
        resp = client.get("/api/signals/blended?weight_scanner=0.6&weight_committee=0.4")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run"]["gate_zone"] == "FULL_DEPLOY"
    assert body["weights"] == {"scanner": 0.6, "committee": 0.4}
    by_symbol = {row["symbol"]: row for row in body["rows"]}
    # DDD promoted to #1: 0.6*60 + 0.4*10*10 = 76 vs AAA 0.6*90 = 54.
    assert by_symbol["DDD"]["blended_rank"] == 1
    assert by_symbol["DDD"]["delta_rank"] == 3
    assert by_symbol["DDD"]["flagged"] is True
    assert by_symbol["DDD"]["committee"]["pm_score"] == 10.0


def test_blended_route_503_when_no_scanner_run() -> None:
    with patch("app.api.signals_routes.scanner_repo.get_latest_run", return_value=None):
        client = _build_client()
        resp = client.get("/api/signals/blended")
    assert resp.status_code == 503


def test_rank_deltas_only_returns_flagged_rows() -> None:
    committee = {
        "DDD": {
            "run_id": "run-ddd",
            "symbol": "DDD",
            "status": "complete",
            "action": "buy",
            "confidence": 1.0,
            "source": "scanner_fanout",
            "scanner_rank": 4,
            "completed_at": "2026-05-17T22:45:00Z",
        }
    }
    with patch("app.api.signals_routes.scanner_repo.get_latest_run", return_value=_latest_run()), \
         patch("app.api.signals_routes.scanner_repo.get_scores_for_run", return_value=_scores()), \
         patch("app.api.signals_routes.committee_store.get_latest_completed_by_symbol",
               return_value=committee):
        client = _build_client()
        resp = client.get("/api/signals/rank-deltas?weight_scanner=0.6&weight_committee=0.4")
    assert resp.status_code == 200
    body = resp.json()
    assert body["threshold"] == 3
    assert [row["symbol"] for row in body["rows"]] == ["DDD"]


def test_symbol_unified_returns_macro_scanner_and_committee() -> None:
    macro_snapshot = {
        "snapshot_date": "2026-05-17",
        "zone": "FULL_DEPLOY",
        "deployment_score": 78.5,
        "vix_score": 90.0,
        "term_score": 60.0,
        "breadth_score": 80.0,
        "credit_score": 75.0,
        "putcall_score": 70.0,
        "crowding_score": 65.0,
    }
    scanner_history = [
        {
            "run_date": "2026-05-17",
            "gate_zone": "FULL_DEPLOY",
            "rank": 4,
            "composite_pct": 60.0,
            "factor_coverage": 1.0,
            "mom_xover_pct": 50.0,
            "vol_surge_pct": 60.0,
            "rs_vs_spy_pct": 65.0,
            "high_52w_proximity_pct": 70.0,
            "short_interest_decline_pct": 55.0,
        }
    ]
    committee = {
        "DDD": {
            "run_id": "run-ddd",
            "symbol": "DDD",
            "status": "complete",
            "action": "buy",
            "confidence": 0.8,
            "source": "scanner_fanout",
            "scanner_rank": 4,
            "completed_at": "2026-05-17T22:45:00Z",
        }
    }
    with patch("app.api.signals_routes.macro_repo.get_latest", return_value=macro_snapshot), \
         patch("app.api.signals_routes.scanner_repo.get_history_for_symbol",
               return_value=scanner_history), \
         patch("app.api.signals_routes.committee_store.get_latest_completed_by_symbol",
               return_value=committee):
        client = _build_client()
        resp = client.get("/api/signals/symbol/ddd")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "DDD"
    assert body["macro"]["zone"] == "FULL_DEPLOY"
    assert body["macro"]["components"]["vix"] == 90.0
    assert len(body["scanner"]) == 1
    assert body["committee"]["action"] == "buy"
    assert body["committee"]["pm_score"] == 8.0
    assert body["committee"]["source"] == "scanner_fanout"


def test_symbol_unified_missing_committee_returns_null_block() -> None:
    macro_snapshot = {
        "snapshot_date": "2026-05-17",
        "zone": "FULL_DEPLOY",
        "deployment_score": 78.5,
        "vix_score": 90.0, "term_score": None, "breadth_score": None,
        "credit_score": None, "putcall_score": None, "crowding_score": None,
    }
    with patch("app.api.signals_routes.macro_repo.get_latest", return_value=macro_snapshot), \
         patch("app.api.signals_routes.scanner_repo.get_history_for_symbol", return_value=[]), \
         patch("app.api.signals_routes.committee_store.get_latest_completed_by_symbol",
               return_value={}):
        client = _build_client()
        resp = client.get("/api/signals/symbol/zzz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["committee"] is None
    assert body["scanner"] == []
    assert body["macro"]["components"]["term"] is None


def test_committee_cost_route_assembles_per_day_rollup() -> None:
    """The cost endpoint returns one CommitteeCostDay per requested day."""

    def fake_rows(_days: int) -> list:
        import app.api.signals_routes as mod

        return [
            mod.CommitteeCostDay(
                date="2026-05-18",
                fan_out_count=1,
                tier1_call_count=25,
                deep_run_count=5,
                total_tokens=18_750,
                est_cost_usd=0.0563,
            )
        ]

    with patch("app.api.signals_routes._committee_cost_rows", side_effect=fake_rows):
        client = _build_client()
        resp = client.get("/api/signals/committee/cost?days=1")

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "days": [
            {
                "date": "2026-05-18",
                "fan_out_count": 1,
                "tier1_call_count": 25,
                "deep_run_count": 5,
                "total_tokens": 18_750,
                "est_cost_usd": 0.0563,
            }
        ]
    }


def test_committee_cost_rows_estimates_cost_when_runs_have_zero_cost() -> None:
    """If committee_runs.cost_usd is 0, fall back to per-token estimate."""
    import datetime as dt

    import pytest as _pytest

    import app.api.signals_routes as mod

    class _FakeCursor:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def fetchall(self) -> list:
            return self._rows

    class _FakeConn:
        def __init__(self, rows_by_marker: dict) -> None:
            self._rows = rows_by_marker

        def execute(self, sql: str, _params: Any) -> _FakeCursor:
            if "source = 'scanner_fanout'" in sql:
                return _FakeCursor(self._rows.get("fanout", []))
            if "tier1-screener-v1" in sql:
                return _FakeCursor(self._rows.get("tier1", []))
            if "status = 'complete'" in sql:
                return _FakeCursor(self._rows.get("deep", []))
            raise AssertionError(f"unexpected SQL: {sql}")

    class _Ctx:
        def __init__(self, conn: _FakeConn) -> None:
            self._conn = conn

        def __enter__(self) -> _FakeConn:
            return self._conn

        def __exit__(self, *_e: Any) -> bool:
            return False

    class _FakeCM:
        def __init__(self, conn: _FakeConn) -> None:
            self._conn = conn

        def connection(self) -> _Ctx:
            return _Ctx(self._conn)

    today = dt.datetime.now(dt.UTC).date()
    rows = {
        "fanout": [(today, 2)],
        "tier1": [(today, 25, 10_000)],
        "deep": [(today, 5, 5_000, 0)],
    }
    cm = _FakeCM(_FakeConn(rows))
    with patch("app.api.signals_routes.get_connection_manager", return_value=cm):
        out = mod._committee_cost_rows(days=1)

    assert len(out) == 1
    row = out[0]
    assert row.fan_out_count == 2
    assert row.tier1_call_count == 25
    assert row.deep_run_count == 5
    # Tier-1 tokens (10k) + deep-run tokens (5k) = 15k; cost_usd was 0
    # so the response uses the per-token fallback (15_000 * 3e-6).
    assert row.total_tokens == 15_000
    assert row.est_cost_usd == _pytest.approx(15_000 * 0.000003, abs=1e-4)
