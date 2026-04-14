"""Unit tests for evidence-account normalization and fallback behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.models.household_finance import HouseholdEvidenceAccount
from app.services.household_evidence_service import HouseholdEvidenceService


def test_normalize_accounts_uses_structured_financial_accounts() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="brokerage",
            account_label="Main brokerage",
        ),
        reviewed={
            "source_type": "brokerage",
            "confidence": 0.96,
            "structured_data": {
                "provider_name": "Fidelity",
                "financial_accounts": [
                    {
                        "asset_group": "taxable",
                        "account_type": "brokerage",
                        "account_mask": "1234",
                        "holdings_value": "10000.25",
                        "cash_balance": "499.75",
                        "as_of_date": "2026-03-09",
                    }
                ],
            },
        },
    )

    assert len(accounts) == 1
    assert accounts[0]["institution_name"] == "Fidelity"
    assert accounts[0]["account_mask"] == "1234"
    assert accounts[0]["balance"] == 10500.0
    assert accounts[0]["holdings_value"] == 10000.25
    assert accounts[0]["cash_balance"] == 499.75


def test_replace_document_accounts_drops_stale_household_account_ids() -> None:
    service = HouseholdEvidenceService()

    class _Result:
        def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
            self._rows = rows or []

        def fetchall(self) -> list[tuple[object, ...]]:
            return self._rows

    class _Conn:
        def __init__(self) -> None:
            self.inserts: list[list[object]] = []

        def execute(self, query: str, params: list[object] | None = None) -> _Result:
            params = params or []
            if query.startswith("SELECT id FROM household_accounts"):
                return _Result([])
            if query.startswith("DELETE FROM household_evidence_accounts"):
                return _Result([])
            if "INSERT INTO household_evidence_accounts" in query:
                self.inserts.append(params)
                return _Result([])
            raise AssertionError(query)

        def commit(self) -> None:
            return None

    class _Storage:
        def __init__(self, conn: _Conn) -> None:
            self._conn = conn

        def connection(self) -> object:
            conn = self._conn

            class _Ctx:
                def __enter__(self) -> _Conn:
                    return conn

                def __exit__(self, exc_type, exc, tb) -> bool:
                    return False

            return _Ctx()

    conn = _Conn()
    fake_service = SimpleNamespace(storage=_Storage(conn))

    count = service.replace_document_accounts(
        fake_service,
        document=SimpleNamespace(
            id="doc-1",
            source_type="credit_card",
            document_type="statement",
            account_label="Amazon Chase (CC)",
            statement_end=None,
            parsed_at="2026-04-14T00:00:00Z",
        ),
        reviewed={
            "source_type": "credit_card",
            "confidence": 0.96,
            "structured_data": {
                "provider_name": "Chase",
                "total_amount": "2958.17",
                "financial_accounts": [
                    {
                        "household_account_id": "missing-household-account",
                        "account_name": "Chase Prime Visa / Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "9728",
                    }
                ],
            },
        },
    )

    assert count == 1
    assert conn.inserts
    insert_params = conn.inserts[0]
    assert insert_params[2] is None
    metadata = json.loads(insert_params[16])
    assert metadata["stale_household_account_id"] == "missing-household-account"


def test_normalize_accounts_preserves_reconciled_household_account_and_root_total() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="credit_card",
            account_label="Amazon Chase (CC)",
            statement_end=None,
        ),
        reviewed={
            "source_type": "credit_card",
            "confidence": 0.96,
            "structured_data": {
                "provider_name": "Chase",
                "total_amount": "2958.17",
                "statement_period": "2026-03-12 to 2026-04-11",
                "financial_accounts": [
                    {
                        "household_account_id": "household-chase",
                        "account_name": "Chase Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "9728",
                        "match_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    }
                ],
            },
        },
    )

    assert len(accounts) == 1
    assert accounts[0]["household_account_id"] == "household-chase"
    assert accounts[0]["balance"] == 2958.17
    assert accounts[0]["as_of_date"] == "2026-04-11T00:00:00"
    metadata = accounts[0]["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["match_key"] == "credit-lineage|chase|prime visa|elias b leslie|credit_card"


def test_normalize_accounts_uses_filename_date_when_statement_date_missing() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="credit_card",
            account_label="Amazon Chase (CC)",
            filename="20260411-statements-9728-.pdf",
            statement_end=None,
        ),
        reviewed={
            "source_type": "credit_card",
            "confidence": 0.96,
            "structured_data": {
                "provider_name": "Chase",
                "total_amount": "2958.17",
                "financial_accounts": [
                    {
                        "account_name": "Chase Prime Visa / Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "9728",
                    }
                ],
            },
        },
    )

    assert len(accounts) == 1
    assert accounts[0]["balance"] == 2958.17
    assert accounts[0]["as_of_date"] == "2026-04-11T00:00:00"


def test_normalize_accounts_falls_back_to_legacy_retirement_snapshot() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="retirement",
            account_label="Rollover IRA",
        ),
        reviewed={
            "source_type": "retirement",
            "confidence": 0.95,
            "structured_data": {
                "account_hint": "Rollover IRA",
                "total_amount": "8230.59",
                "statement_period": "As of 2026-03-09",
            },
        },
    )

    assert len(accounts) == 1
    assert accounts[0]["asset_group"] == "retirement"
    assert accounts[0]["account_type"] == "retirement"
    assert accounts[0]["balance"] == 8230.59
    assert accounts[0]["as_of_date"] == "2026-03-09T00:00:00"


def test_normalize_accounts_routes_529_snapshots_to_education() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="brokerage",
            account_label="529 college savings account",
        ),
        reviewed={
            "source_type": "brokerage",
            "confidence": 0.9,
            "structured_data": {
                "account_hint": "529 college savings account",
                "total_amount": "3087.29",
            },
        },
    )

    assert len(accounts) == 1
    assert accounts[0]["asset_group"] == "education"
    assert accounts[0]["account_type"] == "529"
    assert accounts[0]["balance"] == 3087.29


def test_normalize_accounts_refuses_bank_snapshot_without_real_balance() -> None:
    service = HouseholdEvidenceService()

    accounts = service._normalize_accounts(
        document=SimpleNamespace(
            source_type="bank",
            account_label="Checking",
        ),
        reviewed={
            "source_type": "bank",
            "confidence": 0.88,
            "structured_data": {
                "account_hint": "Checking",
            },
        },
    )

    assert accounts == []


def test_dedupe_accounts_keeps_latest_identity_only() -> None:
    service = HouseholdEvidenceService()

    accounts = service._dedupe_accounts(
        [
            HouseholdEvidenceAccount(
                id="a-1",
                document_id="doc-new",
                source_type="credit_card",
                asset_group="credit",
                account_type="credit_card",
                institution_name="Chase",
                account_name="Amazon card",
                account_mask="5313",
                owner_name=None,
                currency="USD",
                balance=5192.03,
                holdings_value=None,
                cash_balance=None,
                as_of_date=None,
                confidence=0.9,
                metadata={},
            ),
            HouseholdEvidenceAccount(
                id="a-2",
                document_id="doc-old",
                source_type="credit_card",
                asset_group="credit",
                account_type="credit_card",
                institution_name="Chase",
                account_name="Amazon card",
                account_mask="5313",
                owner_name=None,
                currency="USD",
                balance=3988.72,
                holdings_value=None,
                cash_balance=None,
                as_of_date=None,
                confidence=0.9,
                metadata={},
            ),
        ]
    )

    assert len(accounts) == 1
    assert accounts[0].document_id == "doc-new"
