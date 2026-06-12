"""Unit tests for household dashboard builder helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

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


def test_build_recurring_commitment_accepts_likely_monthly_labels() -> None:
    commitment = build_recurring_commitment(
        (
            "Duke Energy",
            "Bills",
            177.51,
            2,
            datetime(2026, 2, 9, tzinfo=UTC),
        ),
        "likely monthly",
        {"confidence": 0.82},
        date(2026, 2, 10),
    )

    assert commitment is not None
    assert commitment.cadence == "likely monthly"
    assert commitment.annualized_cost == 2130.12
    assert commitment.due_status == "upcoming"


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
