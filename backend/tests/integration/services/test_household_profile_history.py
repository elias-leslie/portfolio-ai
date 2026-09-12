from typing import cast

import pytest
from psycopg.errors import NotNullViolation

from app.models.household_finance import HouseholdProfileUpdate
from app.services.household_finance_service import HouseholdFinanceService


def test_exact_profile_changes_are_atomic_and_noop_does_not_add_history(monkeypatch):
    service = HouseholdFinanceService()
    monkeypatch.setattr(service.planning_service, "refresh_document_requirements", lambda *_: None)
    before = service.get_profile()
    service.update_profile(HouseholdProfileUpdate(target_retirement_age=62), source="jenny_chat")
    service.update_profile(HouseholdProfileUpdate(target_retirement_age=62), source="jenny_chat")
    with service.storage.connection() as conn:
        rows = conn.execute(
            "SELECT source, changes FROM household_profile_changes WHERE profile_id=%s", [before.id]
        ).fetchall()
    assert len(rows) == 1 and rows[0][0] == "jenny_chat"
    assert rows[0][1] == [
        {"field": "target_retirement_age", "before": before.target_retirement_age, "after": 62}
    ]

    # A failed audit insert cannot leave a successful but unrecorded profile write.
    with pytest.raises(NotNullViolation):
        service.update_profile(
            HouseholdProfileUpdate(target_retirement_age=63), source=cast(str, None)
        )
    assert service.get_profile().target_retirement_age == 62
