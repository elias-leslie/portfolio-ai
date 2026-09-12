from datetime import date

import pytest
from tests.runtime_seed import main, seed_review_history

from app.services.household_transaction_service import HouseholdTransactionService


def test_runtime_fixture_has_two_reconcilable_months_and_is_idempotent():
    service = HouseholdTransactionService()
    with service.storage.connection() as conn:
        seed_review_history(conn, date(2026, 9, 11))
        seed_review_history(conn, date(2026, 9, 11))
        conn.commit()
    for month in ["2026-08", "2026-09"]:
        view = service.build_spending_view(month=month)
        assert view.summary.total_spend == 200
        assert sum(row.total_spend for row in view.categories) == 200
        assert len(view.categories) == 2


def test_runtime_seeder_refuses_an_ordinary_environment(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(RuntimeError, match="GitHub Actions"):
        main()
