"""Unit tests for canonical household account summaries and inbox derivation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.household_finance import (
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdQuestion,
)
from app.portfolio.models import Account
from app.services._household_account_summary import (
    build_account_summaries,
    build_money_inbox,
)
from app.services._money_workspace_routes import (
    MONEY_ACCOUNTS_ROUTE,
    MONEY_CLARIFICATIONS_ROUTE,
    MONEY_EVIDENCE_ROUTE,
)


def _iso(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def test_build_account_summaries_groups_evidence_and_surfaces_freshness() -> None:
    documents = [
        HouseholdDocument(
            id="doc-new",
            filename="fidelity-april.pdf",
            source_type="brokerage",
            document_type="statement",
            status="parsed",
            account_label="Fidelity Brokerage",
            file_size_bytes=10,
            content_type="application/pdf",
            classification_confidence=0.95,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.95,
            statement_start=None,
            statement_end=_iso(5),
            uploaded_at=_iso(4),
            parsed_at=_iso(4),
            metadata={
                "file_available": True,
                "application_summary": {"status": "applied"},
            },
        ),
        HouseholdDocument(
            id="doc-old",
            filename="fidelity-march.pdf",
            source_type="brokerage",
            document_type="statement",
            status="parsed",
            account_label="Fidelity Brokerage",
            file_size_bytes=10,
            content_type="application/pdf",
            classification_confidence=0.92,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.92,
            statement_start=None,
            statement_end=_iso(45),
            uploaded_at=_iso(44),
            parsed_at=_iso(44),
            metadata={
                "file_available": True,
                "application_summary": {"status": "applied"},
            },
        ),
    ]
    evidence_accounts = [
        HouseholdEvidenceAccount(
            id="acct-new",
            document_id="doc-new",
            source_type="brokerage",
            asset_group="taxable",
            account_type="brokerage",
            institution_name="Fidelity",
            account_name="Brokerage",
            account_mask="1234",
            owner_name=None,
            currency="USD",
            balance=12100.0,
            holdings_value=11800.0,
            cash_balance=300.0,
            as_of_date=_iso(5),
            confidence=0.93,
            metadata={},
        ),
        HouseholdEvidenceAccount(
            id="acct-old",
            document_id="doc-old",
            source_type="brokerage",
            asset_group="taxable",
            account_type="brokerage",
            institution_name="Fidelity",
            account_name="Brokerage",
            account_mask="1234",
            owner_name=None,
            currency="USD",
            balance=11000.0,
            holdings_value=10700.0,
            cash_balance=300.0,
            as_of_date=_iso(45),
            confidence=0.9,
            metadata={},
        ),
    ]

    summaries = build_account_summaries(
        evidence_accounts=evidence_accounts,
        documents=documents,
        portfolio_accounts=[],
        holdings_by_account={},
        statement_freshness={"coverage_months": 3, "gap_months": []},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.label == "Fidelity · Brokerage"
    assert summary.current_value == 12100.0
    assert summary.evidence_count == 2
    assert summary.latest_document_id == "doc-new"
    assert summary.freshness_status == "fresh"
    assert summary.match_status == "tracked"
    assert not any(gap.code == "stale_evidence" for gap in summary.gap_flags)


def test_build_account_summaries_includes_portfolio_accounts_without_evidence() -> None:
    portfolio_account = Account(
        id="portfolio-1",
        name="Roth IRA",
        account_type="Roth",
        cash_balance=500.0,
    )

    summaries = build_account_summaries(
        evidence_accounts=[],
        documents=[],
        portfolio_accounts=[portfolio_account],
        holdings_by_account={"portfolio-1": 9500.0},
        statement_freshness={"coverage_months": 0, "gap_months": []},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.label == "Roth IRA"
    assert summary.current_value == 10000.0
    assert summary.freshness_status == "needs_evidence"
    assert summary.linked_portfolio_account_id == "portfolio-1"
    assert any(gap.code == "missing_evidence" for gap in summary.gap_flags)


def test_build_money_inbox_prioritizes_questions_and_account_gaps() -> None:
    account_summaries = build_account_summaries(
        evidence_accounts=[],
        documents=[],
        portfolio_accounts=[
            Account(
                id="portfolio-1",
                name="Joint Taxable",
                account_type="Taxable",
                cash_balance=0.0,
            )
        ],
        holdings_by_account={"portfolio-1": 15000.0},
        statement_freshness={"coverage_months": 0, "gap_months": ["1 month missing in range"]},
    )
    question = HouseholdQuestion(
        id="question-1",
        field_name="monthly_net_income_target",
        status="open",
        priority="high",
        question="Is this your main household checking account?",
        rationale="Jenny needs to know whether this account drives recurring bills.",
        recommendation="Answer yes if it is your primary checking account.",
        answer_text=None,
        source_document_id="doc-1",
        metadata={},
        created_at=_iso(1),
        answered_at=None,
    )

    inbox = build_money_inbox(
        accounts=account_summaries,
        questions=[question],
        tracked_documents=1,
        parsed_documents=0,
        statement_freshness={"coverage_months": 0, "gap_months": ["1 month missing in range"]},
    )

    assert inbox[0].title == "Finish evidence processing"
    assert inbox[0].action_href == MONEY_EVIDENCE_ROUTE
    assert any(item.related_question_id == "question-1" for item in inbox)
    assert any(
        item.related_question_id == "question-1"
        and item.action_href == MONEY_CLARIFICATIONS_ROUTE
        for item in inbox
    )
    assert any(item.related_account_id == account_summaries[0].id for item in inbox)
    assert any(
        item.related_account_id == account_summaries[0].id
        and item.action_href == MONEY_EVIDENCE_ROUTE
        for item in inbox
    )
    assert any(item.category == "coverage" for item in inbox)
    assert any(
        item.category == "coverage" and item.action_href == MONEY_ACCOUNTS_ROUTE
        for item in inbox
    )
