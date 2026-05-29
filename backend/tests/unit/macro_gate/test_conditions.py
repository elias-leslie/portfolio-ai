from __future__ import annotations

from datetime import datetime
from typing import Any

from app.macro_gate import conditions


def _snapshot(**overrides: Any) -> dict[str, Any]:
    base = {
        "snapshot_date": "2026-05-28",
        "computed_at": datetime(2026, 5, 28, 21, 45),
        "zone": "REDUCED",
        "deployment_score": 59.0,
        "vix_close": 17.0,
        "term_spread_bps": 49.0,
        "breadth_pct": 59.0,
        "hy_spread": 2.7,
        "put_call_ratio": 0.86,
        "factor_crowding_corr": 0.22,
        "crowding_score": 32.0,
        "raw_json": {"coverage": 1.0},
    }
    return {**base, **overrides}


def _history() -> list[dict[str, Any]]:
    return [
        _snapshot(
            snapshot_date="2026-05-14",
            deployment_score=56.0,
            vix_close=18.0,
            breadth_pct=66.0,
            hy_spread=2.9,
            term_spread_bps=62.0,
            crowding_score=48.0,
        ),
        _snapshot(
            snapshot_date="2026-05-21",
            deployment_score=66.0,
            vix_close=15.0,
            breadth_pct=64.0,
            hy_spread=2.5,
            term_spread_bps=58.0,
            crowding_score=42.0,
        ),
        _snapshot(),
    ]


def test_conditions_payload_turns_reduced_gate_into_plain_language_caution() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(),
        yield_curve=conditions.YieldCurveEvidence(
            as_of="2026-05-28",
            ten_year_two_year_bps=49.0,
            ten_year_three_month_bps=98.0,
        ),
        hy_change=conditions.HyOasChange(
            latest_date="2026-05-28",
            latest_value=2.7,
            prior_date="2026-02-28",
            prior_value=3.1,
            change_bps=-40.0,
        ),
        macro_history=_history(),
        yield_curve_history=[
            conditions.YieldCurveHistoryPoint(
                as_of="2026-05-14",
                ten_year_two_year_bps=62.0,
                ten_year_three_month_bps=120.0,
            ),
            conditions.YieldCurveHistoryPoint(
                as_of="2026-05-21",
                ten_year_two_year_bps=58.0,
                ten_year_three_month_bps=112.0,
            ),
            conditions.YieldCurveHistoryPoint(
                as_of="2026-05-28",
                ten_year_two_year_bps=49.0,
                ten_year_three_month_bps=98.0,
            ),
        ],
    )

    assert payload["state"] == "Caution"
    assert payload["stress_score"] == 41
    assert payload["alert"]["active"] is False
    assert payload["summary"] == "Market stress is low-to-moderate."
    assert payload["coverage"] == 1.0
    assert "highest-conviction setups" in " ".join(payload["what_to_do"])

    evidence_by_key = {item["key"]: item for item in payload["evidence"]}
    assert evidence_by_key["ten_year_two_year"]["value"] == "+49 bps"
    assert evidence_by_key["ten_year_three_month"]["value"] == "+98 bps"
    assert evidence_by_key["hy_oas"]["value"] == "2.70"
    assert evidence_by_key["crowding"]["value"] == "High"
    assert evidence_by_key["crowding"]["detail"] == "Corr +0.22"
    assert evidence_by_key["stress"]["trend"]["change_label"] == "7D +7"
    assert payload["trend"]["stress"]["direction"] == "worsening"
    assert payload["trend"]["stress"]["reversal"] is True
    assert payload["market_shifts"][0]["label"] == "Stress reversed worse"


def test_conditions_payload_escalates_only_on_severe_volatility() -> None:
    payload = conditions.build_conditions_payload(_snapshot(vix_close=30.1))

    assert payload["state"] == "Elevated"
    assert payload["flags"] == ["vix_stress"]
    assert payload["alert"] == {
        "active": True,
        "priority": "high",
        "reason": "Severe market-stress threshold crossed.",
    }


def test_conditions_payload_marks_critical_when_stress_score_is_very_high() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(zone="DEFENSIVE", deployment_score=24.0),
    )

    assert payload["state"] == "Elevated"
    assert payload["stress_score"] == 76
    assert payload["flags"] == ["defensive_deployment"]
    assert payload["alert"]["priority"] == "critical"


def test_conditions_payload_uses_hy_widening_as_credit_stress() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(),
        hy_change=conditions.HyOasChange(
            latest_date="2026-05-28",
            latest_value=4.1,
            prior_date="2026-02-28",
            prior_value=2.9,
            change_bps=120.0,
        ),
    )

    assert payload["state"] == "Elevated"
    assert payload["flags"] == ["credit_widening"]
    assert payload["credit_signal"]["change_bps"] == 120.0


def test_conditions_payload_handles_missing_values_without_alerting() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(
            zone="FULL_DEPLOY",
            deployment_score=None,
            vix_close=None,
            hy_spread=None,
            breadth_pct=None,
            crowding_score=None,
            raw_json={},
        ),
    )

    assert payload["state"] == "Calm"
    assert payload["stress_score"] is None
    assert payload["alert"]["active"] is False
    assert payload["evidence"][0]["value"] == "-"
