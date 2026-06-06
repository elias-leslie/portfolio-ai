"""Overnight Lean — forward off-hours risk read.

These tests pin the session model (CME Globex hours), the risk-on/off confluence
vote, the oil watch, and the off-hours-only caution fold. The quote source and the
best-effort cache warm are monkeypatched so the logic is deterministic and DB-free.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.macro_gate import conditions, overnight_lean
from app.macro_gate.conditions import CurrentQuoteChange
from app.utils._market_calendar import NY_TZ

# Anchor dates (2026-06-06 is a Saturday per the project clock).
SAT = datetime(2026, 6, 6, 19, 0, tzinfo=NY_TZ)
WED_NIGHT = datetime(2026, 6, 3, 22, 0, tzinfo=NY_TZ)
WED_RTH = datetime(2026, 6, 3, 14, 0, tzinfo=NY_TZ)
WED_HALT = datetime(2026, 6, 3, 17, 30, tzinfo=NY_TZ)
SUN_PRE = datetime(2026, 6, 7, 12, 0, tzinfo=NY_TZ)
SUN_LIVE = datetime(2026, 6, 7, 19, 0, tzinfo=NY_TZ)


def _changes(**by_symbol: float) -> dict[str, CurrentQuoteChange]:
    return {
        symbol.upper(): CurrentQuoteChange(change_pct=pct, as_of=None, cached_at=None)
        for symbol, pct in by_symbol.items()
    }


@pytest.fixture(autouse=True)
def _no_quote_warm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overnight_lean, "_warm_quotes", lambda: None)


def _patch_changes(monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]) -> None:
    monkeypatch.setattr(overnight_lean, "_current_quote_changes", lambda _symbols: changes)


def test_weekend_is_crypto_only_and_futures_read_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": 0.0, "NQ=F": 0.0, "CL=F": 0.0, "GC=F": 0.4, "ZN=F": -0.1, "BTC-USD": -0.5}),
    )
    lean = overnight_lean.get_overnight_lean(now=SAT)

    assert lean.applies is True
    assert lean.session == "weekend"
    assert "Sun 6 PM ET" in lean.session_label
    by_key = {s.key: s for s in lean.signals}
    assert by_key["stocks_sp"].direction == "closed" and by_key["stocks_sp"].live is False
    assert by_key["crypto"].live is True and by_key["crypto"].direction == "risk_off"
    assert "crypto" in lean.headline.lower()
    # A soft weekend crypto dip must not spike equity caution.
    assert lean.stress_score == 15


def test_weeknight_broad_risk_off(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": -1.0, "NQ=F": -1.2, "CL=F": 0.1, "GC=F": 0.8, "ZN=F": 0.5, "BTC-USD": -2.0}),
    )
    lean = overnight_lean.get_overnight_lean(now=WED_NIGHT)

    assert lean.applies is True
    assert lean.session == "overnight"
    assert lean.direction == "risk_off"
    # stocks + gold + rates + crypto all agree.
    assert lean.live_count == 4 and lean.confidence == 4
    assert lean.stress_score is not None and lean.stress_score > 15
    assert "risk-off" in lean.headline


def test_weeknight_risk_on_does_not_raise_caution(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": 0.8, "NQ=F": 1.0, "CL=F": 0.0, "GC=F": -0.5, "ZN=F": -0.3, "BTC-USD": 1.5}),
    )
    lean = overnight_lean.get_overnight_lean(now=WED_NIGHT)

    assert lean.direction == "risk_on"
    assert lean.confidence == 4
    # Risk-on overnight is no reason for caution to climb.
    assert lean.stress_score == 15


def test_oil_spike_flags_watch_and_bumps_caution(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": -0.1, "NQ=F": 0.1, "CL=F": 2.5, "GC=F": 0.0, "ZN=F": 0.0, "BTC-USD": 0.1}),
    )
    lean = overnight_lean.get_overnight_lean(now=WED_NIGHT)

    oil = next(s for s in lean.signals if s.key == "oil")
    assert oil.note is not None and "geopolitical" in oil.note.lower()
    assert "oil" in lean.headline.lower()
    # Quiet equities (floor 15) + oil geopolitical bump (10).
    assert lean.stress_score == 25


def test_rth_does_not_apply_and_yields_no_stress(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": -1.0, "NQ=F": -1.0, "CL=F": 0.0, "GC=F": 0.5, "ZN=F": 0.3, "BTC-USD": -1.0}),
    )
    lean = overnight_lean.get_overnight_lean(now=WED_RTH)

    assert lean.applies is False
    assert lean.stress_score is None


def test_daily_halt_closes_futures(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_changes(
        monkeypatch,
        _changes(**{"ES=F": -1.0, "NQ=F": -1.0, "CL=F": 0.0, "GC=F": 0.5, "ZN=F": 0.3, "BTC-USD": -1.0}),
    )
    lean = overnight_lean.get_overnight_lean(now=WED_HALT)

    assert lean.session == "halt"
    by_key = {s.key: s for s in lean.signals}
    assert by_key["stocks_sp"].live is False
    assert by_key["crypto"].live is True


def test_sunday_reopen_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    quotes = _changes(**{"ES=F": 0.5, "NQ=F": 0.6, "CL=F": 0.0, "GC=F": 0.0, "ZN=F": 0.0, "BTC-USD": 0.2})
    _patch_changes(monkeypatch, quotes)

    pre = overnight_lean.get_overnight_lean(now=SUN_PRE)
    assert pre.session == "weekend"
    assert {s.key: s for s in pre.signals}["stocks_sp"].live is False

    live = overnight_lean.get_overnight_lean(now=SUN_LIVE)
    assert live.session == "overnight"
    assert {s.key: s for s in live.signals}["stocks_sp"].live is True


def _snapshot(**overrides: Any) -> dict[str, Any]:
    base = {
        "snapshot_date": "2026-06-06",
        "computed_at": None,
        "zone": "REDUCED",
        "deployment_score": 43.0,  # -> macro_stress 57
        "raw_json": {"coverage": 1.0},
    }
    return {**base, **overrides}


def _lean(*, applies: bool, stress: int | None) -> overnight_lean.OvernightLean:
    return overnight_lean.OvernightLean(
        applies=applies,
        session="overnight",
        session_label="x",
        direction="risk_off",
        confidence=3,
        live_count=4,
        headline="h",
        stress_score=stress,
        signals=[],
        note=None,
        as_of=None,
    )


def test_payload_fold_raises_caution_off_hours() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(), overnight_lean=_lean(applies=True, stress=72)
    )
    assert payload["overall_caution_score"] == 72
    assert payload["overnight_lean"]["drove_caution"] is True


def test_payload_fold_is_max_only() -> None:
    # Macro floor (57) already above the overnight stress (40): caution unchanged.
    payload = conditions.build_conditions_payload(
        _snapshot(), overnight_lean=_lean(applies=True, stress=40)
    )
    assert payload["overall_caution_score"] == 57
    assert payload["overnight_lean"]["drove_caution"] is False


def test_payload_fold_noops_during_rth() -> None:
    payload = conditions.build_conditions_payload(
        _snapshot(), overnight_lean=_lean(applies=False, stress=90)
    )
    assert payload["overall_caution_score"] == 57
    assert payload["overnight_lean"]["drove_caution"] is False
