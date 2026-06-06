from __future__ import annotations

from datetime import datetime, timedelta
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
    assert payload["macro_stress_score"] == 41
    assert payload["tape_pressure_score"] is None
    assert payload["overall_caution_score"] == 41
    assert payload["overall_read"] == "selective"
    assert payload["primary_driver"] == "macro"
    assert payload["alert"]["active"] is False
    assert payload["summary"] == "Selective — buying conditions are weakening."
    assert payload["coverage"] == 1.0
    assert "highest-conviction setups" in " ".join(payload["what_to_do"])

    evidence_by_key = {item["key"]: item for item in payload["evidence"]}
    assert evidence_by_key["ten_year_two_year"]["value"] == "+49 bps"
    assert evidence_by_key["ten_year_three_month"]["value"] == "+98 bps"
    assert evidence_by_key["hy_oas"]["value"] == "2.70"
    assert evidence_by_key["crowding"]["value"] == "High"
    assert evidence_by_key["crowding"]["detail"] == "|corr| 0.22"
    assert evidence_by_key["overall_caution"]["value"] == "41"
    assert evidence_by_key["overall_caution"]["trend"] is None
    assert payload["trend"]["stress"]["direction"] == "worsening"
    assert payload["trend"]["stress"]["reversal"] is True
    assert payload["market_shifts"][0]["label"] == "Macro stress reversed worse"


def test_conditions_payload_applies_current_tape_stress_overlay() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=65.0),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=42,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-0.8,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-2.9,
            negative_sector_count=2,
            sector_count=11,
        ),
    )

    assert payload["state"] == "Caution"
    assert payload["stress_score"] == 42
    assert payload["macro_stress_score"] == 35
    assert payload["tape_pressure_score"] == 42
    assert payload["overall_caution_score"] == 42
    assert payload["overall_read"] == "selective"
    assert payload["primary_driver"] == "tape"
    assert payload["deployment_score"] == 65.0
    assert payload["flags"] == []
    assert payload["summary"] == "Selective — tape pressure is elevated, but macro stress is not severe."
    assert "Do not chase the selloff" in payload["action_text"]
    assert "Tape pressure is the main caution" in payload["what_matters"][0]
    assert "Do not chase the selloff" in payload["what_to_do"][0]

    evidence_by_key = {item["key"]: item for item in payload["evidence"]}
    assert evidence_by_key["overall_caution"]["value"] == "42"
    assert evidence_by_key["equity_tape"]["value"] == "42"
    assert evidence_by_key["equity_tape"]["detail"] == (
        "S&P -0.8%, Technology -2.9%, 2/11 sectors down"
    )


def test_conditions_payload_uses_stronger_copy_for_moderate_tape_stress() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=65.0),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=54,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-1.0,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-3.3,
            negative_sector_count=6,
            sector_count=11,
        ),
    )

    assert payload["stress_score"] == 54
    assert payload["overall_read"] == "selective"
    assert payload["primary_driver"] == "tape"
    assert payload["summary"] == "Selective — tape pressure is elevated, but macro stress is not severe."
    assert "Stay invested, but be selective" in payload["action_text"]

    evidence_by_key = {item["key"]: item for item in payload["evidence"]}
    assert evidence_by_key["overall_caution"]["detail"] == "Selective"


def test_conditions_payload_keeps_sixty_tape_stress_as_caution() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=82.0, zone="FULL_DEPLOY"),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=62,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-1.2,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-4.1,
            negative_sector_count=6,
            sector_count=11,
        ),
    )

    assert payload["state"] == "Calm"
    assert payload["stress_score"] == 62
    assert payload["macro_stress_score"] == 18
    assert payload["tape_pressure_score"] == 62
    assert payload["overall_read"] == "selective"
    assert payload["primary_driver"] == "tape"
    assert payload["flags"] == []
    assert payload["alert"]["active"] is False
    assert payload["summary"] == "Selective — tape pressure is elevated, but macro stress is not severe."

    evidence_by_key = {item["key"]: item for item in payload["evidence"]}
    assert evidence_by_key["overall_caution"]["tone"] == "warning"


def test_conditions_payload_escalates_on_severe_current_tape_stress() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=65.0),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=66,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-2.7,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-5.4,
            negative_sector_count=8,
            sector_count=11,
        ),
    )

    assert payload["state"] == "Elevated"
    assert payload["stress_score"] == 66
    assert payload["overall_read"] == "defensive"
    assert payload["primary_driver"] == "tape"
    assert payload["flags"] == ["equity_tape_stress"]
    assert payload["alert"]["active"] is True
    assert payload["alert"]["priority"] == "high"


def test_conditions_payload_marks_both_driver_when_macro_and_tape_are_high() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(zone="DEFENSIVE", deployment_score=30.0),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=68,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-2.9,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-5.8,
            negative_sector_count=8,
            sector_count=11,
        ),
    )

    assert payload["macro_stress_score"] == 70
    assert payload["tape_pressure_score"] == 68
    assert payload["overall_caution_score"] == 70
    assert payload["overall_read"] == "defensive"
    assert payload["primary_driver"] == "both"


