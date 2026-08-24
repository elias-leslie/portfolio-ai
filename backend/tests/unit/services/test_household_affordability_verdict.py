"""The free-to-spend figure has to grade itself, once, on the server.

Before this, the threshold that turned a dollar amount into "tight" lived in a
React hook. Task 2.5 puts the same number on a second screen, and two components
each deciding what $140 means is how a household ends up reading two verdicts on
one figure.
"""

from __future__ import annotations

from datetime import date

from app.models.household_finance import HouseholdRecurringCommitment
from app.services._household_dashboard_builders import (
    TIGHT_FREE_TO_SPEND,
    build_affordability,
)

TODAY = date(2026, 8, 24)


def _afford(
    *,
    cash: float,
    commitments: list[HouseholdRecurringCommitment] | None = None,
    essentials_baseline: float = 1200.0,
    spent_to_date: float | None = 1200.0,
    cards: float | None = 0.0,
) -> object:
    return build_affordability(
        cash_reserve=cash,
        recurring_commitments=commitments or [],
        essentials_baseline=essentials_baseline,
        month_to_date_essential_spend=spent_to_date,
        card_balances=cards,
        committed_fund_balances=0.0,
        today=TODAY,
    )


def _remaining_essentials() -> float:
    """What the builder itself says is still to come, so the tests can aim."""
    return _afford(cash=0.0).remaining_essentials


def test_money_left_over_reads_as_an_estimate_never_as_safe() -> None:
    afford = _afford(cash=_remaining_essentials() + 4_000.0)

    assert afford.status == "estimate"
    assert afford.free_to_spend == 4000.0
    assert "safe" not in afford.headline.lower()
    assert "$4,000 free to spend" in afford.headline


def test_a_thin_margin_is_called_tight_rather_than_handed_over() -> None:
    afford = _afford(cash=_remaining_essentials() + TIGHT_FREE_TO_SPEND - 10.0)

    assert afford.status == "tight"
    assert "$140 left" in afford.headline


def test_the_threshold_itself_is_not_tight() -> None:
    afford = _afford(cash=_remaining_essentials() + TIGHT_FREE_TO_SPEND)

    assert afford.status == "estimate"


def test_a_shortfall_reports_the_size_of_the_hole_not_a_floor_of_zero() -> None:
    afford = _afford(cash=_remaining_essentials() - 250.0)

    assert afford.status == "hold"
    assert afford.free_to_spend == -250.0
    assert "$250 short" in afford.headline


def test_exactly_nothing_left_is_a_hold_and_says_so_in_words() -> None:
    afford = _afford(cash=_remaining_essentials())

    assert afford.status == "hold"
    assert afford.free_to_spend == 0.0
    assert afford.headline.startswith("Nothing left")


def test_the_headline_names_the_horizon_the_bills_were_counted_over() -> None:
    """A number that does not name its own frame is the bug this replaces."""
    afford = _afford(
        cash=20_000.0,
        commitments=[
            HouseholdRecurringCommitment(
                merchant="Landlord",
                category="Bills",
                cadence="monthly",
                average_amount=2_000.0,
                annualized_cost=24_000.0,
                last_seen="2026-08-01",
                days_until_due=8,
                commitment_type="bill",
            )
        ],
    )

    # Aug 31 is 7 days out; the fortnight reaches to Sep 7, so the fortnight wins
    # and the September 1 rent is inside the frame.
    assert afford.bills_due_through == "2026-09-07"
    assert afford.bills_due == 2000.0
    assert "Sep 7" in afford.headline
    assert "Sep 7" in afford.detail


def test_the_detail_line_spells_out_the_subtraction() -> None:
    afford = _afford(cash=20_000.0)

    assert "Cash on hand" in afford.detail
    assert "bills due" in afford.detail
    assert "essentials" in afford.detail
    assert "owed on cards" in afford.detail
