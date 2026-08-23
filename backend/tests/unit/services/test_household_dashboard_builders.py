"""Unit tests for household dashboard builder helpers."""

from __future__ import annotations

from datetime import date

from app.models.household_finance import (
    HouseholdExecutiveReport,
    HouseholdProfile,
    HouseholdRecurringCommitment,
    HouseholdReports,
)
from app.services._household_dashboard_builders import (
    build_budget_snapshot,
    build_recurring_commitment,
    build_retirement_contribution_tracker,
)
from app.services._household_recurrence import (
    CADENCE_DAYS,
    CADENCE_LABELS,
    RecurrencePattern,
)


def _pattern(
    *,
    cadence: str,
    typical_amount: float,
    last_seen: date,
    sightings: int = 6,
    confidence: float = 0.9,
) -> RecurrencePattern:
    return RecurrencePattern(
        cadence=cadence,
        label=CADENCE_LABELS[cadence],
        confidence=confidence,
        typical_amount=typical_amount,
        last_seen=last_seen,
        sightings=sightings,
        median_interval_days=CADENCE_DAYS[cadence],
        span_days=CADENCE_DAYS[cadence] * (sightings - 1),
        distinct_months=sightings,
        evidence="test pattern",
    )


def test_an_annual_bill_becomes_a_commitment_and_is_not_annualized_twelve_times() -> None:
    """A once-a-year bill was not a cadence the builder recognised at all.

    Without ``annual`` in the vocabulary an HOA or a property tax fell straight
    through, so it never reached a sinking fund -- which is the exact shape of
    under-funding the fund is meant to prevent.
    """
    commitment = build_recurring_commitment(
        merchant="Lakeside Association",
        category="Home",
        pattern=_pattern(
            cadence="annual",
            typical_amount=104.13,
            last_seen=date(2026, 2, 17),
            sightings=1,
            confidence=1.0,
        ),
        today=date(2026, 8, 22),
    )

    assert commitment is not None
    assert commitment.cadence == "likely annual"
    assert commitment.annualized_cost == 104.13
    assert commitment.next_expected is not None
    assert commitment.next_expected.startswith("2027-02-17")
    assert commitment.due_status == "upcoming"
    assert commitment.commitment_type == "bill"


def test_a_travel_merchant_that_does_recur_is_a_purchase_and_not_a_bill() -> None:
    """Cadence alone does not make an obligation.

    A monthly flight is a monthly flight. Calling it a bill is what let a
    vacation sit at the head of the household's recurring commitments and be
    counted as money already owed.
    """
    commitment = build_recurring_commitment(
        merchant="Lufthansa",
        category="Travel",
        pattern=_pattern(
            cadence="monthly", typical_amount=400.0, last_seen=date(2026, 8, 2)
        ),
        today=date(2026, 8, 22),
    )

    assert commitment is not None
    assert commitment.commitment_type == "recurring_purchase"


def test_a_series_that_stopped_two_cycles_ago_is_no_longer_a_commitment() -> None:
    """A monthly bill last seen in June is not "overdue by fifty days".

    It is a series that ended -- a cancelled subscription, or a merchant renamed
    underneath the feed -- and presenting it as due invents money owed.
    """
    lapsed = build_recurring_commitment(
        merchant="All Smiles Ortho Clear",
        category="Healthcare",
        pattern=_pattern(
            cadence="monthly", typical_amount=132.08, last_seen=date(2026, 6, 2)
        ),
        today=date(2026, 8, 22),
    )
    still_running = build_recurring_commitment(
        merchant="All Smiles Ortho",
        category="Healthcare",
        pattern=_pattern(
            cadence="monthly", typical_amount=132.08, last_seen=date(2026, 8, 4)
        ),
        today=date(2026, 8, 22),
    )

    assert lapsed is None
    assert still_running is not None
    assert still_running.due_status == "upcoming"


