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
    assert result["committee"] is None


def test_get_symbol_full_picture_unifies_macro_and_committee(monkeypatch: pytest.MonkeyPatch) -> None:
    macro = _macro_snapshot("2026-05-18", deployment_score=72.0, zone="FULL_DEPLOY")
    committee_payload = {
        "NVDA": {
            "run_id": str(uuid4()),
            "symbol": "NVDA",
            "status": "complete",
            "action": "buy",
            "confidence": 0.82,
            "completed_at": "2026-05-18T18:42:00+00:00",
        }
    }

    captured: dict[str, Any] = {}

    def fake_get_latest() -> dict[str, Any]:
        return macro

    def fake_committee(symbols: list[str]) -> dict[str, dict[str, Any]]:
        captured["symbols"] = symbols
        return committee_payload

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)
    monkeypatch.setattr(mcp_server.committee_store, "get_latest_completed_by_symbol", fake_committee)

    result = mcp_server.get_symbol_full_picture(ticker=" nvda ", days=400)

    assert result["symbol"] == "NVDA"
    assert result["days"] == 365  # clamped for backward compatibility
    assert captured["symbols"] == ["NVDA"]
    assert result["macro"]["zone"] == "FULL_DEPLOY"
    assert result["macro"]["components"]["vix"] == 70.0
    assert result["committee"]["latest"]["action"] == "buy"


def test_get_symbol_full_picture_returns_none_committee_when_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get_latest() -> dict[str, Any] | None:
        return None

    def fake_committee(_symbols: list[str]) -> dict[str, dict[str, Any]]:
        return {}

    monkeypatch.setattr(mcp_server.macro_repo, "get_latest", fake_get_latest)
    monkeypatch.setattr(mcp_server.committee_store, "get_latest_completed_by_symbol", fake_committee)

    result = mcp_server.get_symbol_full_picture(ticker="XOM")

    assert result["committee"]["latest"] is None
    assert result["macro"]["zone"] is None


# --------------------------------------------------------------- registration


def test_fastmcp_server_registers_release_tools() -> None:
    import asyncio

    tools = asyncio.run(mcp_server.mcp.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "get_deployment_zone",
        "get_deployment_history",
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
