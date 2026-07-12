"""Safety preconditions for household rebalance proposals."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.portfolio import ips_routes
from app.portfolio.contracts.ips import DriftCoverage, DriftReport
from app.portfolio.ips import RebalancePlanner


def _report(*, coverage: DriftCoverage) -> DriftReport:
    return DriftReport(
        scope="household",
        scope_id="default",
        snapshot_date=date(2026, 7, 12),
        total_value=100_000.0,
        coverage=coverage,
    )


class _EmptyResult:
    def fetchall(self) -> list[object]:
        return []


class _EmptyConnection:
    def execute(self, _query: str, _params: object = None) -> _EmptyResult:
        return _EmptyResult()


class _EmptyStorage:
    @contextmanager
    def connection(self):
        yield _EmptyConnection()


def _planner_with_reports(*reports: DriftReport) -> tuple[RebalancePlanner, MagicMock]:
    compute_drift = MagicMock(side_effect=list(reports))
    calculator = SimpleNamespace(
        compute_drift=compute_drift,
        storage=_EmptyStorage(),
    )
    return RebalancePlanner(calculator, MagicMock(), MagicMock()), compute_drift


def test_household_rebalance_computes_and_uses_one_checked_report(monkeypatch) -> None:
    complete = _report(
        coverage=DriftCoverage(
            status="complete",
            canonical_total_value=100_000.0,
            coverage_pct=1.0,
            excluded_value=0.0,
            message="Complete.",
        )
    )
    later_partial = _report(
        coverage=DriftCoverage(
            status="partial",
            canonical_total_value=100_000.0,
            coverage_pct=0.99,
            excluded_value=1_000.0,
            message="Holdings are incomplete.",
        )
    )
    planner, compute_drift = _planner_with_reports(complete, later_partial)
    monkeypatch.setattr(ips_routes, "_rebalance_planner", lambda: planner)

    result = asyncio.run(
        ips_routes.post_rebalance(
            ips_routes.RebalanceRequest(scope="household", scope_id="default")
        )
    )

    assert result.trades == []
    compute_drift.assert_called_once()


def test_household_rebalance_maps_incomplete_coverage_to_conflict(monkeypatch) -> None:
    partial = _report(
        coverage=DriftCoverage(
            status="partial",
            canonical_total_value=100_000.0,
            coverage_pct=0.99,
            excluded_value=1_000.0,
            message="Add holdings for the remaining account value.",
        )
    )
    planner, compute_drift = _planner_with_reports(partial)
    monkeypatch.setattr(ips_routes, "_rebalance_planner", lambda: planner)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            ips_routes.post_rebalance(
                ips_routes.RebalanceRequest(scope="household", scope_id="default")
            )
        )

    assert exc_info.value.status_code == 409
    assert "Add holdings" in str(exc_info.value.detail)
    compute_drift.assert_called_once()


def test_household_drift_labels_exactly_one_percent_gap_partial() -> None:
    coverage = ips_routes._household_drift_coverage(
        99_000.0,
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert coverage.status == "partial"
    assert coverage.coverage_pct == 0.99
    assert coverage.excluded_value == 1_000.0


def test_household_drift_allows_only_tiny_numeric_reconciliation_gap() -> None:
    coverage = ips_routes._household_drift_coverage(
        99_999.5,
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert coverage.status == "complete"


def test_household_drift_fails_closed_without_canonical_total() -> None:
    coverage = ips_routes._household_drift_coverage(
        70_000.0,
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=0)
        ),
        totals=SimpleNamespace(household_invested_total_value=None),
    )

    assert coverage.status == "unverified"
    assert "unavailable" in coverage.message


def test_household_drift_blocks_account_control_issues() -> None:
    coverage = ips_routes._household_drift_coverage(
        100_000.0,
        dashboard=SimpleNamespace(
            account_control=SimpleNamespace(blocking_issue_count=2)
        ),
        totals=SimpleNamespace(household_invested_total_value=100_000.0),
    )

    assert coverage.status == "blocked"
    assert "2 account-control issues" in coverage.message
