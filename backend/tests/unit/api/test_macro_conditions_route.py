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
    assert body["macro_stress_score"] == 41
    assert body["overall_caution_score"] == 41
    assert body["overall_read"] == "selective"
    assert body["primary_driver"] == "macro"
    assert body["alert"]["active"] is False
    assert body["bond_signals"]["ten_year_three_month_bps"] == 98.0
    assert body["evidence"][0]["label"] == "Overall Caution"
    assert body["trend"]["stress"]["direction"] == "unavailable"
    assert body["market_shifts"][0]["label"] == "No major shifts"


def _next_event() -> dict[str, Any]:
    return {
        "event_type": "cpi_release",
        "event_date": "2026-06-10",
        "event_time": "08:30:00",
        "title": "Consumer Price Index",
        "impact_score": 5,
    }


def _payload() -> dict[str, Any]:
    return conditions.build_conditions_payload(
        _snapshot(),
        yield_curve=conditions.YieldCurveEvidence(
            as_of="2026-05-28",
            ten_year_two_year_bps=49.0,
            ten_year_three_month_bps=98.0,
        ),
    )


def test_macro_conditions_route_surfaces_next_catalyst() -> None:
    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=_snapshot()),
        patch("app.api.macro_routes.run_macro_gate", return_value=None),
        patch(
            "app.api.macro_routes.macro_conditions.get_conditions_payload",
            return_value=_payload(),
        ),
        patch(
            "app.api.macro_routes.get_macro_calendar_cluster",
            return_value={"next_high_impact_event": _next_event()},
        ),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 200, resp.text
    catalyst = resp.json()["next_catalyst"]
    assert catalyst["event_type"] == "cpi_release"
    assert catalyst["event_date"] == "2026-06-10"
    assert catalyst["title"] == "Consumer Price Index"
    assert catalyst["impact_score"] == 5


def test_macro_conditions_route_next_catalyst_null_when_none_upcoming() -> None:
    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=_snapshot()),
        patch("app.api.macro_routes.run_macro_gate", return_value=None),
        patch(
            "app.api.macro_routes.macro_conditions.get_conditions_payload",
            return_value=_payload(),
        ),
        patch(
            "app.api.macro_routes.get_macro_calendar_cluster",
            return_value={"next_high_impact_event": None},
        ),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 200, resp.text
    assert resp.json()["next_catalyst"] is None


def test_macro_conditions_route_next_catalyst_survives_calendar_error() -> None:
    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=_snapshot()),
        patch("app.api.macro_routes.run_macro_gate", return_value=None),
        patch(
            "app.api.macro_routes.macro_conditions.get_conditions_payload",
            return_value=_payload(),
        ),
        patch(
            "app.api.macro_routes.get_macro_calendar_cluster",
            side_effect=RuntimeError("calendar table unavailable"),
        ),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 200, resp.text
    assert resp.json()["next_catalyst"] is None


def test_macro_conditions_route_returns_503_when_inputs_are_unavailable() -> None:
    with (
        patch("app.api.macro_routes.repository.get_latest", return_value=None),
        patch("app.api.macro_routes.run_macro_gate", return_value=None),
    ):
        client = _build_client()
        resp = client.get("/api/macro/conditions")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "macro_gate_inputs_unavailable"
