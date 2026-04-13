"""Unit tests for canonical household account summaries and inbox derivation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.household_finance import (
    HouseholdDiscoveredAccount,
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdQuestion,
    HouseholdTrackedAccount,
)
from app.portfolio.models import Account
from app.services._household_account_summary import (
    build_account_summaries,
    build_money_inbox,
)
from app.services._money_workspace_routes import (
    MONEY_ACCOUNTS_ROUTE,
    MONEY_CLARIFICATIONS_ROUTE,
    MONEY_DATE_QUALITY_ROUTE,
    MONEY_EVIDENCE_ROUTE,
    money_account_focus_route,
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
        tracked_accounts=[],
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
        tracked_accounts=[],
        holdings_by_account={"portfolio-1": 9500.0},
        statement_freshness={"coverage_months": 0, "gap_months": []},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.label == "Roth IRA"
    assert summary.current_value == 10000.0
    assert summary.freshness_status == "needs_evidence"
    assert summary.linked_portfolio_account_id == "portfolio-1"
    assert summary.match_confidence is None
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
        tracked_accounts=[],
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
        and item.action_href == money_account_focus_route(account_summaries[0].id, intent='evidence')
        for item in inbox
    )
    assert any(item.category == "coverage" for item in inbox)
    assert any(
        item.category == "coverage" and item.action_href == MONEY_ACCOUNTS_ROUTE
        for item in inbox
    )


def test_build_money_inbox_routes_future_date_issues_to_focused_evidence_review() -> None:
    inbox = build_money_inbox(
        accounts=[],
        questions=[],
        tracked_documents=3,
        parsed_documents=3,
        statement_freshness={
            "coverage_months": 3,
            "gap_months": [],
            "future_transaction_count": 2,
            "latest_future_date": "2026-09-03",
        },
    )

    assert inbox[0].id == "cashflow-future-transaction-dates"
    assert inbox[0].action_label == "Review dates"
    assert inbox[0].action_href == MONEY_DATE_QUALITY_ROUTE


def test_build_account_summaries_marks_stale_spending_transactions_and_routes_to_statements() -> None:
    documents = [
        HouseholdDocument(
            id="doc-checking",
            filename="checking.pdf",
            source_type="bank",
            document_type="statement",
            status="parsed",
            account_label="Joint Checking",
            file_size_bytes=10,
            content_type="application/pdf",
            classification_confidence=0.94,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.94,
            statement_start=None,
            statement_end=_iso(2),
            uploaded_at=_iso(1),
            parsed_at=_iso(1),
            metadata={
                "file_available": True,
                "application_summary": {"status": "applied"},
            },
        )
    ]
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-checking",
                document_id="doc-checking",
                source_type="bank",
                asset_group="cash",
                account_type="checking",
                institution_name="Wells Fargo",
                account_name="Joint Checking",
                account_mask="4421",
                owner_name=None,
                currency="USD",
                balance=4200.0,
                holdings_value=None,
                cash_balance=4200.0,
                as_of_date=_iso(2),
                confidence=0.95,
                metadata={},
            )
        ],
        documents=documents,
        portfolio_accounts=[],
        tracked_accounts=[],
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
        latest_transaction_dates_by_document={"doc-checking": (datetime.now(UTC) - timedelta(days=12)).date()},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.money_role == "spend_driver"
    assert summary.balance_freshness_status == "fresh"
    assert summary.transaction_freshness_status == "stale"
    assert any(gap.code == "stale_transactions" for gap in summary.gap_flags)

    inbox = build_money_inbox(
        accounts=summaries,
        questions=[],
        tracked_documents=1,
        parsed_documents=1,
        statement_freshness={"coverage_months": 1, "gap_months": []},
    )

    assert any(item.title == "Refresh transactions for Wells Fargo · Joint Checking" for item in inbox)
    assert any(item.action_label == "Add statements" for item in inbox)
    assert any(
        item.action_href == money_account_focus_route(summary.id, intent='evidence')
        for item in inbox
    )
    assert any(
        "covering" in item.detail
        and "Blocks monthly spend, budget status, and safe to spend." in item.detail
        for item in inbox
    )


def test_build_account_summaries_use_activity_observed_through_for_spend_driver_freshness() -> None:
    documents = [
        HouseholdDocument(
            id="doc-cash",
            filename="cash-activity.txt",
            source_type="brokerage",
            document_type="brokerage_statement",
            status="parsed",
            account_label="Cash Management (Joint WROS)",
            file_size_bytes=10,
            content_type="text/plain",
            classification_confidence=0.94,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.94,
            statement_start=None,
            statement_end=_iso(0),
            uploaded_at=_iso(0),
            parsed_at=_iso(0),
            metadata={
                "file_available": True,
                "application_summary": {"status": "applied"},
            },
        )
    ]
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-cash",
                document_id="doc-cash",
                source_type="brokerage",
                asset_group="taxable",
                account_type="brokerage",
                institution_name="Fidelity",
                account_name="Cash Management (Joint WROS)",
                account_mask="Z38367298",
                owner_name=None,
                currency="USD",
                balance=39400.59,
                holdings_value=39400.59,
                cash_balance=33400.59,
                as_of_date=_iso(0),
                confidence=0.95,
                metadata={"activity_observed_through": _iso(0)},
            )
        ],
        documents=documents,
        portfolio_accounts=[],
        tracked_accounts=[],
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
        latest_transaction_dates_by_document={"doc-cash": (datetime.now(UTC) - timedelta(days=5)).date()},
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.money_role == "spend_driver"
    assert summary.last_transaction_at is not None
    assert summary.last_transaction_at.startswith((datetime.now(UTC) - timedelta(days=5)).date().isoformat())
    assert summary.transaction_freshness_status == "fresh"
    assert not any(gap.code == "refresh_transactions_soon" for gap in summary.gap_flags)


def test_build_account_summaries_merge_same_mask_across_alias_names() -> None:
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-summary",
                document_id="doc-summary",
                source_type="brokerage",
                asset_group="taxable",
                account_type="brokerage",
                institution_name="Fidelity",
                account_name="Cash Management (Joint WROS)",
                account_mask="Z38367298",
                owner_name=None,
                currency="USD",
                balance=39400.59,
                holdings_value=33400.59,
                cash_balance=33400.59,
                as_of_date=_iso(3),
                confidence=0.95,
                metadata={},
            ),
            HouseholdEvidenceAccount(
                id="acct-csv",
                document_id="doc-csv",
                source_type="brokerage",
                asset_group="taxable",
                account_type="brokerage",
                institution_name=None,
                account_name="Account Z38367298",
                account_mask="Z38367298",
                owner_name=None,
                currency="USD",
                balance=39400.59,
                holdings_value=39400.59,
                cash_balance=39400.59,
                as_of_date=_iso(5),
                confidence=0.9,
                metadata={},
            ),
        ],
        documents=[],
        portfolio_accounts=[],
        tracked_accounts=[],
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
        latest_transaction_dates_by_account_label={
            "Cash Management (Joint WROS)": (datetime.now(UTC) - timedelta(days=5)).date(),
            "Account Z38367298": (datetime.now(UTC) - timedelta(days=5)).date(),
        },
    )

    assert len(summaries) == 1
    assert summaries[0].label == "Fidelity · Cash Management (Joint WROS)"
    assert summaries[0].account_mask == "Z38367298"
    assert summaries[0].evidence_count == 2
    assert summaries[0].institution_name == "Fidelity"


def test_build_account_summaries_merge_same_institution_mask_across_source_types() -> None:
    portfolio_account = Account(
        id="portfolio-roth",
        name="ROTH IRA",
        account_type="Roth",
        cash_balance=0.0,
    )
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-older",
                document_id="doc-older",
                source_type="brokerage",
                asset_group="retirement",
                account_type="roth_ira",
                institution_name="Fidelity",
                account_name="ROTH IRA",
                account_mask="250696445",
                owner_name=None,
                currency="USD",
                balance=48014.15,
                holdings_value=48014.15,
                cash_balance=None,
                as_of_date="2026-03-31",
                confidence=0.92,
                metadata={},
            ),
            HouseholdEvidenceAccount(
                id="acct-newer",
                document_id="doc-newer",
                source_type="retirement",
                asset_group="retirement",
                account_type="roth_ira",
                institution_name="Fidelity",
                account_name="ROTH IRA",
                account_mask="250696445",
                owner_name=None,
                currency="USD",
                balance=48014.15,
                holdings_value=48014.15,
                cash_balance=None,
                as_of_date="2026-04-12",
                confidence=0.95,
                metadata={},
            ),
        ],
        documents=[],
        portfolio_accounts=[portfolio_account],
        tracked_accounts=[],
        holdings_by_account={"portfolio-roth": 48014.15},
        statement_freshness={"coverage_months": 1, "gap_months": []},
    )

    assert len(summaries) == 1
    assert summaries[0].label == "ROTH IRA"
    assert summaries[0].source_type == "retirement"
    assert summaries[0].evidence_count == 2
    assert summaries[0].linked_portfolio_account_id == "portfolio-roth"
    assert summaries[0].last_balance_at is not None
    assert summaries[0].last_balance_at.startswith("2026-04-12")


def test_build_money_inbox_surfaces_discovered_accounts_with_review_route() -> None:
    inbox = build_money_inbox(
        accounts=[],
        discovered_accounts=[
            HouseholdDiscoveredAccount(
                key="discover-chase-1234",
                institution="Chase",
                partial_account="1234",
                suggested_label="Chase · …1234",
                asset_group="credit",
                account_type="credit_card",
                source_type="credit_card",
                confidence=0.87,
                occurrence_count=3,
                sample_description="AUTOPAY CHASE ...1234",
                detail="Three imported rows reference a possible Chase credit card ending in 1234.",
            )
        ],
        questions=[],
        tracked_documents=2,
        parsed_documents=2,
        statement_freshness={"coverage_months": 2, "gap_months": []},
    )

    assert any(item.title == "Confirm possible account: Chase · …1234" for item in inbox)
    assert any(item.action_href == "/money?tab=accounts&focus=discovered-accounts" for item in inbox)


def test_build_account_summaries_links_evidence_to_tracked_accounts() -> None:
    documents = [
        HouseholdDocument(
            id="doc-1",
            filename="checking-april.pdf",
            source_type="bank",
            document_type="statement",
            status="parsed",
            account_label="Main Checking",
            file_size_bytes=10,
            content_type="application/pdf",
            classification_confidence=0.94,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.94,
            statement_start=None,
            statement_end=_iso(3),
            uploaded_at=_iso(2),
            parsed_at=_iso(2),
            metadata={
                "file_available": True,
                "application_summary": {"status": "applied"},
            },
        )
    ]
    evidence_accounts = [
        HouseholdEvidenceAccount(
            id="acct-1",
            document_id="doc-1",
            source_type="bank",
            asset_group="cash",
            account_type="checking",
            institution_name="Fidelity",
            account_name="Cash Management",
            account_mask="4421",
            owner_name=None,
            currency="USD",
            balance=25057.0,
            holdings_value=None,
            cash_balance=25057.0,
            as_of_date=_iso(3),
            confidence=0.93,
            metadata={},
        )
    ]
    tracked_accounts = [
        HouseholdTrackedAccount(
            id="tracked-1",
            label="Main Checking",
            asset_group="cash",
            account_type="checking",
            source_type="bank",
            institution_name="Fidelity",
            owner_name=None,
            account_mask="4421",
            notes=None,
            created_at=_iso(10),
            updated_at=_iso(1),
        )
    ]

    summaries = build_account_summaries(
        evidence_accounts=evidence_accounts,
        documents=documents,
        portfolio_accounts=[],
        tracked_accounts=tracked_accounts,
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
    )

    assert len(summaries) == 1
    assert summaries[0].label == "Main Checking"
    assert summaries[0].tracked_account_id == "tracked-1"
    assert summaries[0].account_origin == "tracked"
    assert summaries[0].match_status == "linked"


def test_build_account_summaries_links_prefixed_evidence_to_tracked_account_by_account_name() -> None:
    documents = [
        HouseholdDocument(
            id="doc-ira",
            filename="positions.csv",
            source_type="retirement",
            document_type="retirement_statement",
            status="parsed",
            account_label="Fidelity positions export (2 accounts)",
            file_size_bytes=10,
            content_type="text/csv",
            classification_confidence=0.95,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.95,
            statement_start=None,
            statement_end=_iso(1),
            uploaded_at=_iso(1),
            parsed_at=_iso(1),
            metadata={"file_available": True, "application_summary": {"status": "applied"}},
        )
    ]
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-ira",
                document_id="doc-ira",
                source_type="retirement",
                asset_group="retirement",
                account_type="ira",
                institution_name="Fidelity",
                account_name="Traditional IRA",
                account_mask="245944181",
                owner_name=None,
                currency="USD",
                balance=347053.83,
                holdings_value=345082.73,
                cash_balance=1971.10,
                as_of_date=_iso(1),
                confidence=0.95,
                metadata={},
            )
        ],
        documents=documents,
        portfolio_accounts=[],
        tracked_accounts=[
            HouseholdTrackedAccount(
                id="tracked-ira",
                label="Traditional IRA",
                asset_group="retirement",
                account_type="ira",
                source_type="retirement",
                institution_name="Fidelity",
                owner_name=None,
                account_mask="245944181",
                notes=None,
                created_at=_iso(10),
                updated_at=_iso(1),
            )
        ],
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
    )

    assert len(summaries) == 1
    assert summaries[0].label == "Traditional IRA"
    assert summaries[0].tracked_account_id == "tracked-ira"
    assert summaries[0].match_status == "linked"


def test_build_account_summaries_uses_portfolio_label_for_linked_evidence_accounts() -> None:
    documents = [
        HouseholdDocument(
            id="doc-tod",
            filename="positions.csv",
            source_type="brokerage",
            document_type="brokerage_statement",
            status="parsed",
            account_label="Individual - TOD",
            file_size_bytes=10,
            content_type="text/csv",
            classification_confidence=0.95,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.95,
            statement_start=None,
            statement_end=_iso(1),
            uploaded_at=_iso(1),
            parsed_at=_iso(1),
            metadata={"file_available": True, "application_summary": {"status": "applied"}},
        )
    ]
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-tod",
                document_id="doc-tod",
                source_type="brokerage",
                asset_group="taxable",
                account_type="brokerage",
                institution_name="Fidelity",
                account_name="Individual - TOD",
                account_mask="Z35217544",
                owner_name=None,
                currency="USD",
                balance=507248.61,
                holdings_value=505821.08,
                cash_balance=1427.53,
                as_of_date=_iso(1),
                confidence=0.95,
                metadata={},
            )
        ],
        documents=documents,
        portfolio_accounts=[
            Account(
                id="portfolio-tod",
                name="Individual - TOD",
                account_type="Taxable",
                cash_balance=1427.53,
            )
        ],
        tracked_accounts=[],
        holdings_by_account={"portfolio-tod": 505821.08},
        statement_freshness={"coverage_months": 1, "gap_months": []},
    )

    assert len(summaries) == 1
    assert summaries[0].label == "Individual - TOD"
    assert summaries[0].linked_portfolio_account_id == "portfolio-tod"
    assert summaries[0].linked_portfolio_account_name == "Individual - TOD"
    assert summaries[0].institution_name == "Fidelity"
    assert summaries[0].match_status == "linked"


def test_build_account_summaries_uses_account_mask_to_credit_transaction_only_docs() -> None:
    documents = [
        HouseholdDocument(
            id="doc-balance",
            filename="cash-management-summary.txt",
            source_type="brokerage",
            document_type="brokerage_statement",
            status="parsed",
            account_label="Cash Management (Joint WROS)",
            file_size_bytes=10,
            content_type="text/plain",
            classification_confidence=0.94,
            review_status="complete",
            review_summary="Reviewed",
            review_confidence=0.94,
            statement_start=None,
            statement_end=_iso(2),
            uploaded_at=_iso(1),
            parsed_at=_iso(1),
            metadata={"file_available": True, "application_summary": {"status": "applied"}},
        )
    ]
    summaries = build_account_summaries(
        evidence_accounts=[
            HouseholdEvidenceAccount(
                id="acct-cash-management",
                document_id="doc-balance",
                source_type="brokerage",
                asset_group="taxable",
                account_type="brokerage",
                institution_name=None,
                account_name="Cash Management (Joint WROS)",
                account_mask="Z38367298",
                owner_name=None,
                currency="USD",
                balance=39400.59,
                holdings_value=39400.59,
                cash_balance=33400.59,
                as_of_date=_iso(2),
                confidence=0.95,
                metadata={},
            )
        ],
        documents=documents,
        portfolio_accounts=[],
        tracked_accounts=[],
        holdings_by_account={},
        statement_freshness={"coverage_months": 1, "gap_months": []},
        latest_transaction_dates_by_document={},
        latest_transaction_dates_by_account_label={
            "Z38367298": (datetime.now(UTC) - timedelta(days=4)).date()
        },
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.label == "Cash Management (Joint WROS)"
    assert summary.last_transaction_at is not None
    assert summary.days_since_transaction == 4
    assert summary.transaction_freshness_status == "aging"
    assert not any(gap.code == "missing_transaction_history" for gap in summary.gap_flags)
