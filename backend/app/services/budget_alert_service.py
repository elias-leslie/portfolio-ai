"""The month's plan, evaluated and dispatched (plan §7 3.7, D19).

The card kinds live in ``spend_alert_service`` and continue alongside these;
what is new here is the plan itself — whether the month is heading past it,
whether a category has reached a cap the household set, and whether a purchase
turned up that the ledger has no precedent for.

The evaluation reads ``get_spending()`` once and derives everything from that
one payload, so an alert and the screen it links to are reading the same
numbers by construction. ``_household_budget_alerts`` decides what is worth
saying; ``_alert_dispatch`` decides where it goes and whether it has already
been said.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.logging_config import get_logger
from app.services._alert_dispatch import Alert, dispatch_alerts
from app.services._household_budget_alerts import build_budget_alerts
from app.services.household_finance_service import HouseholdFinanceService

logger = get_logger(__name__)

# Stable synthetic routine id for jenny_notifications rows from this service.
BUDGET_ALERT_ROUTINE_ID = "household-budget-alerts"

# Its own namespace: a card marker and a plan marker for the same month must
# never be able to cancel each other out.
_MARKER_PREFIX = "budget_alert_sent"


class BudgetAlertService:
    def evaluate_and_dispatch(self, *, trigger: str) -> list[Alert]:
        # No month argument: the alerts are about the month the household is
        # living in, which is the only one still worth interrupting them over.
        view = HouseholdFinanceService().get_spending()
        alerts = build_budget_alerts(view, today=datetime.now(UTC).date())
        return dispatch_alerts(
            alerts,
            routine_id=BUDGET_ALERT_ROUTINE_ID,
            routine_type="household_budget_alerts",
            marker_prefix=_MARKER_PREFIX,
            trigger=trigger,
            category_prefix="budget_",
        )


def evaluate_and_dispatch(*, trigger: str) -> list[Alert]:
    """Module-level convenience for workflow/task call sites."""
    return BudgetAlertService().evaluate_and_dispatch(trigger=trigger)
