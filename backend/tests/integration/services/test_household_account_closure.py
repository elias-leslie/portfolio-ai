"""Closing an account must resolve identity without losing transaction history."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from tests.integration.services.test_household_transaction_dedup import (
    _insert_document,
    _insert_txn,
)

from app.services._household_account_status import fetch_closed_household_account_ids
from app.services._household_dashboard_unknown_accounts import detect_unknown_accounts
from app.services.household_account_lifecycle_service import (
    AccountClosureRequest,
    record_account_closed,
)
from app.services.household_finance_service import HouseholdFinanceService
from app.storage import get_storage


def test_closed_candidate_links_aliases_preserves_history_and_is_repeatable(monkeypatch):
    service = HouseholdFinanceService()
    storage = get_storage()
    monkeypatch.setattr(service, "list_documents", lambda **_: SimpleNamespace(items=[]))
    ids = []
    for index, label in enumerate(["Visa Credit ****4635", "Visa credit ending 4635", "Visa ending 4635"]):
        doc = _insert_document(storage, source_type="receipt")
        tid = _insert_txn(storage, account_id=None, document_id=doc, source_system="receipt",
            on=date.today()-timedelta(days=150-index), amount=10+index, raw_merchant="Fixture store")
        with storage.connection() as conn:
            conn.execute("UPDATE household_transactions SET account_label = %s WHERE id = %s", [label, tid])
            conn.commit()
        ids.append(tid)
    request = AccountClosureRequest(kind="discovered", id="unlinked_4635")
    result = record_account_closed(service, request)
    assert record_account_closed(service, request)["account_id"] == result["account_id"]
    service.account_registry_service.sync_registry(service)
    service.account_registry_service.refresh_coverage(service)
    with storage.connection() as conn:
        rows = conn.execute("SELECT household_account_id::text, amount, removed FROM household_transactions WHERE id = ANY(%s) ORDER BY amount", [ids]).fetchall()
        account = conn.execute("SELECT metadata, feed_status, owner_name FROM household_accounts WHERE id = %s", [result["account_id"]]).fetchone()
    assert [str(row[0]) for row in rows] == [result["account_id"]]*3
    assert [float(row[1]) for row in rows] == [10, 11, 12]
    assert not any(row[2] for row in rows)
    assert account is not None
    metadata = account[0]
    assert isinstance(metadata, dict)
    assert metadata["status_confirmed_by"] == "user"
    assert not metadata.get("closed_date")
    assert account[1] == "closed"
    assert account[2] is None
    assert result["account_id"] in fetch_closed_household_account_ids(storage)
    assert not any(a["key"] == "unlinked_4635" for a in detect_unknown_accounts(storage, []))


def test_closure_rejects_stale_candidate_and_future_date_without_creating_accounts():
    service = HouseholdFinanceService()
    with pytest.raises(ValueError, match="changed"):
        record_account_closed(service, AccountClosureRequest(kind="discovered", id="not-a-current-candidate"))
    with pytest.raises(ValueError, match="actual closure date"):
        record_account_closed(service, AccountClosureRequest(kind="registered", id="any", closed_date=date.today()+timedelta(days=1)))