def test_build_budget_snapshot_exposes_profile_plan_source() -> None:
    snapshot = build_budget_snapshot(
        profile=HouseholdProfile(
            id="profile-1",
            household_name="Household",
            monthly_net_income_target=9000,
            monthly_essential_target=5000,
            monthly_discretionary_target=1500,
            monthly_savings_target=None,
            target_retirement_age=None,
            target_retirement_spend=None,
            notes=None,
            created_at="2026-04-24T00:00:00Z",
            updated_at="2026-04-24T00:00:00Z",
        ),
        reports=HouseholdReports(
            executive=HouseholdExecutiveReport(
                headline="Visible",
                summary="Visible",
                average_monthly_spend=6100,
                average_monthly_essentials=4500,
                average_monthly_discretionary=1300,
                recent_30_day_spend=6000,
                recurring_merchant_count=0,
                tracked_expense_count=10,
                coverage_months=3,
            )
        ),
        month_to_date_spend=3000,
    )

    assert snapshot.monthly_plan_total == 6500
    assert snapshot.monthly_plan_source == "household_profile_targets"
    assert snapshot.monthly_plan_source_label == "Household profile targets"


def _reports_for_pace() -> HouseholdReports:
    return HouseholdReports(
        executive=HouseholdExecutiveReport(
            headline="Visible",
            summary="Visible",
            average_monthly_spend=6100,
            average_monthly_essentials=4500,
            average_monthly_discretionary=1300,
            recent_30_day_spend=6000,
            recurring_merchant_count=0,
            tracked_expense_count=10,
            coverage_months=3,
        )
    )


def _profile_for_pace(
    *, essential: float | None, discretionary: float | None, savings: float | None
) -> HouseholdProfile:
    return HouseholdProfile(
        id="profile-1",
        household_name="Household",
        monthly_net_income_target=9000,
        monthly_essential_target=essential,
        monthly_discretionary_target=discretionary,
        monthly_savings_target=savings,
        target_retirement_age=None,
        target_retirement_spend=None,
        notes=None,
        created_at="2026-04-24T00:00:00Z",
        updated_at="2026-04-24T00:00:00Z",
    )


def test_partial_plan_does_not_read_as_running_hot() -> None:
    # Only essentials is set: total month-to-date spend (well above the prorated
    # essentials-only plan) must NOT be paced as "running hot".
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=None, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=99999,
    )
    assert snapshot.plan_is_partial is True
    assert snapshot.missing_plan_components == ["discretionary", "savings"]
    assert snapshot.pace_status == "partial_plan"


def test_full_plan_still_paces_against_total() -> None:
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=1500),
        reports=_reports_for_pace(),
        month_to_date_spend=200,
    )
    assert snapshot.plan_is_partial is False
    assert snapshot.missing_plan_components == []
    assert snapshot.pace_status != "partial_plan"


def test_a_partial_plan_gets_no_verdict_at_all_rather_than_on_track() -> None:
    """Two verdicts in one payload, and one of them came from nothing.

    ``status: on_track`` was the fall-through for every case the lane checks did
    not catch -- including "the targets are not set" -- so it sat next to
    ``pace_status: partial_plan`` and an average spend well over the plan total.
    """
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=None, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=7342,
    )

    assert snapshot.status == "plan_incomplete"
    assert "discretionary or savings" in snapshot.summary
    assert "6,100" in snapshot.summary


def test_spending_over_a_complete_plan_is_not_on_track_even_with_every_lane_inside() -> None:
    """$6,100 a month against a $5,600 plan is not inside the guardrails.

    Each lane can sit under its own cap while the total still misses, because the
    lanes do not have to add up to the plan.
    """
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=-900),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
    )

    assert snapshot.monthly_plan_total == 5600
    assert snapshot.status == "above_plan"
    assert "not holding" in snapshot.summary


def test_a_plan_the_spending_fits_inside_is_still_allowed_to_say_so() -> None:
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=1500),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
    )

    assert snapshot.status == "on_track"


def test_a_zero_savings_target_is_not_evidence_that_saving_is_on_track() -> None:
    """Zero trivially keeps up with zero.

    The tracker reported ``on_track`` with a $0 target, $0 contributions and a $0
    gap, over the sentence "Recent retirement contributions are keeping up with
    the savings target".
    """
    tracker = build_retirement_contribution_tracker(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=0.0),
        estimated_monthly_contributions=0.0,
    )

    assert tracker.status == "target_missing"
    assert tracker.monthly_target is None
    assert "nothing to measure" in tracker.detail


