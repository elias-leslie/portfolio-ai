"""IPS check unit tests — concentration + sector cap.

Tax-bill and wash-sale checks read DB/TLH state and are covered in
integration tests; here we only assert the decision logic.
"""

from __future__ import annotations

from app.agents.committee.ips import _check_concentration
from app.agents.committee.schemas import TradeProposal


def _proposal(action: str, qty_pct: float) -> TradeProposal:
    return TradeProposal(
        action=action,
        qty_pct=qty_pct,
        entry_price=100.0,
        stop_price=None,
        horizon="3-6mo",
        rationale_md="test",
    )


def test_concentration_buy_within_cap_passes() -> None:
    check = _check_concentration(
        _proposal("buy", 0.10), symbol="NVDA", household_id=None
    )
    assert check.passed is True
    assert check.severity == "info"
    assert check.threshold == 0.25


def test_concentration_buy_over_cap_blocks() -> None:
    check = _check_concentration(
        _proposal("buy", 0.30), symbol="NVDA", household_id=None
    )
    assert check.passed is False
    assert check.severity == "block"


def test_concentration_sell_always_passes() -> None:
    """Sells do not concentrate; severity stays informational."""
    check = _check_concentration(
        _proposal("sell", 0.99), symbol="NVDA", household_id=None
    )
    assert check.passed is True
    assert check.severity == "info"


def test_concentration_hold_passes_regardless() -> None:
    check = _check_concentration(
        _proposal("hold", 0.5), symbol="NVDA", household_id=None
    )
    assert check.passed is True
