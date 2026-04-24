"""Unit tests for household dashboard builder helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.models.household_finance import (
    HouseholdExecutiveReport,
    HouseholdProfile,
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
