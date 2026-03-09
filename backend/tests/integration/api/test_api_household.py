"""Integration tests for Household Finance API endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.portfolio.models import PriceData


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_storage():
    from app.storage import get_storage

    return get_storage()


def test_household_profile_is_created_and_can_be_updated(client: TestClient) -> None:
    response = client.get("/api/household/profile")
    assert response.status_code == 200
    profile = response.json()
    assert profile["household_name"] == "Household"

    update_response = client.post(
        "/api/household/profile",
        json={
            "household_name": "Kasadis Family",
            "monthly_net_income_target": 12500,
            "monthly_essential_target": 5200,
            "monthly_discretionary_target": 1800,
            "monthly_savings_target": 2600,
            "target_retirement_age": 60,
            "target_retirement_spend": 9000,
            "notes": "Prioritize travel flexibility.",
        },
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["household_name"] == "Kasadis Family"
    assert updated["monthly_net_income_target"] == 12500
    assert updated["target_retirement_age"] == 60


def test_household_document_upload_persists_metadata(
    client: TestClient,
    tmp_path: Path,
) -> None:
    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Primary Amex statement with enough history to infer spending lanes.",
                "document_type": "statement",
                "source_type": "credit_card",
                "confidence": 0.91,
                "structured_data": {
                    "merchant": "American Express",
                    "account_hint": "Amex Gold",
                },
                "inferred_values": [
                    {
                        "field_name": "monthly_essential_target",
                        "value": "5100",
                        "confidence": 0.78,
                        "rationale": "Core household bills and groceries appear stable.",
                    }
                ],
                "questions": [
                    {
                        "field_name": "monthly_net_income_target",
                        "question": "Is this your primary household card for recurring expenses?",
                        "priority": "high",
                        "rationale": "Jenny needs to know whether this spend stream is representative.",
                    }
                ],
            },
        ),
    ):
        response = client.post(
            "/api/household/documents",
            files={"file": ("amex_statement_march.pdf", b"fake pdf bytes", "application/pdf")},
            data={"account_label": "Amex Gold"},
        )

    assert response.status_code == 200
    document = response.json()
    assert document["filename"] == "amex_statement_march.pdf"
    assert document["source_type"] == "credit_card"
    assert document["document_type"] == "statement"
    assert document["status"] == "staged"
    assert document["account_label"] == "Amex Gold"
    assert document["review_status"] is None
    assert document["metadata"]["stored_path"].endswith(".pdf")

    documents_response = client.get("/api/household/documents")
    assert documents_response.status_code == 200
    reviewed_document = documents_response.json()["items"][0]
    assert reviewed_document["source_type"] == "credit_card"
    assert reviewed_document["document_type"] == "statement"
    assert reviewed_document["account_label"] == "Amex Gold"
    assert reviewed_document["review_status"] == "complete"


def test_household_dashboard_uses_profile_documents_and_portfolio(
    client: TestClient,
    test_storage,
) -> None:
    client.post(
        "/api/household/profile",
        json={
            "household_name": "Kasadis Family",
            "monthly_net_income_target": 12500,
            "monthly_essential_target": 5200,
            "monthly_discretionary_target": 1800,
            "monthly_savings_target": 2600,
            "target_retirement_age": 60,
            "target_retirement_spend": 9000,
        },
    )

    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO symbols (symbol, company_name)
            VALUES ('VTI', 'Vanguard Total Stock Market ETF'),
                   ('VXUS', 'Vanguard Total International Stock ETF')
            ON CONFLICT (symbol) DO NOTHING
            """
        )
        conn.execute(
            """
            INSERT INTO portfolio_accounts (
                id, name, account_type, cash_balance, initial_cash, created_at, updated_at
            ) VALUES
                ('11111111-1111-1111-1111-111111111111', 'Joint Taxable', 'Taxable', 12000, 12000, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('22222222-2222-2222-2222-222222222222', 'Roth IRA', 'Roth', 3500, 3500, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.execute(
            """
            INSERT INTO portfolio_positions (
                id, account_id, symbol, shares, cost_basis, position_type, created_at, updated_at
            ) VALUES
                ('33333333-3333-3333-3333-333333333333', '11111111-1111-1111-1111-111111111111', 'VTI', 10, 240, 'long', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                ('44444444-4444-4444-4444-444444444444', '22222222-2222-2222-2222-222222222222', 'VXUS', 20, 55, 'long', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )
        conn.commit()

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=Path("/tmp/household-test-uploads"),
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Checking statement covering recurring deposits and baseline spending.",
                "document_type": "statement",
                "source_type": "bank",
                "confidence": 0.89,
                "structured_data": {"account_hint": "Joint Checking"},
                "inferred_values": [
                    {
                        "field_name": "monthly_net_income_target",
                        "value": "12500",
                        "confidence": 0.82,
                        "rationale": "Recurring deposits suggest household take-home income.",
                    }
                ],
                "questions": [],
            },
        ),
        patch(
            "app.services.household_finance_service.PriceDataFetcher.fetch_price_data",
            return_value={
                "VTI": PriceData(symbol="VTI", price=275),
                "VXUS": PriceData(symbol="VXUS", price=62),
            },
        ),
    ):
        client.post(
            "/api/household/documents",
            files={"file": ("checking_statement.pdf", b"bank bytes", "application/pdf")},
        )
        response = client.get("/api/household/dashboard")

    assert response.status_code == 200
    dashboard = response.json()
    assert dashboard["profile"]["household_name"] == "Kasadis Family"
    assert dashboard["overview"]["invested_assets"] == 3990
    assert dashboard["overview"]["cash_reserve"] == 15500
    assert dashboard["overview"]["retirement_assets"] == 4740
    assert dashboard["overview"]["taxable_assets"] == 14750
    assert dashboard["overview"]["visibility_score"] >= 90
    assert dashboard["budget_readiness"]["status"] == "ready_for_budgeting"
    assert dashboard["retirement_preparedness"]["status"] == "scenario_ready"
    assert dashboard["import_center"]["tracked_documents"] == 1


