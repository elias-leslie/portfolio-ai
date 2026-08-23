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


def test_budget_snapshot_safe_to_spend_picks_binding_constraint() -> None:
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=5000, discretionary=1500, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
        cash_reserve=10000.0,
        recurring_commitments=[
            _commitment(average_amount=300.0, days_until_due=10),
            _commitment(average_amount=400.0, days_until_due=20),
            _commitment(average_amount=250.0, days_until_due=None),
        ],
    )

    # Only the bill inside 14 days counts toward due-soon.
    assert snapshot.due_soon_bills_total == 300.0
    assert snapshot.operating_cushion == 5000.0
    # Candidates: cash 10000-5000-300=4700, plan residual 9000-6500=2500,
    # discretionary headroom 1500-1300=200 -> headroom binds.
    assert snapshot.safe_to_spend == 200.0
    assert snapshot.safe_to_spend_constraint == "discretionary_cap"


def test_budget_snapshot_safe_to_spend_floors_at_zero_and_falls_back_to_essentials() -> None:
    snapshot = build_budget_snapshot(
        profile=_profile_for_pace(essential=None, discretionary=None, savings=None),
        reports=_reports_for_pace(),
        month_to_date_spend=3000,
        cash_reserve=2000.0,
        recurring_commitments=[_commitment(average_amount=600.0, days_until_due=3)],
    )

    # No essential target -> cushion falls back to observed average essentials.
    assert snapshot.operating_cushion == 4500.0
    # Cash path 2000-4500-600 is negative; figure floors at zero but still
    # names the cash path as the binding constraint.
    assert snapshot.safe_to_spend == 0.0
    assert snapshot.safe_to_spend_constraint == "cash_after_cushion"


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
