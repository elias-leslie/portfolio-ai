"""A lane is only configured when the household configured it.

"Configured" used to mean any resolved value at all, so the Lifestyle lane
reported Configured off an inferred $4,073.26 -- the discretionary spending the
household already does, copied back to it as a cap. All three lanes read
Configured while 17 of 19 category caps were unset.
"""

from __future__ import annotations

from app.models.household_finance import HouseholdResolvedValue
from app.services._household_dashboard_assembly import build_budget_readiness


def _value(field: str, value: str, status: str) -> HouseholdResolvedValue:
    return HouseholdResolvedValue(
        field_name=field,
        label=field,
        value=value,
        status=status,
        source="manual" if status == "confirmed" else "jenny_inference",
    )


def test_a_cap_copied_from_spending_is_not_a_configured_lane() -> None:
    readiness = build_budget_readiness(
        resolved_values=[
            _value("monthly_essential_target", "5000", "confirmed"),
            _value("monthly_discretionary_target", "4073.26", "inferred"),
            _value("monthly_savings_target", "0", "confirmed"),
        ],
        documents=[object()],
    )

    assert [lane.status for lane in readiness.starter_lanes] == [
        "Configured",
        "Inferred from spending",
        "Configured",
    ]
    assert readiness.status == "partially_configured"
    assert "Lifestyle" in readiness.summary


def test_readiness_is_claimed_only_when_every_lane_was_set_by_a_person() -> None:
    readiness = build_budget_readiness(
        resolved_values=[
            _value("monthly_net_income_target", "6283.33", "confirmed"),
            _value("monthly_essential_target", "5000", "confirmed"),
            _value("monthly_discretionary_target", "1500", "confirmed"),
            _value("monthly_savings_target", "800", "confirmed"),
        ],
        documents=[object()],
    )

    assert readiness.status == "ready_for_budgeting"
    assert all(lane.status == "Configured" for lane in readiness.starter_lanes)


def test_a_household_with_no_targets_is_not_ready_however_much_evidence_arrives() -> None:
    readiness = build_budget_readiness(resolved_values=[], documents=[object()] * 40)

    assert readiness.status == "setup_needed"
    assert all(lane.status == "Needs target" for lane in readiness.starter_lanes)
