"""Unit tests for the MCP server tool wrappers.

Each tool is a thin adapter over a repository — these tests stub the
repositories and assert that the tools shape the return value correctly
(tier/kind tagging, clamping, missing-row fallbacks, 24-hour filtering).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.mcp_server import server as mcp_server
from app.scanner.factors import FACTOR_NAMES

# --------------------------------------------------------------- helpers


def _macro_snapshot(snapshot_date: str, deployment_score: float, zone: str) -> dict[str, Any]:
    return {
        "snapshot_date": snapshot_date,
        "vix_close": 18.0,
        "term_spread_bps": 25.0,
        "breadth_pct": 60.0,
        "hy_spread": 3.5,
        "put_call_ratio": 0.85,
        "factor_crowding_corr": 0.12,
        "vix_score": 70.0,
        "term_score": 65.0,
        "breadth_score": 60.0,
        "credit_score": 80.0,
        "putcall_score": 55.0,
        "crowding_score": 50.0,
        "deployment_score": deployment_score,
        "zone": zone,
        "raw_json": {},
        "computed_at": f"{snapshot_date}T17:30:00",
    }


def _committee_row(
    *,
    status: str,
    completed_at: str | None,
    symbol: str = "AAPL",
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "symbol": symbol,
        "status": status,
        "decision_action": "buy" if status in {"complete", "approved"} else None,
        "decision_pct_portfolio": 2.5,
        "confidence": 0.7,
        "parent_run_id": None,
        "started_at": completed_at,
        "completed_at": completed_at,
    }


def _patch_macro(monkeypatch: pytest.MonkeyPatch, *, latest: dict[str, Any] | None, history: list[dict[str, Any]]) -> None:
    def fake_get_latest() -> dict[str, Any] | None:
        return latest

    def fake_get_history(days: int) -> list[dict[str, Any]]:
        assert days > 0
        return history

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)
    monkeypatch.setattr(mcp_server.macro_repo, "get_history", fake_get_history)


# --------------------------------------------------------------- get_deployment_zone


def test_get_deployment_zone_returns_none_fields_when_no_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_macro(monkeypatch, latest=None, history=[])

    result = mcp_server.get_deployment_zone()

    assert result["tier"] == "L1"
    assert result["kind"] == "deterministic"
    assert result["snapshot_date"] is None
    assert result["zone"] is None
    assert result["deployment_score"] is None
    assert result["components"] == {
        "vix": None, "term": None, "breadth": None,
        "credit": None, "putcall": None, "crowding": None,
    }
    assert result["trend"] == {"delta_7d": None, "prior_score": None, "prior_date": None}


def test_get_deployment_zone_computes_components_and_trend(monkeypatch: pytest.MonkeyPatch) -> None:
    today = _macro_snapshot("2026-05-18", deployment_score=72.0, zone="FULL_DEPLOY")
    history = [
        _macro_snapshot("2026-05-10", deployment_score=60.0, zone="REDUCED"),
        _macro_snapshot("2026-05-11", deployment_score=62.0, zone="REDUCED"),
        _macro_snapshot("2026-05-18", deployment_score=72.0, zone="FULL_DEPLOY"),
    ]
    _patch_macro(monkeypatch, latest=today, history=history)

    result = mcp_server.get_deployment_zone()

    assert result["zone"] == "FULL_DEPLOY"
    assert result["deployment_score"] == 72.0
    assert result["components"]["vix"] == 70.0
    assert result["components"]["crowding"] == 50.0
    # 2026-05-11 is the latest sample at or before 2026-05-18 minus 7d.
    assert result["trend"]["prior_date"] == "2026-05-11"
    assert result["trend"]["prior_score"] == 62.0
    assert result["trend"]["delta_7d"] == pytest.approx(10.0)


def test_get_deployment_zone_trend_returns_none_when_no_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    today = _macro_snapshot("2026-05-18", deployment_score=80.0, zone="FULL_DEPLOY")
    history = [
        _macro_snapshot("2026-05-17", deployment_score=78.0, zone="FULL_DEPLOY"),
        _macro_snapshot("2026-05-18", deployment_score=80.0, zone="FULL_DEPLOY"),
    ]
    _patch_macro(monkeypatch, latest=today, history=history)

    result = mcp_server.get_deployment_zone()

    assert result["trend"]["delta_7d"] is None
    assert result["trend"]["prior_score"] is None
    assert result["trend"]["prior_date"] is None


# --------------------------------------------------------------- get_deployment_history


def test_get_deployment_history_clamps_days_and_shapes_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_history(days: int) -> list[dict[str, Any]]:
        captured["days"] = days
        return [_macro_snapshot("2026-05-17", 65.0, "REDUCED")]

    monkeypatch.setattr(mcp_server.macro_repo, "get_history", fake_history)

    result = mcp_server.get_deployment_history(days=10_000)  # over the 730 cap

    assert captured["days"] == 730
    assert result["days"] == 730
    assert result["count"] == 1
    assert result["rows"][0]["zone"] == "REDUCED"
    assert result["rows"][0]["components"]["vix"] == 70.0
    assert result["tier"] == "L1"


def test_get_deployment_history_min_clamp(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, int] = {}

    def fake_history(days: int) -> list[dict[str, Any]]:
        captured["days"] = days
        return []

    monkeypatch.setattr(mcp_server.macro_repo, "get_history", fake_history)

    result = mcp_server.get_deployment_history(days=0)

    assert captured["days"] == 1
    assert result["days"] == 1
    assert result["count"] == 0


# --------------------------------------------------------------- get_scanner_top


def test_get_scanner_top_returns_empty_when_no_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_latest_run() -> dict[str, Any] | None:
        return None

    def fake_scores(run_id: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
        pytest.fail(f"should not be called when no run (run_id={run_id}, limit={limit})")

    monkeypatch.setattr(mcp_server.scanner_repo, "get_latest_run", fake_latest_run)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_scores_for_run", fake_scores)

    result = mcp_server.get_scanner_top()

    assert result == {
        "tier": "L2",
        "kind": "deterministic",
        "run": None,
        "rows": [],
        "factor_order": list(FACTOR_NAMES),
    }


def test_get_scanner_top_skips_score_fetch_on_defensive(monkeypatch: pytest.MonkeyPatch) -> None:
    run = {
        "run_id": str(uuid4()),
        "run_date": "2026-05-18",
        "gate_zone": "DEFENSIVE",
        "gate_score": 30.0,
        "universe_size": 503,
        "scored_count": 0,
        "skip_reason": "gate_defensive",
        "started_at": "2026-05-18T17:35:00",
        "completed_at": "2026-05-18T17:35:01",
    }

    def fake_latest_run() -> dict[str, Any]:
        return run

    def fake_scores(run_id: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
        pytest.fail(f"should not be called when defensive (run_id={run_id}, limit={limit})")

    monkeypatch.setattr(mcp_server.scanner_repo, "get_latest_run", fake_latest_run)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_scores_for_run", fake_scores)

    result = mcp_server.get_scanner_top(limit=50)

    assert result["run"]["skip_reason"] == "gate_defensive"
    assert result["rows"] == []
    assert result["factor_order"] == list(FACTOR_NAMES)


def test_get_scanner_top_shapes_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid4()
    run = {
        "run_id": str(run_id),
        "run_date": "2026-05-18",
        "gate_zone": "FULL_DEPLOY",
        "gate_score": 78.0,
        "universe_size": 503,
        "scored_count": 480,
        "skip_reason": None,
        "started_at": "2026-05-18T17:35:00",
        "completed_at": "2026-05-18T17:38:00",
    }
    score_row: dict[str, Any] = {
        "symbol": "NVDA",
        "rank": 1,
        "composite_pct": 96.2,
        "factor_coverage": 1.0,
        **dict.fromkeys(FACTOR_NAMES, 1.5),
        **{f"{name}_pct": 92.0 for name in FACTOR_NAMES},
    }
    captured: dict[str, Any] = {}

    def fake_latest_run() -> dict[str, Any]:
        return run

    def fake_scores(rid: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
        captured["run_id"] = rid
        captured["limit"] = limit
        return [score_row]

    monkeypatch.setattr(mcp_server.scanner_repo, "get_latest_run", fake_latest_run)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_scores_for_run", fake_scores)

    result = mcp_server.get_scanner_top(limit=10)

    assert captured["run_id"] == run_id  # str -> UUID conversion happened
    assert captured["limit"] == 10
    assert result["rows"][0]["symbol"] == "NVDA"
    assert result["rows"][0]["rank"] == 1
    assert result["rows"][0]["composite_pct"] == 96.2
    assert set(result["rows"][0]["factors"]) == set(FACTOR_NAMES)
    assert set(result["rows"][0]["percentiles"]) == set(FACTOR_NAMES)
    assert result["factor_order"] == list(FACTOR_NAMES)


def test_get_scanner_top_clamps_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid4()
    run = {
        "run_id": str(run_id), "run_date": "2026-05-18", "gate_zone": "FULL_DEPLOY",
        "gate_score": 75.0, "universe_size": 500, "scored_count": 480,
        "skip_reason": None, "started_at": None, "completed_at": None,
    }
    captured: dict[str, Any] = {}

    def fake_latest_run() -> dict[str, Any]:
        return run

    def fake_scores(rid: Any, *, limit: int | None = None) -> list[dict[str, Any]]:
        captured["rid"] = rid
        captured["limit"] = limit
        return []

    monkeypatch.setattr(mcp_server.scanner_repo, "get_latest_run", fake_latest_run)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_scores_for_run", fake_scores)

    mcp_server.get_scanner_top(limit=10_000)
    assert captured["limit"] == 500

    mcp_server.get_scanner_top(limit=0)
    assert captured["limit"] == 1


# --------------------------------------------------------------- get_committee_runs_today


def test_get_committee_runs_today_filters_status_and_window(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    rows = [
        _committee_row(status="complete", completed_at=now.isoformat(), symbol="AAPL"),
        _committee_row(status="approved", completed_at=(now - timedelta(hours=12)).isoformat(), symbol="MSFT"),
        _committee_row(status="failed",   completed_at=now.isoformat(), symbol="XOM"),  # filtered: status
        _committee_row(status="complete", completed_at=(now - timedelta(hours=30)).isoformat(), symbol="OLD"),  # filtered: window
        _committee_row(status="complete", completed_at=None, symbol="NULL"),  # filtered: missing ts
    ]

    def fake_list_recent(household: str | None, *, limit: int) -> list[dict[str, Any]]:
        assert household is None
        return rows[:limit]

    monkeypatch.setattr(mcp_server.committee_store, "list_recent_runs", fake_list_recent)

    result = mcp_server.get_committee_runs_today()

    assert result["tier"] == "L3"
    assert result["kind"] == "non-deterministic"
    assert result["window_hours"] == 24
    symbols = sorted(r["symbol"] for r in result["rows"])
    assert symbols == ["AAPL", "MSFT"]
    assert result["count"] == 2


def test_get_committee_runs_today_handles_naive_timestamps(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    # Naive ISO string (no tz) is treated as UTC by the wrapper.
    naive_ts = now.replace(tzinfo=None).isoformat()
    rows = [_committee_row(status="complete", completed_at=naive_ts)]

    def fake_list_recent(_household: str | None, *, limit: int) -> list[dict[str, Any]]:
        return rows[:limit]

    monkeypatch.setattr(mcp_server.committee_store, "list_recent_runs", fake_list_recent)

    result = mcp_server.get_committee_runs_today()

    assert result["count"] == 1


def test_get_committee_runs_today_skips_malformed_timestamps(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [_committee_row(status="complete", completed_at="not-a-timestamp")]

    def fake_list_recent(_household: str | None, *, limit: int) -> list[dict[str, Any]]:
        return rows[:limit]

    monkeypatch.setattr(mcp_server.committee_store, "list_recent_runs", fake_list_recent)

    result = mcp_server.get_committee_runs_today()

    assert result["count"] == 0
    assert result["rows"] == []


# --------------------------------------------------------------- get_symbol_full_picture


def test_get_symbol_full_picture_rejects_empty_ticker(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_latest() -> dict[str, Any]:
        pytest.fail("should not query when ticker empty")

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)

    result = mcp_server.get_symbol_full_picture(ticker="  ")

    assert result["error"] == "empty_ticker"
    assert result["symbol"] == ""
    assert result["macro"] is None
    assert result["scanner"] is None
    assert result["committee"] is None


def test_get_symbol_full_picture_unifies_three_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    macro = _macro_snapshot("2026-05-18", deployment_score=72.0, zone="FULL_DEPLOY")
    scanner_history = [
        {
            "run_date": "2026-05-18",
            "gate_zone": "FULL_DEPLOY",
            "rank": 5,
            "composite_pct": 88.0,
            "factor_coverage": 0.8,
            **{f"{name}_pct": 85.0 for name in FACTOR_NAMES},
        }
    ]
    committee_payload = {
        "NVDA": {
            "run_id": str(uuid4()),
            "symbol": "NVDA",
            "status": "complete",
            "action": "buy",
            "confidence": 0.82,
            "source": "scanner_fanout",
            "scanner_rank": 5,
            "completed_at": "2026-05-18T18:42:00+00:00",
        }
    }

    captured: dict[str, Any] = {}

    def fake_get_latest() -> dict[str, Any]:
        return macro

    def fake_history(symbol: str, days: int) -> list[dict[str, Any]]:
        captured["symbol"] = symbol
        captured["days"] = days
        return scanner_history

    def fake_committee(symbols: list[str]) -> dict[str, dict[str, Any]]:
        captured["symbols"] = symbols
        return committee_payload

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_history_for_symbol", fake_history)
    monkeypatch.setattr(mcp_server.committee_store, "get_latest_completed_by_symbol", fake_committee)

    result = mcp_server.get_symbol_full_picture(ticker=" nvda ", days=400)

    assert result["symbol"] == "NVDA"
    assert captured["symbol"] == "NVDA"
    assert captured["days"] == 365  # clamped
    assert captured["symbols"] == ["NVDA"]
    assert result["macro"]["zone"] == "FULL_DEPLOY"
    assert result["macro"]["components"]["vix"] == 70.0
    assert result["scanner"]["days"] == 365
    assert result["scanner"]["history"][0]["rank"] == 5
    assert set(result["scanner"]["history"][0]["percentiles"]) == set(FACTOR_NAMES)
    assert result["committee"]["latest"]["action"] == "buy"
    assert result["committee"]["latest"]["scanner_rank"] == 5


def test_get_symbol_full_picture_returns_none_committee_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_latest() -> dict[str, Any] | None:
        return None

    def fake_history(_symbol: str, days: int) -> list[dict[str, Any]]:
        assert days > 0
        return []

    def fake_committee(_symbols: list[str]) -> dict[str, dict[str, Any]]:
        return {}

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)
    monkeypatch.setattr(mcp_server.scanner_repo, "get_history_for_symbol", fake_history)
    monkeypatch.setattr(mcp_server.committee_store, "get_latest_completed_by_symbol", fake_committee)

    result = mcp_server.get_symbol_full_picture(ticker="XOM")

    assert result["committee"]["latest"] is None
    assert result["macro"]["zone"] is None
    assert result["scanner"]["history"] == []


# --------------------------------------------------------------- registration


def test_fastmcp_server_registers_all_five_tools() -> None:
    import asyncio

    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "get_deployment_zone",
        "get_deployment_history",
        "get_scanner_top",
        "get_committee_runs_today",
        "get_symbol_full_picture",
    }


def test_main_entry_invokes_mcp_run(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.mcp_server import __main__ as entry

    called: dict[str, bool] = {"ran": False}

    def fake_run(*_args: Any, **_kwargs: Any) -> None:
        called["ran"] = True

    monkeypatch.setattr(entry.mcp, "run", fake_run)
    entry.main()
    assert called["ran"] is True