def test_household_questions_can_be_answered_and_confirm_profile_value(
    client: TestClient,
    tmp_path: Path,
) -> None:
    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Retirement statement with ambiguous target assumptions.",
                "document_type": "retirement_statement",
                "source_type": "retirement",
                "confidence": 0.88,
                "structured_data": {"account_hint": "Roth IRA"},
                "inferred_values": [],
                "questions": [
                    {
                        "field_name": "target_retirement_age",
                        "question": "What age do you want to retire?",
                        "priority": "high",
                        "recommendation": "Use age 60 unless you expect to work materially longer.",
                        "rationale": "Jenny needs a target age to anchor retirement scenarios.",
                    }
                ],
            },
        ),
    ):
        upload_response = client.post(
            "/api/household/documents",
            files={"file": ("roth_statement.pdf", b"retirement bytes", "application/pdf")},
        )

    assert upload_response.status_code == 200

    questions_response = client.get("/api/household/questions")
    assert questions_response.status_code == 200
    questions = questions_response.json()["items"]
    assert len(questions) == 1
    assert questions[0]["field_name"] == "target_retirement_age"
    assert questions[0]["recommendation"] == "Use age 60 unless you expect to work materially longer."
    assert questions[0]["metadata"]["source_document"]["filename"] == "roth_statement.pdf"

    answer_response = client.post(
        f"/api/household/questions/{questions[0]['id']}/answer",
        json={"answer_text": "Age 60"},
    )
    assert answer_response.status_code == 200
    answered = answer_response.json()
    assert answered["status"] == "answered"
    assert answered["answer_text"] == "Age 60"

    profile_response = client.get("/api/household/profile")
    assert profile_response.status_code == 200
    profile = profile_response.json()
    assert profile["target_retirement_age"] == 60

    dashboard_response = client.get("/api/household/dashboard")
    assert dashboard_response.status_code == 200
    dashboard = dashboard_response.json()
    retirement_value = next(
        item
        for item in dashboard["resolved_values"]
        if item["field_name"] == "target_retirement_age"
    )
    assert retirement_value["status"] == "confirmed"
    assert retirement_value["source"] == "manual"


def test_household_answering_question_closes_matching_sibling_questions(
    client: TestClient,
    tmp_path: Path,
) -> None:
    review_payload = {
        "summary": "Checking statement covering recurring deposits and baseline spending.",
        "document_type": "statement",
        "source_type": "bank",
        "confidence": 0.89,
        "structured_data": {"account_hint": "Wells Fargo Everyday Checking"},
        "inferred_values": [],
        "questions": [
            {
                "field_name": "monthly_essential_target",
                "question": "Is Wells Fargo Everyday Checking your primary account for monthly bills, deposits, and budget tracking?",
                "priority": "high",
                "recommendation": "Answer 'yes' if most paycheck deposits, bill payments, and core household cash flow pass through this account.",
                "rationale": "Primary checking accounts anchor the household cash-flow model.",
            }
        ],
    }

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review_payload,
        ),
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("022726 WellsFargo.pdf", b"bank bytes 1", "application/pdf")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("012726 WellsFargo.pdf", b"bank bytes 2", "application/pdf")},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    questions_response = client.get("/api/household/questions")
    questions = questions_response.json()["items"]
    assert len(questions) == 2

    answer_response = client.post(
        f"/api/household/questions/{questions[0]['id']}/answer",
        json={"answer_text": "yes"},
    )
    assert answer_response.status_code == 200

    refreshed_questions = client.get("/api/household/questions").json()["items"]
    assert refreshed_questions == []


