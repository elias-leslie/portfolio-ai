"""Four chosen funds, each priced from its own trailing spend (D18)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services._household_dashboard_builders import build_sinking_funds

TODAY = date(2026, 8, 24)


def _row(
    *,
    month: str,
    amount: float,
    category: str,
    merchant: str = "Somebody",
    row_id: str = "row",
) -> dict[str, Any]:
    year, month_number = (int(part) for part in month.split("-"))
    return {
        "id": row_id,
        "date": date(year, month_number, 15),
        "amount": amount,
        "signed_amount": amount,
        "category": category,
        "merchant": merchant,
        "description": merchant,
    }


def _spread(category: str, amount: float, merchant: str = "Somebody") -> list[dict]:
    """One row a month across the twelve complete months before August 2026."""
    months = [f"2025-{m:02d}" for m in range(9, 13)] + [
        f"2026-{m:02d}" for m in range(1, 9)
    ]
    return [
        _row(
            month=month,
            amount=amount,
            category=category,
            merchant=merchant,
            row_id=f"{category}-{month}",
        )
        for month in months
        if month < "2026-08"
    ]


def _funds(rows: list[dict], **kwargs: Any) -> dict[str, Any]:
    built = build_sinking_funds(spend_rows=rows, today=TODAY, **kwargs)
    return {fund.key: fund for fund in built}


def test_all_four_chosen_funds_are_always_present() -> None:
    """The household picked these four; a quiet month does not remove one."""
    funds = _funds([])

    assert list(funds) == [
        "travel",
        "home_repair",
        "insurance_taxes_registration",
        "gifts_holidays",
    ]


def test_a_fund_divides_by_the_months_the_ledger_covered() -> None:
    funds = _funds(_spread("Travel", 400.0))

    assert funds["travel"].status == "derived"
    assert funds["travel"].window_months == 11
    assert funds["travel"].monthly_target == 400.0
    assert "-> $400/mo" in funds["travel"].derivation


def test_the_running_month_is_never_priced() -> None:
    """August is a third finished; counting it quotes a third of a rate."""
    rows = [*_spread("Travel", 400.0), _row(month="2026-08", amount=9999.0, category="Travel")]
    funds = _funds(rows)

    assert funds["travel"].monthly_target == 400.0
    assert funds["travel"].window_total == 4400.0


def test_the_largest_purchase_can_be_set_aside_as_one_time() -> None:
    rows = [
        *_spread("Travel", 400.0),
        _row(
            month="2026-01",
            amount=3606.0,
            category="Travel",
            merchant="Check Paid",
            row_id="cruise",
        ),
    ]

    kept = _funds(rows)["travel"]
    dropped = _funds(rows, overrides={"travel": {"drop_largest": True}})["travel"]

    assert kept.monthly_target == 727.82
    assert dropped.monthly_target == 400.0
    assert dropped.monthly_target_including_largest == 727.82
    assert dropped.largest is not None
    assert dropped.largest.merchant == "Check Paid"
    assert "set aside as one-time" in dropped.derivation


def test_a_tax_row_belongs_to_taxes_even_though_it_is_filed_under_home() -> None:
    """The property tax posts as Home. It is a tax, not a repair (D23)."""
    rows = [
        *_spread("Home", 100.0, merchant="Wayfair"),
        _row(
            month="2025-11",
            amount=2144.48,
            category="Home",
            merchant="Pinellas County Tax Collector",
            row_id="tax",
        ),
    ]
    funds = _funds(rows)

    assert funds["insurance_taxes_registration"].window_total == 2144.48
    assert funds["home_repair"].window_total == 1100.0


def test_one_purchase_can_only_fund_one_buffer() -> None:
    rows = [
        _row(
            month="2025-11",
            amount=2144.48,
            category="Home",
            merchant="Pinellas County Tax Collector",
            row_id="tax",
        )
    ]
    funds = _funds(rows)
    counted = [fund.key for fund in funds.values() if fund.window_total > 0]

    assert counted == ["insurance_taxes_registration"]


def test_a_fund_with_no_history_asks_rather_than_reporting_zero() -> None:
    funds = _funds(_spread("Travel", 400.0))

    assert funds["gifts_holidays"].status == "no_history"
    assert funds["gifts_holidays"].monthly_target is None
    assert "has to be declared" in funds["gifts_holidays"].note


def test_a_declared_amount_wins_and_keeps_the_derivation_visible() -> None:
    funds = _funds(
        _spread("Travel", 400.0),
        overrides={
            "travel": {
                "monthly_override": 250.0,
                "override_set_on": "2026-08-01",
                "override_note": "Only one trip planned",
            }
        },
    )

    assert funds["travel"].status == "declared"
    assert funds["travel"].monthly_target == 250.0
    assert "Trailing spend says $400/mo" in funds["travel"].derivation
    assert funds["travel"].override_set_on == "2026-08-01"


def test_refunds_never_raise_a_fund() -> None:
    """A credit is not a contribution; it just is not spend."""
    rows = [
        *_spread("Travel", 400.0),
        {
            **_row(month="2026-02", amount=-500.0, category="Travel", row_id="refund"),
            "signed_amount": -500.0,
        },
    ]
    funds = _funds(rows)

    assert funds["travel"].window_total == 4400.0
