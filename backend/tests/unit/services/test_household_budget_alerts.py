"""The three plan findings worth interrupting someone for (§7 3.7, D19)."""

from __future__ import annotations

from datetime import date

from app.models.household_finance import (
    HouseholdCapPlan,
    HouseholdOneTimePurchase,
    HouseholdSpendingCategory,
    HouseholdSpendingSummary,
    HouseholdSpendingView,
)
from app.services._household_budget_alerts import (
    MIN_DAYS_FOR_PROJECTION,
    NOVEL_PURCHASE_WINDOW_DAYS,
    build_budget_alerts,
)

TODAY = date(2026, 8, 20)


def _summary(**overrides) -> HouseholdSpendingSummary:
    base = {
        "month": "2026-08",
        "month_label": "August 2026",
        "is_month_to_date": True,
        "days_elapsed": 20,
        "days_in_month": 31,
        "total_spend": 4000.0,
        "average_monthly_spend": 6000.0,
    }
    base.update(overrides)
    return HouseholdSpendingSummary(**base)


def _plan(**overrides) -> HouseholdCapPlan:
    base = {"status": "proposed", "available_for_categories": 6000.0}
    base.update(overrides)
    return HouseholdCapPlan(**base)


def _category(
    name: str,
    *,
    spent: float,
    confirmed: float | None = None,
    found: float | None = None,
) -> HouseholdSpendingCategory:
    source = (
        "confirmed"
        if confirmed is not None
        else ("found_unconfirmed" if found is not None else "no_budget")
    )
    return HouseholdSpendingCategory(
        category=name,
        essentiality="mixed",
        total_spend=spent,
        average_monthly_spend=spent,
        share_of_spend=0.1,
        transaction_count=3,
        confirmed_monthly_budget=confirmed,
        found_monthly_budget=found,
        budget_source=source,
        effective_monthly_budget=confirmed if confirmed is not None else found,
    )


def _purchase(
    *,
    amount: float,
    day: int = 18,
    merchant: str = "Costco",
    transaction_id: str = "txn-1",
) -> HouseholdOneTimePurchase:
    return HouseholdOneTimePurchase(
        transaction_id=transaction_id,
        date=date(2026, 8, day).isoformat(),
        merchant=merchant,
        category="Household",
        amount=amount,
        share_of_month=0.9,
        reason="no precedent",
    )


def _view(**overrides) -> HouseholdSpendingView:
    base = {
        "generated_at": "2026-08-20T00:00:00+00:00",
        "summary": _summary(),
        "cap_plan": _plan(),
        "categories": [],
        "one_time_purchases": [],
    }
    base.update(overrides)
    return HouseholdSpendingView(**base)


def _kinds(view: HouseholdSpendingView, *, today: date = TODAY) -> list[str]:
    return [alert.kind for alert in build_budget_alerts(view, today=today)]


# -- a finished month ---------------------------------------------------------


def test_a_month_the_household_has_finished_living_raises_nothing() -> None:
    """A closed month is a thing to review, not a thing to head off."""
    view = _view(
        summary=_summary(is_month_to_date=False, total_spend=12000.0),
        categories=[_category("Groceries", spent=900.0, confirmed=500.0)],
    )

    assert _kinds(view) == []


# -- projected over plan ------------------------------------------------------


def test_a_month_running_past_its_plan_is_projected_not_extrapolated_silently() -> None:
    # $5,200 in 20 days runs to $8,060 against a $6,000 plan.
    view = _view(summary=_summary(total_spend=5200.0))

    [alert] = build_budget_alerts(view, today=TODAY)

    assert alert.kind == "month_projected_over_plan"
    assert alert.severity == "warning"
    assert "$8,060" in alert.body
    assert "$6,000" in alert.body
    assert "11 days left" in alert.body
    assert alert.marker_key == "month_projected_over_plan:2026-08"


def test_a_month_already_past_its_plan_earns_the_stronger_interrupt() -> None:
    """Days still to run with the plan already spent is a different fact."""
    view = _view(summary=_summary(total_spend=6500.0))

    [alert] = build_budget_alerts(view, today=TODAY)

    assert alert.kind == "month_over_plan"
    assert alert.severity == "critical"
    assert alert.marker_key == "month_over_plan:2026-08"


def test_a_month_on_pace_says_nothing() -> None:
    # $3,800 in 20 days runs to $5,890 — under the $6,000 plan.
    view = _view(summary=_summary(total_spend=3800.0))

    assert _kinds(view) == []


def test_a_projection_inside_the_tolerance_is_not_a_finding() -> None:
    """The same tolerance the dashboard's pace verdict uses, so the two agree."""
    # $3,900 in 20 days runs to $6,045 — $45 over a $6,000 plan, inside $300.
    view = _view(summary=_summary(total_spend=3900.0))

    assert _kinds(view) == []


def test_the_first_days_of_a_month_do_not_get_to_project_it() -> None:
    """One large grocery run on the 3rd projects to a month that never happens."""
    view = _view(
        summary=_summary(
            days_elapsed=MIN_DAYS_FOR_PROJECTION - 1, total_spend=3000.0
        ),
        cap_plan=_plan(),
    )

    assert _kinds(view) == []


def test_no_anchor_means_no_plan_to_exceed() -> None:
    """A verdict from an unset input is the thing this revamp exists to stop."""
    view = _view(
        summary=_summary(total_spend=9000.0),
        cap_plan=_plan(status="no_anchor", available_for_categories=0.0),
    )

    assert _kinds(view) == []