def test_household_answer_reconciles_related_open_questions_with_different_wording(
    client: TestClient,
    tmp_path: Path,
) -> None:
    first_review_payload = {
        "summary": "Checking statement covering recurring deposits and baseline spending.",
        "document_type": "statement",
        "source_type": "bank",
        "confidence": 0.89,
        "structured_data": {"account_hint": "Wells Fargo Everyday Checking"},
        "inferred_values": [],
        "questions": [
            {
                "field_name": "monthly_essential_target",
                "question": "Is Wells Fargo Everyday Checking your primary account for monthly bills, deposits, and budget tracking?",
                "priority": "high",
                "recommendation": "Answer 'yes' if most paycheck deposits, bill payments, and core household cash flow pass through this account.",
                "rationale": "Primary checking accounts anchor the household cash-flow model.",
            }
        ],
    }
    second_review_payload = {
        "summary": "Checking account with cash-flow activity.",
        "document_type": "statement",
        "source_type": "bank",
        "confidence": 0.87,
        "structured_data": {"account_hint": "Wells Fargo Everyday Checking"},
        "inferred_values": [],
        "questions": [
            {
                "field_name": "monthly_essential_target",
                "question": "Is this account part of your core monthly household spending?",
                "priority": "high",
                "recommendation": "Confirm if this account covers regular household bills, groceries, or everyday spending.",
                "rationale": "This determines whether Jenny should treat the spend as budget-driving data.",
            }
        ],
    }

    with patch(
        "app.services.household_finance_service.HouseholdFinanceService._upload_root",
        return_value=tmp_path,
    ), patch(
        "app.services.household_document_review.HouseholdDocumentReviewService.review",
        side_effect=[first_review_payload, second_review_payload],
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("022726 WellsFargo.pdf", b"bank bytes 1", "application/pdf")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("012726 WellsFargo.pdf", b"bank bytes 2", "application/pdf")},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    questions = client.get("/api/household/questions").json()["items"]
    assert len(questions) == 2

    answer_response = client.post(
        f"/api/household/questions/{questions[0]['id']}/answer",
        json={
            "answer_text": "yes, this is one of our main household checking accounts and it covers regular bills and cash flow",
        },
    )
    assert answer_response.status_code == 200

    refreshed_questions = client.get("/api/household/questions").json()["items"]
    assert refreshed_questions == []


def test_household_list_questions_reconciles_stale_open_duplicates(
    client: TestClient,
    tmp_path: Path,
    test_storage,
) -> None:
    review_payload = {
        "summary": "Checking statement covering recurring deposits and baseline spending.",
        "document_type": "statement",
        "source_type": "bank",
        "confidence": 0.89,
        "structured_data": {"account_hint": "Wells Fargo Everyday Checking"},
        "inferred_values": [],
        "questions": [
            {
                "field_name": "monthly_essential_target",
                "question": "Is Wells Fargo Everyday Checking your primary account for monthly bills, deposits, and budget tracking?",
                "priority": "high",
                "recommendation": "Answer 'yes' if most paycheck deposits, bill payments, and core household cash flow pass through this account.",
                "rationale": "Primary checking accounts anchor the household cash-flow model.",
            }
        ],
    }

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review_payload,
        ),
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("022726 WellsFargo.pdf", b"bank bytes 1", "application/pdf")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("012726 WellsFargo.pdf", b"bank bytes 2", "application/pdf")},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    questions = client.get("/api/household/questions").json()["items"]
    assert len(questions) == 2

    answer_response = client.post(
        f"/api/household/questions/{questions[0]['id']}/answer",
        json={"answer_text": "yes"},
    )
    assert answer_response.status_code == 200

    sibling_id = questions[1]["id"]
    with test_storage.connection() as conn:
        conn.execute(
            """
            UPDATE household_questions
            SET status = 'open',
                answer_text = NULL,
                answered_at = NULL,
                metadata = '{}'::jsonb
            WHERE id = %s
            """,
            [sibling_id],
        )
        conn.commit()

    refreshed_questions = client.get("/api/household/questions").json()["items"]
    assert refreshed_questions == []


def test_household_document_duplicate_upload_returns_existing_document(
    client: TestClient,
    tmp_path: Path,
) -> None:
    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Checking statement covering recurring deposits and baseline spending.",
                "document_type": "statement",
                "source_type": "bank",
                "confidence": 0.89,
                "structured_data": {"account_hint": "Joint Checking"},
                "inferred_values": [],
                "questions": [],
            },
        ) as review_mock,
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("checking_statement.pdf", b"same-bytes", "application/pdf")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("checking_statement.pdf", b"same-bytes", "application/pdf")},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    first_document = first.json()
    second_document = second.json()
    assert second_document["id"] == first_document["id"]
    assert second_document["metadata"]["duplicate_detected"] is True
    assert review_mock.call_count == 1

    documents_response = client.get("/api/household/documents")
    assert documents_response.status_code == 200
    assert len(documents_response.json()["items"]) == 1


