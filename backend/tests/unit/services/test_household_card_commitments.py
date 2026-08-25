"""What the cards commit the plan to, in the place the plan is read (P0-20)."""

from __future__ import annotations

from datetime import date

from app.models.credit_cards import CreditCardProduct, HouseholdCreditCard
from app.services._household_card_commitments import build_card_commitments

TODAY = date(2026, 8, 25)


def _product(
    name: str,
    *,
    annual_fee: float = 0.0,
    welcome_min_spend: float | None = None,
) -> CreditCardProduct:
    return CreditCardProduct(
        id=f"product-{name}",
        slug=name.lower().replace(" ", "-"),
        issuer="Chase",
        product_name=name,
        annual_fee=annual_fee,
        welcome_min_spend=welcome_min_spend,
    )


def _card(
    card_id: str,
    product: CreditCardProduct,
    *,
    status: str = "active",
    account_id: str | None = None,
    mask: str | None = None,
    owner: str | None = None,
    fee_due: str | None = None,
    welcome_deadline: str | None = None,
    welcome_status: str = "not_started",
    welcome_progress: float = 0.0,
) -> HouseholdCreditCard:
    return HouseholdCreditCard(
        id=card_id,
        product_id=product.id,
        household_account_id=account_id,
        status=status,
        annual_fee_due_date=fee_due,
        welcome_deadline=welcome_deadline,
        welcome_status=welcome_status,
        welcome_progress_amount=welcome_progress,
        product=product,
        account_mask=mask,
        account_owner=owner,
    )


SAPPHIRE = _product("Chase Sapphire Preferred", annual_fee=95.0, welcome_min_spend=5000.0)
AMAZON = _product("Amazon Prime Visa")


def test_a_card_with_no_feed_is_named_rather_than_counted_as_paid_off() -> None:
    """A card nothing reports on is the one whose balance is most likely a surprise."""
    plan = build_card_commitments(
        cards=[
            _card("a", SAPPHIRE, account_id="acct-1", mask="3627", owner="Elias B Leslie"),
            _card("b", SAPPHIRE, account_id="acct-2", mask="8054", owner="Mariana Leslie"),
        ],
        account_values={"acct-1": -5926.5},
        today=TODAY,
    )

    owed = {row.account_mask: row.balance_owed for row in plan.cards}
    assert owed == {"3627": 5926.5, "8054": None}
    assert plan.balance_total == 5926.5
    assert plan.balance_unknown_labels == ["Chase Sapphire Preferred (Mariana ·8054)"]
    assert "Mariana ·8054" in plan.detail


def test_annual_fees_become_a_monthly_accrual_the_plan_can_use() -> None:
    """$190 charged once a year is $16 a month of income already spoken for."""
    plan = build_card_commitments(
        cards=[
            _card("a", SAPPHIRE, fee_due="2027-08-02"),
            _card("b", SAPPHIRE, fee_due="2027-08-02"),
            _card("c", AMAZON),
        ],
        today=TODAY,
    )

    assert plan.annual_fee_yearly == 190.0
    assert plan.annual_fee_monthly == 15.83
    assert plan.next_fee_detail == (
        "2 fees totalling $190 land together on Aug 02, 2027, 342 days away."
    )
    assert "$16/mo of income already spoken for" in plan.detail


def test_a_single_next_fee_names_the_card_it_lands_on() -> None:
    plan = build_card_commitments(
        cards=[
            _card("a", SAPPHIRE, mask="3627", owner="Elias B Leslie", fee_due="2026-09-10"),
            _card("b", SAPPHIRE, mask="8054", owner="Mariana Leslie", fee_due="2027-08-02"),
        ],
        today=TODAY,
    )

    assert plan.next_fee_detail == (
        "Next up: $95 on Chase Sapphire Preferred (Elias ·3627) on Sep 10, 2026, 16 days away."
    )


def test_a_fee_with_no_recorded_date_says_nothing_can_warn_about_it() -> None:
    plan = build_card_commitments(cards=[_card("a", SAPPHIRE)], today=TODAY)

    assert plan.cards[0].annual_fee_due_date is None
    assert "no recorded renewal date" in plan.cards[0].annual_fee_detail
    assert "no renewal date is recorded" in plan.next_fee_detail


def test_an_open_bonus_states_the_daily_pace_that_still_wins_it() -> None:
    plan = build_card_commitments(
        cards=[
            _card(
                "a",
                SAPPHIRE,
                welcome_deadline="2026-10-24",
                welcome_status="in_progress",
                welcome_progress=2000.0,
            )
        ],
        today=TODAY,
    )
    card = plan.cards[0]

    assert plan.welcome_open_count == 1
    assert card.welcome_days_left == 60
    # $3,000 left over 60 days.
    assert card.welcome_detail == (
        "$3,000 to go by Oct 24, 2026 -- 60 days left, about $50/day. "
        "Route household spend here."
    )
    assert plan.welcome_detail == card.welcome_detail


def test_a_missed_deadline_is_reported_as_missed_not_as_progress() -> None:
    plan = build_card_commitments(
        cards=[
            _card(
                "a",
                SAPPHIRE,
                welcome_deadline="2026-07-01",
                welcome_status="in_progress",
                welcome_progress=1200.0,
            )
        ],
        today=TODAY,
    )

    assert plan.welcome_open_count == 0
    assert plan.cards[0].welcome_status == "deadline_passed"
    assert "The deadline passed on Jul 01, 2026" in plan.cards[0].welcome_detail
    assert plan.welcome_detail == "No welcome bonus is open."


def test_earned_bonuses_are_summarised_when_nothing_is_open() -> None:
    plan = build_card_commitments(
        cards=[
            _card("a", SAPPHIRE, welcome_status="earned", welcome_progress=5831.5),
            _card("b", SAPPHIRE, welcome_status="earned", welcome_progress=5801.5),
        ],
        today=TODAY,
    )

    assert plan.welcome_open_count == 0
    assert plan.welcome_detail == "2 welcome bonuses already earned; nothing is open."


def test_only_open_cards_commit_the_household_to_anything() -> None:
    plan = build_card_commitments(
        cards=[
            _card("a", SAPPHIRE, fee_due="2027-08-02"),
            _card("b", SAPPHIRE, status="closed", fee_due="2027-08-02"),
            _card("c", SAPPHIRE, status="candidate", fee_due="2027-08-02"),
        ],
        today=TODAY,
    )

    assert [row.card_id for row in plan.cards] == ["a"]
    assert plan.annual_fee_yearly == 95.0


def test_no_open_cards_says_so_instead_of_reporting_zero_owed() -> None:
    """Card rotation is routine (D22): a card the plan cannot see is untracked money."""
    plan = build_card_commitments(cards=[], today=TODAY)

    assert plan.status == "no_cards"
    assert plan.balance_total is None
    assert "Add it on the Cards tab" in plan.detail


def test_a_half_cent_balance_reads_the_same_here_as_on_the_screen() -> None:
    """The row prints this text beside the browser's own formatting of the
    same number, and Python's default rounding would disagree with it."""
    plan = build_card_commitments(
        cards=[_card("a", SAPPHIRE, account_id="acct-1")],
        account_values={"acct-1": -5896.5},
        today=TODAY,
    )

    assert plan.cards[0].balance_owed == 5896.5
    assert plan.cards[0].balance_detail == "$5,897 owed right now."
