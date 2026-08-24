"""Saving is a declared state, not a $0 target reporting success (D17)."""

from __future__ import annotations

from datetime import date

from app.models.household_finance import HouseholdProfile
from app.services._household_dashboard_builders import (
    build_income_anchor,
    build_savings_plan,
)

TODAY = date(2026, 8, 24)
LIVE_INCOME = {"2026-05": 6067.39, "2026-06": 7984.87, "2026-07": 2804.36}


def _plan(**kwargs: object):
    profile = HouseholdProfile(
        id="profile-1",
        household_name="Household",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        **kwargs,
    )
    anchor = build_income_anchor(
        profile=profile, monthly_income=LIVE_INCOME, today=TODAY
    )
    return build_savings_plan(profile=profile, anchor=anchor, today=TODAY)


def test_a_zero_target_is_called_out_rather_than_passed() -> None:
    """The live profile's own value. Zero trivially keeps up with zero."""
    plan = _plan(monthly_savings_target=0.0)

    assert plan.status == "undeclared"
    assert "not a plan" in plan.headline
    assert "reports success for saving nothing" in plan.detail


def test_no_target_at_all_is_undeclared_too() -> None:
    plan = _plan()

    assert plan.status == "undeclared"
    assert plan.monthly_target is None


def test_an_active_target_says_what_it_leaves_rather_than_grading_it() -> None:
    plan = _plan(monthly_savings_target=1500.0)

    assert plan.status == "active"
    assert plan.leaves_for_spending == 4567.39
    assert "Leaves $4,567 of the $6,067 anchor" in plan.detail


def test_a_target_above_the_anchor_says_one_of_the_two_is_wrong() -> None:
    plan = _plan(monthly_savings_target=9000.0)

    assert plan.status == "active"
    assert "more than the $6,067" in plan.detail


def test_a_pause_carries_the_day_it_was_taken_and_why() -> None:
    plan = _plan(
        monthly_savings_target=0.0,
        savings_paused_on="2026-02-01",
        savings_pause_reason="On unemployment while SummitFlow is pending",
        savings_restart_income_threshold=8000.0,
    )

    assert plan.status == "paused"
    assert "Paused since Feb 01, 2026" in plan.detail
    assert "On unemployment while SummitFlow is pending" in plan.detail
    assert "$1,933 short" in plan.detail
    assert not plan.restart_ready


def test_the_pause_ends_itself_when_income_reaches_the_declared_trigger() -> None:
    plan = _plan(
        savings_paused_on="2026-02-01",
        savings_restart_income_threshold=5000.0,
    )

    assert plan.status == "restart_due"
    assert plan.restart_ready
    assert "$6,067" in plan.restart_detail
    assert "$5,000" in plan.restart_detail


def test_a_pause_with_no_trigger_says_nothing_will_ever_end_it() -> None:
    plan = _plan(savings_paused_on="2026-02-01")

    assert plan.status == "paused"
    assert "nothing will ever prompt this to resume" in plan.detail


def test_a_pause_cannot_be_judged_without_income_history() -> None:
    profile = HouseholdProfile(
        id="profile-1",
        household_name="Household",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        savings_paused_on="2026-02-01",
        savings_restart_income_threshold=8000.0,
    )
    anchor = build_income_anchor(profile=profile, monthly_income={}, today=TODAY)
    plan = build_savings_plan(profile=profile, anchor=anchor, today=TODAY)

    assert plan.status == "paused"
    assert not plan.restart_ready
    assert "not enough income history" in plan.detail


def test_the_pause_reads_the_same_anchor_the_screen_shows() -> None:
    """The trigger and the anchor are one number, never two readings of income."""
    plan = _plan(
        savings_paused_on="2026-02-01",
        savings_restart_income_threshold=8000.0,
        income_anchor_override=9000.0,
        income_anchor_override_set_on="2026-08-01",
    )

    # The declared anchor outranks the median, so the trigger is met on it.
    assert plan.anchor_monthly_income == 9000.0
    assert plan.status == "restart_due"