# -- a category at its cap ----------------------------------------------------


def test_reaching_a_cap_counts_not_only_passing_it() -> None:
    """D19 asked for 100% of cap, so equality is the crossing."""
    view = _view(categories=[_category("Groceries", spent=800.0, confirmed=800.0)])

    [alert] = build_budget_alerts(view, today=TODAY)

    assert alert.kind == "category_at_cap"
    assert alert.title == "Groceries has reached its cap"
    assert alert.marker_key == "category_at_cap:2026-08:Groceries"


def test_a_suggested_cap_never_interrupts_anyone() -> None:
    """It is the system's guess at what the household already spends.

    Alerting on one would interrupt a person to tell them they are spending
    what they usually spend.
    """
    view = _view(categories=[_category("Dining", spent=900.0, found=400.0)])

    assert _kinds(view) == []


def test_a_category_under_its_cap_is_not_a_finding() -> None:
    view = _view(categories=[_category("Groceries", spent=799.0, confirmed=800.0)])

    assert _kinds(view) == []


def test_a_cap_too_small_to_matter_does_not_buzz_a_phone() -> None:
    """Live the household holds a $17.09 Fitness cap beside a $1,100 Groceries one.

    Reaching the small one is arithmetic, not news, and pushing it is how a
    person learns to swipe these away.
    """
    view = _view(
        categories=[
            _category("Groceries", spent=500.0, confirmed=1000.0),
            _category("Fitness", spent=90.0, confirmed=17.0),
        ]
    )

    assert _kinds(view) == []


def test_the_floor_is_a_share_of_the_household_plan_not_a_dollar_figure() -> None:
    """The same cap is worth an interrupt in a small plan and noise in a large one."""
    small_plan = _view(
        categories=[
            _category("Dining", spent=90.0, confirmed=80.0),
            _category("Gas", spent=10.0, confirmed=100.0),
        ]
    )
    large_plan = _view(
        categories=[
            _category("Dining", spent=90.0, confirmed=80.0),
            _category("Mortgage", spent=10.0, confirmed=40000.0),
        ]
    )

    assert _kinds(small_plan) == ["category_at_cap"]
    assert _kinds(large_plan) == []


def test_caps_that_break_together_still_arrive_one_at_a_time() -> None:
    """Four at once is a wall of notifications; the rest wait for the next pass."""
    view = _view(
        categories=[
            _category("Dining", spent=700.0, confirmed=300.0),
            _category("Travel", spent=900.0, confirmed=250.0),
            _category("Groceries", spent=810.0, confirmed=800.0),
            _category("Household", spent=650.0, confirmed=400.0),
        ]
    )

    alerts = build_budget_alerts(view, today=TODAY)

    # Ordered by how far over, so the worst is never the one that waits.
    assert [alert.title.split(" has")[0] for alert in alerts] == [
        "Travel",
        "Dining",
        "Household",
    ]


# -- a purchase with no precedent ---------------------------------------------


def test_a_purchase_with_no_precedent_names_what_it_is_against() -> None:
    view = _view(one_time_purchases=[_purchase(amount=3000.0)])

    [alert] = build_budget_alerts(view, today=TODAY)

    assert alert.kind == "novel_purchase"
    assert "$3,000 at Costco" in alert.title
    # 3000/6000 of a *normal* month, not of the 20 days so far.
    assert "50% of a normal month" in alert.body
    assert alert.marker_key == "novel_purchase:txn-1"


def test_the_share_is_measured_against_a_normal_month_not_this_one() -> None:
    """The screen's denominator is the month so far, which on the 3rd is three
    days long — every large purchase would clear a fifth of it."""
    # $1,100 is 28% of the $4,000 spent so far but only 18% of a normal month.
    view = _view(one_time_purchases=[_purchase(amount=1100.0)])

    assert _kinds(view) == []


def test_a_purchase_from_earlier_in_the_month_is_not_news_today() -> None:
    """Without a window the first pass after a deploy pushes the whole month."""
    view = _view(
        one_time_purchases=[
            _purchase(amount=3000.0, day=20 - NOVEL_PURCHASE_WINDOW_DAYS - 1)
        ]
    )

    assert _kinds(view) == []


def test_a_purchase_is_alerted_once_ever_not_once_a_pass() -> None:
    """The marker is the transaction, so a second pass has nothing new to say."""
    view = _view(
        one_time_purchases=[
            _purchase(amount=3000.0, transaction_id="txn-a"),
            _purchase(amount=2500.0, transaction_id="txn-b", merchant="Best Buy"),
        ]
    )

    alerts = build_budget_alerts(view, today=TODAY)

    assert {alert.marker_key for alert in alerts} == {
        "novel_purchase:txn-a",
        "novel_purchase:txn-b",
    }


def test_no_history_to_compare_against_means_no_novelty_claim() -> None:
    """A household with no typical month cannot be told a purchase is unlike it."""
    view = _view(
        summary=_summary(average_monthly_spend=0.0),
        one_time_purchases=[_purchase(amount=9000.0)],
    )

    assert _kinds(view) == []


# -- the three together -------------------------------------------------------


def test_all_three_kinds_can_land_from_one_evaluation() -> None:
    view = _view(
        summary=_summary(total_spend=5200.0),
        categories=[_category("Groceries", spent=810.0, confirmed=800.0)],
        one_time_purchases=[_purchase(amount=3000.0)],
    )

    assert _kinds(view) == [
        "month_projected_over_plan",
        "category_at_cap",
        "novel_purchase",
    ]
