"""Unit tests for evidence-account normalization and fallback behavior."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.models.household_finance import HouseholdEvidenceAccount
from app.services.household_evidence_service import HouseholdEvidenceService
from app.services.household_review_agent_service import HOUSEHOLD_REVIEW_AGENT_SLUG


class _Result:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Conn:
    def __init__(
        self,
        *,
        existing_rows: list[tuple[object, ...]] | None = None,
        valid_account_ids: list[str] | None = None,
    ) -> None:
        self._existing_rows = existing_rows or []
        self._valid_account_ids = valid_account_ids or []
        self.inserts: list[list[object]] = []
        self.deleted = False

    def execute(self, query: str, params: list[object] | None = None) -> _Result:
        params = params or []
        if query.startswith("SELECT id, document_id, household_account_id, source_type"):
            return _Result(self._existing_rows)
        if query.startswith("SELECT id FROM household_accounts"):
            return _Result([(account_id,) for account_id in self._valid_account_ids])
        if query.startswith("DELETE FROM household_evidence_accounts"):
            self.deleted = True
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


def _evidence_row(
    *,
    id: str,
    document_id: str,
    household_account_id: str | None,
    source_type: str,
    asset_group: str,
    account_type: str,
    institution_name: str | None,
    account_name: str | None,
    account_mask: str | None,
    owner_name: str | None,
    currency: str = "USD",
    balance: float | None = None,
    holdings_value: float | None = None,
    cash_balance: float | None = None,
    as_of_date: str | None = None,
    metadata: dict[str, object] | None = None,
    confidence: float | None = None,
) -> tuple[object, ...]:
    return (
        id,
        document_id,
        household_account_id,
        source_type,
        asset_group,
        account_type,
        institution_name,
        account_name,
        account_mask,
        owner_name,
        currency,
        balance,
        holdings_value,
        cash_balance,
        as_of_date,
        metadata or {},
        confidence,
    )


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
                        "owner_name": "Alex Demo",
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
    assert metadata["assigned_review_agent_slug"] == HOUSEHOLD_REVIEW_AGENT_SLUG
    assert metadata["review_strategy"] == "unknown"
    assert metadata["review_agent_applied"] is False


def test_replace_document_accounts_preserves_existing_household_account_link() -> None:
    service = HouseholdEvidenceService()
    conn = _Conn(
        existing_rows=[
            _evidence_row(
                id="existing-frs",
                document_id="doc-frs",
                household_account_id="household-frs-jordan-demo",
                source_type="retirement",
                asset_group="retirement",
                account_type="retirement",
                institution_name="Florida Retirement System (FRS)",
                account_name="FRS Investment Plan",
                account_mask=None,
                owner_name="Jordan Demo",
                balance=131002.45,
                holdings_value=131002.45,
                as_of_date="2026-04-10T00:00:00",
                metadata={"match_key": "frs|jordan-demo|investment-plan"},
                confidence=0.98,
            )
        ],
        valid_account_ids=["household-frs-jordan-demo"],
    )
    fake_service = SimpleNamespace(storage=_Storage(conn))

    count = service.replace_document_accounts(
        fake_service,
        document=SimpleNamespace(
            id="doc-frs",
            source_type="retirement",
            document_type="statement",
            account_label="FRS",
            statement_end=None,
            parsed_at="2026-04-14T00:00:00Z",
        ),
        reviewed={
            "source_type": "retirement",
            "confidence": 0.97,
            "_review_strategy": "agent",
            "structured_data": {
                "provider_name": "Florida Retirement System (FRS)",
                "financial_accounts": [
                    {
                        "account_name": "FRS Investment Plan",
                        "account_type": "retirement",
                        "asset_group": "retirement",
                        "institution_name": "Florida Retirement System (FRS)",
                        "owner_name": "Jordan Demo",
                        "balance": "131002.45",
                        "holdings_value": "131002.45",
                        "match_key": "frs|jordan-demo|investment-plan",
                    }
                ],
            },
        },
    )

    assert count == 1
    assert conn.deleted is True
    assert len(conn.inserts) == 1
    insert_params = conn.inserts[0]
    assert insert_params[2] == "household-frs-jordan-demo"
    metadata = json.loads(insert_params[16])
    assert metadata["preserved_household_account_id"] == "household-frs-jordan-demo"
    assert metadata["preserved_from_existing_evidence"] is True
    assert metadata["assigned_review_agent_slug"] == HOUSEHOLD_REVIEW_AGENT_SLUG
    assert metadata["review_strategy"] == "agent"
    assert metadata["review_agent_applied"] is True


def test_replace_document_accounts_dedupes_duplicate_review_accounts() -> None:
    service = HouseholdEvidenceService()
    conn = _Conn()
    fake_service = SimpleNamespace(storage=_Storage(conn))

    count = service.replace_document_accounts(
        fake_service,
        document=SimpleNamespace(
            id="doc-dup",
            source_type="retirement",
            document_type="statement",
            account_label="Pinellas County Schools 403(b) Plan",
            statement_end=None,
            parsed_at="2026-04-14T00:00:00Z",
        ),
        reviewed={
            "source_type": "retirement",
            "confidence": 0.95,
            "_review_strategy": "agent",
            "structured_data": {
                "provider_name": "Pinellas County Schools",
                "financial_accounts": [
                    {
                        "account_name": "Pinellas County Schools 403(b) Plan",
                        "account_type": "401k",
                        "asset_group": "retirement",
                        "institution_name": "Pinellas County Schools",
                        "owner_name": "Jordan Demo",
                        "balance": "130087.12",
                        "holdings_value": "130087.12",
                        "match_key": "pcs|403b|jordan-demo",
                    },
                    {
                        "account_name": "Pinellas County Schools 403(b) Plan",
                        "account_type": "401k",
                        "asset_group": "retirement",
                        "institution_name": "Pinellas County Schools",
                        "owner_name": "Jordan Demo",
                        "match_key": "pcs|403b|jordan-demo",
                    },
                ],
            },
        },
    )

    assert count == 1
    assert conn.deleted is True
    assert len(conn.inserts) == 1
    insert_params = conn.inserts[0]
    assert insert_params[11] == 130087.12


def test_replace_document_accounts_keeps_existing_rows_when_new_review_is_empty() -> None:
    service = HouseholdEvidenceService()
    conn = _Conn(
        existing_rows=[
            _evidence_row(
                id="existing-403b",
                document_id="doc-403b",
                household_account_id="household-403b-jordan-demo",
                source_type="retirement",
                asset_group="retirement",
                account_type="401k",
                institution_name="Pinellas County Schools",
                account_name="Pinellas County Schools 403(b) Plan",
                account_mask=None,
                owner_name="Jordan Demo",
                balance=130087.12,
                holdings_value=130087.12,
                as_of_date="2026-04-10T00:00:00",
                metadata={"match_key": "pcs|403b|jordan-demo"},
                confidence=0.98,
            )
        ]
    )
    fake_service = SimpleNamespace(storage=_Storage(conn))

    count = service.replace_document_accounts(
        fake_service,
        document=SimpleNamespace(
            id="doc-403b",
            source_type="retirement",
            document_type="statement",
            account_label="Pinellas County Schools 403(b) Plan",
            statement_end=None,
            parsed_at="2026-04-14T00:00:00Z",
        ),
        reviewed={
            "source_type": "retirement",
            "confidence": 0.4,
            "_review_strategy": "baseline",
            "structured_data": {},
        },
    )

    assert count == 1
    assert conn.deleted is False
    assert conn.inserts == []


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
                        "owner_name": "Alex Demo",
                        "account_mask": "9728",
                        "match_key": "credit-lineage|chase|prime visa|alex demo|credit_card",
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
    assert metadata["match_key"] == "credit-lineage|chase|prime visa|alex demo|credit_card"


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
                        "owner_name": "Alex Demo",
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
