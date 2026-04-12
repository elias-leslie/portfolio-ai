"""Unit tests for household dashboard builder helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.services._household_dashboard_builders import build_recurring_commitment


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
