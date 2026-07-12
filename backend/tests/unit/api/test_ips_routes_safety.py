"""Safety preconditions for household rebalance proposals."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.api.portfolio.ips_routes import (
    _household_drift_coverage,
    _household_rebalance_blocker,
)
from app.portfolio.contracts.ips import DriftReport


def _report(total_value: float) -> DriftReport:
    return DriftReport(
        scope="household",
        scope_id="default",
        snapshot_date=date(2026, 7, 12),
        total_value=total_value,
    )


def test_household_rebalance_blocks_account_control_issues() -> None:
    blocker = _household_rebalance_blocker(
        _report(100_000.0),
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=2)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert blocker is not None
    assert "2 account-control issues" in blocker


def test_household_rebalance_blocks_material_coverage_mismatch() -> None:
    blocker = _household_rebalance_blocker(
        _report(70_000.0),
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert blocker is not None
    assert "70.0%" in blocker


def test_household_rebalance_allows_reconciled_coverage() -> None:
    blocker = _household_rebalance_blocker(
        _report(99_500.0),
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert blocker is None


def test_household_drift_labels_partial_coverage() -> None:
    coverage = _household_drift_coverage(
        70_000.0,
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert coverage.status == "partial"
    assert coverage.coverage_pct == 0.7
    assert coverage.excluded_value == 30_000.0


def test_household_rebalance_fails_closed_without_canonical_total() -> None:
    blocker = _household_rebalance_blocker(
        _report(70_000.0),
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=None),
    )

    assert blocker is not None
    assert "unavailable" in blocker