def test_a_real_savings_target_is_still_measured() -> None:
    tracker = build_retirement_contribution_tracker(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=800.0),
        estimated_monthly_contributions=900.0,
    )

    assert tracker.status == "on_track"
    assert tracker.monthly_gap == 0.0


def _commitment(*, average_amount: float, days_until_due: int | None) -> HouseholdRecurringCommitment:
    return HouseholdRecurringCommitment(
        merchant="Duke Energy",
        category="Bills",
        cadence="monthly",
        average_amount=average_amount,
        annualized_cost=average_amount * 12,
        last_seen="2026-06-01",
        days_until_due=days_until_due,
        commitment_type="bill",
    )


def test_free_to_spend_is_cash_minus_what_is_already_owed() -> None:
    """The figure is arithmetic on money, not on two targets.

    The old Safe-to-Spend was usually bound by ``plan_residual`` -- monthly
    income target minus monthly plan total -- so it read $1,283 while $30,494.75
    sat in the CMA and $17,287.71 was owed on three cards. Neither number
    reached it.
    """
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=7342.12,
        month_to_date_essential_spend=5748.61,
        cash_reserve=30494.75,
        card_balances=17287.71,
        today=date(2026, 8, 23),
        recurring_commitments=[
            _commitment(average_amount=300.0, days_until_due=10),
            _commitment(average_amount=400.0, days_until_due=20),
            _commitment(average_amount=250.0, days_until_due=None),
        ],
    )

    affordability = snapshot.affordability
    assert affordability is not None
    assert affordability.cash_on_hand == 30494.75
    # Aug 31 is 8 days away, so the horizon is the further of the two: Sep 6.
    assert affordability.bills_due_through == "2026-09-06"
    assert affordability.bills_due == 300.0
    # August's 5,000 essentials baseline is already spent, so what remains is
    # the eight days still to come at the same rate, not nothing.
    assert affordability.remaining_essentials == 1290.32
    assert affordability.card_balances == 17287.71
    assert affordability.free_to_spend == 11616.72
    assert snapshot.safe_to_spend == 11616.72
    assert snapshot.safe_to_spend_constraint == "cash_after_commitments"


def test_free_to_spend_names_the_inputs_the_household_has_not_given_yet() -> None:
    """Treating an unknown as zero is the same lie in a new place."""
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
        cash_reserve=10000.0,
        today=date(2026, 8, 23),
        recurring_commitments=[_commitment(average_amount=300.0, days_until_due=10)],
    )

    affordability = snapshot.affordability
    assert affordability is not None
    assert affordability.missing_inputs == [
        "essential_spend_to_date",
        "sinking_fund_balances",
        "card_balances",
    ]
    # Nothing is known to be spent yet, so the whole baseline is still ahead.
    assert affordability.remaining_essentials == 5000.0


def test_free_to_spend_says_how_big_the_hole_is_rather_than_showing_zero() -> None:
    """A household that cannot cover what it owes needs the size of the gap.

    The old figure floored at zero, which reads as "spend nothing more" when it
    actually means "you are already short".
    """
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=None, discretionary=None, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
        month_to_date_essential_spend=0.0,
        cash_reserve=2000.0,
        card_balances=17287.71,
        today=date(2026, 8, 23),
        recurring_commitments=[_commitment(average_amount=600.0, days_until_due=3)],
    )

    # No essential target -> the baseline falls back to observed average essentials.
    assert snapshot.operating_cushion == 4500.0
    assert snapshot.safe_to_spend == 2000.0 - 600.0 - 4500.0 - 17287.71
    assert snapshot.safe_to_spend_constraint == "cash_after_commitments"


def test_budget_snapshot_safe_to_spend_null_without_cash_context() -> None:
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
    )

    assert snapshot.safe_to_spend is None
    assert snapshot.safe_to_spend_constraint is None
    assert snapshot.due_soon_bills_total is None
    assert snapshot.operating_cushion == 5000.0
