from __future__ import annotations

from typing import Any

from app.macro_gate import conditions_history


def _payload(**overrides: Any) -> dict[str, Any]:
    base = {
        "snapshot_date": "2026-06-06",
        "deployment_score": 57.0,
        "macro_stress_score": 43,
        "tape_pressure_score": None,
        "overall_caution_score": 43,
        "overall_read": "selective",
        "primary_driver": "macro",
        "state": "Caution",
        "tape_available": False,
        "market_session": "closed",
    }
    return {**base, **overrides}


def test_headline_from_payload_maps_response_keys() -> None:
    row = conditions_history._headline_from_payload(_payload())
    assert row["macro_stress"] == 43
    assert row["overall_caution"] == 43
    assert row["tape_pressure"] is None
    assert row["tape_available"] is False
    assert row["market_session"] == "closed"


def test_changed_inserts_first_row_and_on_value_move() -> None:
    current = conditions_history._headline_from_payload(_payload())
    # No prior row -> always log the first observation.
    assert conditions_history._changed(None, current) is True

    same = conditions_history._headline_from_payload(_payload())
    assert conditions_history._changed(current, same) is False

    # A headline move logs a new step-change point.
    moved = conditions_history._headline_from_payload(
        _payload(overall_caution_score=51, macro_stress_score=51),
    )
    assert conditions_history._changed(current, moved) is True


def test_changed_logs_when_tape_availability_or_day_flips() -> None:
    macro_only = conditions_history._headline_from_payload(_payload())
    # Same number, but tape became live -> the point's meaning changed, log it.
    now_live = conditions_history._headline_from_payload(
        _payload(tape_available=True, market_session="open"),
    )
    assert conditions_history._changed(macro_only, now_live) is True

    # New trading day with identical numbers still logs a fresh daily point.
    next_day = conditions_history._headline_from_payload(
        _payload(snapshot_date="2026-06-08"),
    )
    assert conditions_history._changed(macro_only, next_day) is True
