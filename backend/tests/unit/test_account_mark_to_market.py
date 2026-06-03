"""Unit tests for mark-to-market account re-valuation.

Covers the scenarios validated against real account data: live price drift,
unpriceable/partial holdings, pure-cash accounts, missing broker total, and
the pending-settlement safety property (anchor on broker total, never recompute
cash from holdings).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.portfolio.account_valuation import mark_to_market_account_value
from app.portfolio.models import PriceData


def _price(symbol: str, price: float, *, error: str | None = None) -> PriceData:
    return PriceData(
        symbol=symbol,
        price=price,
        cached_at=datetime(2026, 6, 3, 22, 30, tzinfo=UTC),
        source="yfinance",
        error=error,
    )


def test_all_positions_priced_applies_drift_and_keeps_cash() -> None:
    # Traditional IRA shape: broker total 388,708.68 = VTI 994.409 @ 374.36 + 16,441.73 cash.
    # VTI drops to 370.46 -> account should fall by 994.409 * (374.36 - 370.46), cash untouched.
    result = mark_to_market_account_value(
        Decimal("388708.68"),
        [(Decimal("994.409"), Decimal("374.36"), "VTI")],
        {"VTI": _price("VTI", 370.46)},
    )
    expected = 388708.68 + (370.46 - 374.36) * 994.409
    assert result.valuation_source == "live"
    assert result.total_value is not None
    assert abs(result.total_value - expected) < 1e-6
    assert result.priced_position_count == 1
    assert result.quote_as_of is not None


def test_pure_cash_account_returns_broker_total_not_zero() -> None:
    # No positions (cash management account): must show the broker total, never $0.
    result = mark_to_market_account_value(Decimal("38434.48"), [], {})
    assert result.valuation_source == "broker"
    assert result.total_value == 38434.48
    assert result.priced_position_count == 0


def test_unpriceable_position_keeps_broker_value() -> None:
    # A holding with no live quote contributes zero drift -> stays at broker valuation,
    # and the account is reported as broker-sourced (no live delta applied).
    result = mark_to_market_account_value(
        Decimal("9447.26"),
        [(Decimal("25.16"), Decimal("374.36"), "VTI")],
        {"VTI": _price("VTI", 0.0, error="quote unavailable")},
    )
    assert result.valuation_source == "broker"
    assert result.total_value == 9447.26


def test_partial_pricing_applies_only_priced_drift() -> None:
    # One priced holding, one unpriceable: only the priced one moves the total.
    result = mark_to_market_account_value(
        Decimal("567182.23"),
        [
            (Decimal("1488"), Decimal("374.36"), "VTI"),
            (Decimal("80"), Decimal("125.77"), "VGT"),
        ],
        {"VTI": _price("VTI", 370.46)},  # VGT has no quote
    )
    expected = 567182.23 + (370.46 - 374.36) * 1488
    assert result.valuation_source == "live"
    assert result.total_value is not None
    assert abs(result.total_value - expected) < 1e-6
    assert result.priced_position_count == 1


def test_missing_broker_total_is_unknown() -> None:
    result = mark_to_market_account_value(None, [(Decimal("10"), Decimal("100"), "VTI")], {"VTI": _price("VTI", 110.0)})
    assert result.valuation_source == "unknown"
    assert result.total_value is None


def test_position_without_broker_price_contributes_nothing() -> None:
    # Pending/unsettled holding with no broker snapshot price: do NOT recompute from
    # holdings (would double-count cash); anchor stays at the broker total.
    result = mark_to_market_account_value(
        Decimal("49541.96"),
        [(Decimal("401.702"), None, "VGT")],
        {"VGT": _price("VGT", 122.60)},
    )
    assert result.valuation_source == "broker"
    assert result.total_value == 49541.96
