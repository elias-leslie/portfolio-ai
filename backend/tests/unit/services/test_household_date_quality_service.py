"""Unit tests for household date-quality mutations."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.household_finance import HouseholdTransactionDateIssueResolution
from app.services.household_date_quality_service import HouseholdDateQualityService


def _service_with_connection() -> tuple[SimpleNamespace, MagicMock]:
    service = SimpleNamespace(storage=MagicMock())
    conn = service.storage.connection.return_value.__enter__.return_value
    return service, conn


def test_resolve_document_issue_marks_summary_resolved() -> None:
    service, conn = _service_with_connection()
    conn.execute.return_value.fetchone.return_value = ("doc-1",)

    updated = HouseholdDateQualityService().resolve_issue(
        service,
        issue_id="future-date-document-doc-1-0",
        payload=HouseholdTransactionDateIssueResolution(
            resolution="date_confirmed_future",
            note="September order date is real.",
        ),
    )

    assert updated is True
    sql, params = conn.execute.call_args.args
    assert "UPDATE household_documents" in sql
    patch = json.loads(params[0])
    assert patch["status"] == "resolved"
    assert patch["resolution"] == "date_confirmed_future"
    assert patch["resolved_issue_id"] == "future-date-document-doc-1-0"
    assert patch["resolution_note"] == "September order date is real."
    conn.commit.assert_called_once()


def test_resolve_transaction_issue_marks_transaction_resolution() -> None:
    service, conn = _service_with_connection()
    conn.execute.return_value.fetchone.return_value = ("txn-1",)

    updated = HouseholdDateQualityService().resolve_issue(
        service,
        issue_id="future-date-txn-1",
        payload=HouseholdTransactionDateIssueResolution(
            resolution="date_confirmed_future",
        ),
    )

    assert updated is True
    sql, params = conn.execute.call_args.args
    assert "UPDATE household_transactions" in sql
    patch = json.loads(params[0])["date_quality_resolution"]
    assert patch["status"] == "resolved"
    assert patch["resolution"] == "date_confirmed_future"
    conn.commit.assert_called_once()


def test_mark_replaced_document_supersedes_document_and_future_rows() -> None:
    service, conn = _service_with_connection()
    document_result = MagicMock()
    document_result.fetchone.return_value = ("doc-old",)
    transaction_result = MagicMock()
    conn.execute.side_effect = [document_result, transaction_result]

    updated = HouseholdDateQualityService().mark_replaced_document(
        service,
        replaced_document_id="doc-old",
        replacement_document_id="doc-new",
        issue_id="future-date-document-doc-old-0",
    )

    assert updated is True
    document_patch = json.loads(conn.execute.call_args_list[0].args[1][0])
    transaction_patch = json.loads(conn.execute.call_args_list[1].args[1][0])[
        "date_quality_resolution"
    ]
    assert document_patch["status"] == "superseded"
    assert document_patch["replacement_document_id"] == "doc-new"
    assert transaction_patch["status"] == "superseded"
    assert transaction_patch["replacement_document_id"] == "doc-new"
    conn.commit.assert_called_once()


def test_supersede_matching_document_issues_marks_exact_receipt_match() -> None:
    service, conn = _service_with_connection()
    list_result = MagicMock()
    list_result.fetchall.return_value = [
        (
            "doc-old",
            [{"amount": "164.14"}],
            "https://www.walmart.com/orders/084371683152095307956?groupId=0",
            {"total_amount": "164.14"},
        )
    ]
    document_result = MagicMock()
    document_result.fetchone.return_value = ("doc-old",)
    transaction_result = MagicMock()
    conn.execute.side_effect = [list_result, document_result, transaction_result]

    updated = HouseholdDateQualityService().supersede_matching_document_issues(
        service,
        replacement_document_id="doc-new",
        reviewed={
            "extracted_text": "https://www.walmart.com/orders/084371683152095307956?groupId=0",
            "structured_data": {"total_amount": "164.14"},
        },
    )

    assert updated == 1
    patch = json.loads(conn.execute.call_args_list[1].args[1][0])
    assert patch["status"] == "superseded"
    assert patch["replacement_document_id"] == "doc-new"
    conn.commit.assert_called_once()


def test_supersede_matching_document_issues_requires_amount_match() -> None:
    service, conn = _service_with_connection()
    list_result = MagicMock()
    list_result.fetchall.return_value = [
        (
            "doc-old",
            [{"amount": "164.14"}],
            "https://www.walmart.com/orders/084371683152095307956?groupId=0",
            {"total_amount": "164.14"},
        )
    ]
    conn.execute.return_value = list_result

    updated = HouseholdDateQualityService().supersede_matching_document_issues(
        service,
        replacement_document_id="doc-new",
        reviewed={
            "extracted_text": "https://www.walmart.com/orders/084371683152095307956?groupId=0",
            "structured_data": {"total_amount": "165.00"},
        },
    )

    assert updated == 0
    conn.commit.assert_not_called()


def test_unknown_resolution_is_rejected() -> None:
    service, _conn = _service_with_connection()

    try:
        HouseholdDateQualityService().resolve_issue(
            service,
            issue_id="future-date-txn-1",
            payload=HouseholdTransactionDateIssueResolution(resolution="hide_it"),
        )
    except ValueError as exc:
        assert "Unsupported date issue resolution" in str(exc)
    else:
        raise AssertionError("Expected unsupported date issue resolution to fail")
