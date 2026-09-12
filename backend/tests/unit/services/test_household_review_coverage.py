from contextlib import contextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.services import household_review_coverage
from app.services.household_review_coverage import review_coverage


@pytest.fixture(autouse=True)
def no_synced_accounts(monkeypatch):
    monkeypatch.setattr(household_review_coverage, "synced_activity_coverage", lambda _storage: {})


class Storage:
    def __init__(self, rows):
        self.rows = rows

    @contextmanager
    def connection(self):
        yield SimpleNamespace(execute=lambda *_args: SimpleNamespace(fetchall=lambda: self.rows))


def test_late_spending_feed_prevents_a_complete_review():
    storage = Storage([
        ("Everyday card", "credit", "credit_card", {}, "active", date(2026, 9, 1)),
        ("Retirement", "retirement", "ira", {}, "active", date(2026, 7, 1)),
    ])
    result = review_coverage(storage, end_date=date(2026, 9, 11))
    assert result["coverage_status"] == "incomplete"
    assert "Everyday card" in result["coverage_detail"]
    assert "Retirement" not in result["coverage_detail"]


def test_closed_feed_does_not_block_and_future_activity_is_not_future_coverage():
    storage = Storage([
        ("Everyday card", "credit", "credit_card", {}, "active", date(2026, 9, 11)),
        ("Old card", "credit", "credit_card", {}, "closed", None),
    ])
    result = review_coverage(storage, end_date=date(2026, 8, 31))
    assert result["coverage_status"] == "current"
    assert result["coverage_through"] == "2026-08-31"


def test_missing_coverage_is_not_a_zero_spending_success():
    storage = Storage([("Everyday card", "credit", "credit_card", {}, "active", None)])
    assert review_coverage(storage, end_date=date(2026, 9, 11))["coverage_status"] == "incomplete"
    assert review_coverage(Storage([]), end_date=date(2026, 9, 11))["coverage_status"] == "unknown"


def test_completed_empty_sync_covers_a_quiet_bank_account(monkeypatch):
    monkeypatch.setattr(household_review_coverage, "synced_activity_coverage",
        lambda _storage: {"bank": datetime(2026, 9, 11, tzinfo=UTC)})
    storage = Storage([("Checking", "cash", "checking", {}, "active", None, "bank")])
    result = review_coverage(storage, end_date=date(2026, 9, 11))
    assert result["coverage_status"] == "current"
    assert result["coverage_through"] == "2026-09-11"
