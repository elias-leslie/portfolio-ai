from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.macro_routes import router as macro_router
from app.macro_gate import conditions


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(macro_router)
    return TestClient(app)


def _snapshot() -> dict[str, Any]:
    return {
        "snapshot_date": "2026-05-28",
        "computed_at": "2026-05-28T21:45:00",
        "zone": "REDUCED",
        "deployment_score": 59.0,
        "vix_close": 17.0,
        "breadth_pct": 59.0,
        "hy_spread": 2.7,
        "crowding_score": 32.0,
        "raw_json": {"coverage": 1.0},
    }


def test_macro_conditions_route_returns_today_briefing_contract() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(),
        yield_curve=conditions.YieldCurveEvidence(
            as_of="2026-05-28",
            ten_year_two_year_bps=49.0,
            ten_year_three_month_bps=98.0,
        ),
    )

    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=_snapshot()),
        patch("app.api.macro_routes.run_macro_gate", return_value=None) as run_macro_gate,
        patch(
            "app.api.macro_routes.macro_conditions.get_conditions_payload",
            return_value=payload,
        ),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 200, resp.text
    run_macro_gate.assert_not_called()
    body = resp.json()
    assert body["state"] == "Caution"
    assert body["stress_score"] == 41
    assert body["alert"]["active"] is False
    assert body["bond_signals"]["ten_year_three_month_bps"] == 98.0
    assert body["evidence"][0]["label"] == "Stress"
    assert body["trend"]["stress"]["direction"] == "unavailable"
    assert body["market_shifts"][0]["label"] == "No major shifts"


def test_macro_conditions_route_returns_503_when_inputs_are_unavailable() -> None:
    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=None),
        patch("app.api.macro_routes.run_macro_gate", return_value=None),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "macro_gate_inputs_unavailable"