def test_get_tape_stress_requires_fresh_sp500_and_broad_sector_coverage(monkeypatch) -> None:
    now = datetime(2026, 6, 5, 10, 30, tzinfo=conditions.NY_TZ)
    fresh = now - timedelta(minutes=5)
    stale = now - timedelta(minutes=30)
    sector_symbols = list(conditions.SECTOR_ETFS.keys())

    def quote(change_pct: float, cached_at: datetime) -> conditions.CurrentQuoteChange:
        return conditions.CurrentQuoteChange(
            change_pct=change_pct,
            as_of=cached_at.isoformat(),
            cached_at=cached_at,
        )

    monkeypatch.setattr(
        conditions,
        "_current_quote_changes",
        lambda _symbols: {
            conditions.INDEX_SP500: quote(-1.0, stale),
            **{symbol: quote(-0.4, fresh) for symbol in sector_symbols},
        },
    )
    assert conditions.get_tape_stress(now=now) is None

    monkeypatch.setattr(
        conditions,
        "_current_quote_changes",
        lambda _symbols: {
            conditions.INDEX_SP500: quote(-1.0, fresh),
            **{symbol: quote(-0.4, fresh) for symbol in sector_symbols[:8]},
        },
    )
    assert conditions.get_tape_stress(now=now) is None


def test_conditions_payload_escalates_only_on_severe_volatility() -> None:
    payload = conditions.build_conditions_payload(_snapshot(vix_close=30.1))

    assert payload["state"] == "Elevated"
    assert payload["flags"] == ["vix_stress"]
    assert payload["overall_read"] == "defensive"
    assert payload["alert"] == {
        "active": True,
        "priority": "high",
        "reason": "Severe overall-caution threshold crossed.",
    }


def test_conditions_payload_marks_critical_when_stress_score_is_very_high() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(zone="DEFENSIVE", deployment_score=24.0),
    )

    assert payload["state"] == "Elevated"
    assert payload["stress_score"] == 76
    assert payload["overall_read"] == "defensive"
    assert payload["primary_driver"] == "macro"
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
    assert payload["overall_caution_score"] is None
    assert payload["overall_read"] == "unavailable"
    assert payload["primary_driver"] == "data_limited"
    assert payload["alert"]["active"] is False
    assert payload["evidence"][0]["value"] == "-"


def test_conditions_payload_marks_tape_live_during_open_session() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=65.0),
        tape_stress=conditions.TapeStressEvidence(
            stress_score=42,
            as_of="2026-06-04T14:20:00+00:00",
            sp500_change_pct=-0.8,
            weakest_sector_symbol="XLK",
            weakest_sector_name="Technology",
            weakest_sector_change_pct=-2.9,
            negative_sector_count=2,
            sector_count=11,
        ),
        market_session="open",
    )

    assert payload["tape_available"] is True
    assert payload["market_session"] == "open"
    assert payload["tape_status"] is None
    assert payload["tape_pressure_score"] == 42


def test_conditions_payload_off_hours_is_macro_only_with_tape_unavailable() -> None:
    # Off the regular session there is no live tape: the read falls back to a
    # macro-only number, honestly labelled, instead of a stale carried-forward
    # close presented as if it were current.
    payload = conditions.build_conditions_payload(
        _snapshot(deployment_score=57.0),
        tape_stress=None,
        market_session="closed",
    )

    assert payload["tape_available"] is False
    assert payload["market_session"] == "closed"
    assert payload["tape_pressure_score"] is None
    assert payload["overall_caution_score"] == payload["macro_stress_score"]
    assert payload["primary_driver"] == "macro"
    assert payload["tape_status"] == (
        "Markets closed — macro-only read; tape resumes at next open."
    )


def test_tape_status_distinguishes_closed_from_thin_coverage() -> None:
    assert conditions._tape_status("open", tape_available=True) is None
    assert "coverage too thin" in conditions._tape_status("open", tape_available=False)
    for session in ("closed", "pre_market", "after_hours"):
        assert "Markets closed" in conditions._tape_status(session, tape_available=False)


def test_driving_read_states_the_why_across_regimes() -> None:
    tape = conditions.TapeStressEvidence(
        stress_score=74,
        as_of="2026-06-05T20:00:00+00:00",
        sp500_change_pct=-2.6,
        weakest_sector_symbol="XLK",
        weakest_sector_name="Technology",
        weakest_sector_change_pct=-7.4,
        negative_sector_count=6,
        sector_count=11,
    )

    risk_off = conditions._driving_read(
        overall_read="defensive",
        primary_driver="tape",
        tape_stress=tape,
        vix_close=21.5,
        hy_change_bps=-39.0,
        breadth_pct=58.0,
    )
    assert risk_off["tone"] == "risk_off"
    assert risk_off["headline"].startswith("Risk-off —")
    assert "Technology -7.4%" in risk_off["headline"]
    assert "6/11 sectors down" in risk_off["headline"]
    assert "VIX 21.5" in risk_off["headline"]

    # Selective tape with calm volatility: no volatility cue, softer posture.
    cautious = conditions._driving_read(
        overall_read="selective",
        primary_driver="tape",
        tape_stress=tape,
        vix_close=17.0,
        hy_change_bps=None,
        breadth_pct=58.0,
    )
    assert cautious["tone"] == "caution"
    assert cautious["headline"].startswith("Cautious —")
    assert "VIX" not in cautious["headline"]

    # Widening credit surfaces as its own cue even without elevated volatility.
    credit = conditions._driving_read(
        overall_read="defensive",
        primary_driver="macro",
        tape_stress=None,
        vix_close=18.0,
        hy_change_bps=60.0,
        breadth_pct=40.0,
    )
    assert "credit spreads widening" in credit["headline"]

    steady = conditions._driving_read(
        overall_read="normal",
        primary_driver="none",
        tape_stress=None,
        vix_close=13.0,
        hy_change_bps=None,
        breadth_pct=64.0,
    )
    assert steady["tone"] == "constructive"
    assert steady["headline"].startswith("Broad and steady")
    assert "VIX 13.0" in steady["headline"]

    blank = conditions._driving_read(
        overall_read="unavailable",
        primary_driver="data_limited",
        tape_stress=None,
        vix_close=None,
        hy_change_bps=None,
        breadth_pct=None,
    )
    assert blank["tone"] == "neutral"