def test_household_order_history_reupload_dedupes_import_rows(
    client: TestClient,
    tmp_path: Path,
    test_storage,
) -> None:
    review_payload = {
        "summary": "Amazon order history export.",
        "document_type": "receipt",
        "source_type": "receipt",
        "confidence": 0.93,
        "structured_data": {
            "merchant": "Amazon",
            "account_hint": "Amazon account",
        },
        "inferred_values": [],
        "questions": [],
        "extracted_text": (
            "ASIN,Order Date,Order ID,Payment Instrument Type,Original Quantity,Shipping Charge,Total Amount,Unit Price\n"
            "B001,2026-03-01T00:00:00Z,111-1111111-1111111,VISA,1,0,10.00,10.00"
        ),
    }

    first_csv = (
        "ASIN,Order Date,Order ID,Payment Instrument Type,Original Quantity,Currency,Shipping Charge,Total Amount,Unit Price\n"
        "B001,2026-03-01T00:00:00Z,111-1111111-1111111,VISA,1,USD,0,10.00,10.00\n"
        "B002,2026-03-02T00:00:00Z,222-2222222-2222222,VISA,1,USD,1.50,25.50,24.00\n"
    )
    second_csv = (
        "ASIN,Order Date,Order ID,Payment Instrument Type,Original Quantity,Currency,Shipping Charge,Total Amount,Unit Price\n"
        "B001,2026-03-01T00:00:00Z,111-1111111-1111111,VISA,1,USD,0,10.00,10.00\n"
        "B002,2026-03-02T00:00:00Z,222-2222222-2222222,VISA,1,USD,1.50,25.50,24.00\n"
        "B003,2026-03-03T00:00:00Z,333-3333333-3333333,VISA,2,USD,0,30.00,15.00\n"
    )

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review_payload,
        ),
        patch(
            "app.services.household_review_agent_service.HouseholdReviewAgentService.save_learning",
            return_value="memory-1",
        ),
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("Order History.csv", first_csv.encode("utf-8"), "text/csv")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("Order History.csv", second_csv.encode("utf-8"), "text/csv")},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    with test_storage.connection() as conn:
        import_rows = conn.execute("SELECT COUNT(*) FROM household_import_rows").fetchone()[0]
        signatures = conn.execute("SELECT COUNT(*) FROM household_document_signatures").fetchone()[0]
        imported_amount = conn.execute(
            """
            SELECT amount
            FROM household_import_rows
            WHERE external_row_id = '222-2222222-2222222'
            """
        ).fetchone()[0]

    assert import_rows == 3
    assert signatures >= 1
    assert float(imported_amount) == 25.50


def test_household_order_history_reupload_backfills_amounts(
    client: TestClient,
    tmp_path: Path,
    test_storage,
) -> None:
    review_payload = {
        "summary": "Amazon order history export with pricing.",
        "document_type": "receipt",
        "source_type": "receipt",
        "confidence": 0.93,
        "structured_data": {
            "merchant": "Amazon",
            "account_hint": "Amazon account",
        },
        "inferred_values": [],
        "questions": [],
        "extracted_text": (
            "ASIN,Order Date,Order ID,Original Quantity,Shipping Charge,Total Amount,Unit Price\n"
            "B001,2026-03-01T00:00:00Z,111-1111111-1111111,1,0,10.00,10.00"
        ),
    }

    first_csv = (
        "ASIN,Order Date,Order ID,Original Quantity,Currency\n"
        "B001,2026-03-01T00:00:00Z,111-1111111-1111111,1,USD\n"
    )
    second_csv = (
        "ASIN,Order Date,Order ID,Original Quantity,Currency,Shipping Charge,Total Amount,Unit Price\n"
        "B001,2026-03-01T00:00:00Z,111-1111111-1111111,1,USD,0,10.00,10.00\n"
    )

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review_payload,
        ),
        patch(
            "app.services.household_review_agent_service.HouseholdReviewAgentService.save_learning",
            return_value="memory-1",
        ),
    ):
        first = client.post(
            "/api/household/documents",
            files={"file": ("Order History.csv", first_csv.encode("utf-8"), "text/csv")},
        )
        second = client.post(
            "/api/household/documents",
            files={"file": ("Order History.csv", second_csv.encode("utf-8"), "text/csv")},
        )

    assert first.status_code == 200
    assert second.status_code == 200

    with test_storage.connection() as conn:
        imported_amount = conn.execute(
            """
            SELECT amount
            FROM household_import_rows
            WHERE external_row_id = '111-1111111-1111111'
            """
        ).fetchone()[0]

    assert float(imported_amount) == 10.00
