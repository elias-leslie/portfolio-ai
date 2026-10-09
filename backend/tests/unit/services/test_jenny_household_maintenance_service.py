"""Unit tests for Jenny household maintenance service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from app.services import jenny_household_maintenance_service as maintenance_module
from app.services.jenny_household_maintenance_service import JennyHouseholdMaintenanceService


@pytest.fixture(autouse=True)
def _populated_upload_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "household_uploads"
    root.mkdir()
    (root / "other-document.pdf").write_bytes(b"%PDF-")
    monkeypatch.setattr(maintenance_module, "household_upload_root", lambda _service=None: root)
    return root


@pytest.mark.parametrize("create_root", [False, True])
def test_unavailable_upload_storage_never_marks_documents_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, create_root: bool
) -> None:
    """A missing or empty upload root is misconfiguration, not lost files.

    Managed releases are code-only snapshots; resolving uploads inside one made
    every intact receipt look deleted and told the household to re-upload it.
    """
    root = tmp_path / "release" / "data" / "household_uploads"
    if create_root:
        root.mkdir(parents=True)
    monkeypatch.setattr(maintenance_module, "household_upload_root", lambda _service=None: root)
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("doc-1", "doc-1.pdf", "needs_review", "failed")
    ]

    result = maintenance._replay_candidate_documents(service)

    assert result == {"attempted": 0, "recovered": 0, "missing_source": 0, "unresolved": 1}
    service.household_service.review_document.assert_not_called()
    assert not any(
        "source_missing" in str(call.args[1:]) or "review_status = 'complete'" in call.args[0]
        for call in connection.execute.call_args_list
    )


def test_replay_candidate_documents_targets_weak_docs_not_all_add_anything() -> None:
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = []

    maintenance._replay_candidate_documents(service)

    query = connection.execute.call_args.args[0]
    assert "filename = 'add-anything'" not in query
    assert "application_summary" in query
    assert "reconciliation_summary" in query
    assert "source_type IN ('bank', 'credit_card', 'brokerage', 'retirement')" in query
    assert "COALESCE(metadata->'reconciliation_summary'->>'status', '') = ''" in query
    assert "review_confidence" not in query
    assert "retry_recommended" in query
    assert "financial_accounts" not in query


def test_run_daily_maintenance_pass_reads_dashboard_from_household_service() -> None:
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    dashboard = MagicMock()
    dashboard.overview.net_worth_status = "current"
    dashboard.overview.monthly_spend_status = "estimated"
    dashboard.inbox = []
    service.household_service.get_dashboard.return_value = dashboard
    service.household_service.repair_transaction_system.return_value = {
        "canonicalized": 0,
        "rules_backfilled": 0,
        "provenance_backfilled": 0,
        "account_linked": 0,
        "application_summaries_repaired": 0,
    }
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
    connection.execute.return_value.fetchone.return_value = (10,)
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
    service.household_service.review_document.assert_called_once_with("doc-1")
    service.household_service.document_pipeline.describe_application_state.assert_called_once()
    assert connection.commit.called
    summary_call = next(
        call
        for call in connection.execute.call_args_list
        if "application_summary" in str(call.args[1][0])
    )
    assert '"recovered_without_source"' in summary_call.args[1][0]


def test_recovering_a_sourceless_document_takes_it_out_of_the_review_queue() -> None:
    """A file that is gone cannot be re-uploaded, and its money is already counted.

    Recovery used to write the summaries and stop, leaving the document at
    needs_review with "Re-upload or add more context." Acting on that advice is
    the one thing that could double-count spend the ledger already holds.
    """
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("doc-1", "/missing/path.pdf", "needs_review", "failed")
    ]
    connection.execute.return_value.fetchone.return_value = (10,)
    service.household_service.get_document.return_value = SimpleNamespace(id="doc-1")
    service.household_service.document_pipeline.describe_application_state.return_value = {
        "status": "applied",
        "transactions": {"inserted": 10, "updated": 10},
    }

    maintenance._replay_candidate_documents(service)

    settle = next(
        call
        for call in connection.execute.call_args_list
        if "review_status = 'complete'" in call.args[0]
    )
    assert "status = 'parsed'" in settle.args[0]
    assert "10 transaction(s) are in the ledger already" in settle.args[1][0]
    assert "re-upload" in settle.args[1][0]
    assert '"source_file_missing_spend_already_applied"' in settle.args[1][2]


def test_the_verified_count_comes_from_the_ledger_not_from_the_summary() -> None:
    """The reassurance and the evidence for it must not be able to drift apart."""
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("doc-1", "/missing/path.pdf", "needs_review", "failed")
    ]
    connection.execute.return_value.fetchone.return_value = (3,)
    service.household_service.get_document.return_value = SimpleNamespace(id="doc-1")
    service.household_service.document_pipeline.describe_application_state.return_value = {
        "status": "applied",
        # The summary claims 20 changes; the ledger holds 3 live rows.
        "transactions": {"inserted": 10, "updated": 10},
    }

    maintenance._replay_candidate_documents(service)

    settle = next(
        call
        for call in connection.execute.call_args_list
        if "review_status = 'complete'" in call.args[0]
    )
    assert "3 transaction(s)" in settle.args[1][0]
    count_query = next(
        call
        for call in connection.execute.call_args_list
        if "COUNT(*)" in call.args[0] and "household_transactions" in call.args[0]
    )
    assert "removed IS NOT TRUE" in count_query.args[0]


def test_a_sourceless_document_that_never_applied_says_so_instead_of_the_generic_failure() -> None:
    """Nothing landed and the file is gone, so re-uploading really is the fix.

    The document stays in the queue -- but it says why, rather than repeating
    "Jenny could not finish reviewing this document yet" on every pass.
    """
    maintenance = JennyHouseholdMaintenanceService()
    service = MagicMock()
    connection = service.storage.connection.return_value.__enter__.return_value
    connection.execute.return_value.fetchall.return_value = [
        ("doc-1", "/missing/path.pdf", "needs_review", "failed")
    ]
    service.household_service.get_document.return_value = SimpleNamespace(id="doc-1")
    service.household_service.document_pipeline.describe_application_state.return_value = {
        "status": "incomplete",
    }

    result = maintenance._replay_candidate_documents(service)

    assert result["missing_source"] == 1
    assert result["recovered"] == 0
    reported = next(
        call
        for call in connection.execute.call_args_list
        if "source_missing" in str(call.args[1][2:3])
    )
    assert "no longer on disk" in reported.args[1][0]
    assert "Upload it again" in reported.args[1][0]
    # It is still the household's move, so it stays in the queue.
    assert "review_status = 'complete'" not in reported.args[0]
    assert "status = 'parsed'" not in reported.args[0]
