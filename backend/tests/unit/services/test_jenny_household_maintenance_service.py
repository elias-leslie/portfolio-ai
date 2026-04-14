"""Unit tests for Jenny household maintenance service."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

from app.services.jenny_household_maintenance_service import JennyHouseholdMaintenanceService


def test_replay_candidate_documents_targets_weak_docs_not_all_add_anything() -> None:
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = []

    maintenance._replay_candidate_documents(service)

    query = connection.execute.call_args.args[0]
    assert "filename = 'add-anything'" not in query
    assert "application_summary" in query
    assert "financial_accounts" in query
    assert "source_type IN ('bank', 'credit_card', 'brokerage', 'retirement')" in query


def test_run_daily_maintenance_pass_reads_dashboard_from_household_service() -> None:
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    dashboard = MagicMock()
    dashboard.overview.net_worth_status = "current"
    dashboard.overview.monthly_spend_status = "estimated"
    dashboard.inbox = []
    service.household_service.get_dashboard.return_value = dashboard
    cast(Any, maintenance)._replay_candidate_documents = MagicMock(
        return_value={"attempted": 0, "recovered": 0, "missing_source": 0, "unresolved": 0}
    )
    cast(Any, maintenance)._sync_household_notifications = MagicMock(return_value=0)

    result = maintenance.run_daily_maintenance_pass(service, routine_id="routine-1")

    service.household_service.get_dashboard.assert_called_once_with()
    assert result["documents_reviewed"] == 0


def test_replay_candidate_documents_recovers_applied_doc_without_source_file() -> None:
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("doc-1", "/missing/path.pdf", "parsed", "complete")
    ]
    service.household_service.get_document.return_value = SimpleNamespace(id="doc-1")
    service.household_service.document_pipeline.describe_application_state.return_value = {
        "status": "applied",
        "impacts": ["accounts"],
        "needs_follow_up": False,
    }

    result = maintenance._replay_candidate_documents(service)

    assert result == {
        "attempted": 0,
        "recovered": 1,
        "missing_source": 0,
        "unresolved": 0,
    }
    service.household_service.review_document.assert_not_called()
    service.household_service.document_pipeline.describe_application_state.assert_called_once()
    assert connection.commit.called
