"""The three findings about the month that are worth interrupting someone for (D19).

Everything here is read off the **published spending view** — the same payload
the Budget screen renders. Nothing re-derives spend, re-reads the ledger or
re-decides what a cap is, because an alert that computed its own numbers could
say the month is over plan while the screen it links to says it is not, which is
the exact failure this revamp exists to remove.

Three kinds, in the priority order D19 set:

**Projected over plan.** Month-to-date spend, run to the end of the month,
against what the anchor leaves the categories to divide. Better-price-found is
the fourth kind and waits for Phase 5 unit pricing.

**A category at its cap.** Only *confirmed* caps count. A suggested cap is the
system's guess at what the household already spends, and alerting on one would
interrupt a person to tell them they are spending what they usually spend.

**A purchase with no precedent.** Reuses ``find_one_time_purchases``' test
rather than inventing a second definition of unusual — with one deliberate
substitution, documented at ``_novel_purchase_alerts``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.services._alert_dispatch import Alert
from app.services._household_one_time_purchases import MIN_SHARE_OF_MONTH

# Days of the month that must have elapsed before a projection is worth
# believing. Run the rate from three days and one large grocery run projects to
# a month that never happens; a week of days is a rate, and still leaves three
# weeks in which to act on it.
MIN_DAYS_FOR_PROJECTION = 7

# How far over plan a projection has to reach before it interrupts anyone. The
# same shape the dashboard's own pace verdict uses, so the alert and the card
# on screen cannot disagree about what counts as running hot.
PROJECTION_TOLERANCE_PCT = 0.05
PROJECTION_TOLERANCE_FLOOR = 100.0

# A purchase interrupts near the event or not at all. Without a window the first
# pass after a deploy would push every large purchase of the month at once, and
# the household would learn to swipe the alerts away.
NOVEL_PURCHASE_WINDOW_DAYS = 7

# Caps that break together still arrive one at a time. Any beyond this wait for
# the next pass rather than arriving as a wall of notifications — none is lost,
# because each carries its own once-a-month marker.
MAX_CATEGORY_ALERTS_PER_PASS = 3

# How large a cap has to be, as a share of every cap the household confirmed,
# before reaching it is worth a phone buzzing. Live the household holds a $17.09
# Fitness cap and a $10.68 Entertainment one beside a $1,100 Groceries cap;
# reaching the small ones is arithmetic, not news, and pushing them is how a
# person learns to swipe these away. Measured against the household's own plan
# rather than a dollar figure, so it scales with what they actually run.
MIN_CAP_SHARE_OF_PLAN = 0.02


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def build_budget_alerts(view: Any, *, today: date) -> list[Alert]:
    """Every plan finding the month currently justifies, most urgent first."""
    summary = view.summary
    # A month the household has finished living is a thing to review, not a
    # thing to head off. Alerts are only ever about the month still running.
    if not getattr(summary, "is_month_to_date", False):
        return []

    alerts: list[Alert] = []
    alerts.extend(_projection_alerts(view, today=today))
    alerts.extend(_category_cap_alerts(view))
    alerts.extend(_novel_purchase_alerts(view, today=today))
    return alerts


def _projection_alerts(view: Any, *, today: date) -> list[Alert]:
    summary = view.summary
    plan = getattr(view, "cap_plan", None)
    if plan is None or plan.status != "proposed":
        # No anchor means no plan to exceed. Saying a month is "over" against a
        # total nobody set would be a verdict from an unset input.
        return []
    planned = float(plan.available_for_categories or 0.0)
    days_elapsed = int(summary.days_elapsed or 0)
    days_in_month = int(summary.days_in_month or 0)
    if planned <= 0 or days_elapsed < MIN_DAYS_FOR_PROJECTION or days_in_month <= 0:
        return []

    spent = float(summary.total_spend or 0.0)
    projected = spent / days_elapsed * days_in_month
    overage = projected - planned
    tolerance = max(planned * PROJECTION_TOLERANCE_PCT, PROJECTION_TOLERANCE_FLOOR)
    if overage <= tolerance:
        return []

    days_left = max(days_in_month - days_elapsed, 0)
    month = summary.month
    # Already past the plan with days still to run is a different fact from
    # heading for it, and it earns the stronger interrupt: what is left of the
    # month is spending that has nowhere to come from.
    already_over = spent > planned
    if already_over:
        return [
            Alert(
                kind="month_over_plan",
                severity="critical",
                title=f"{summary.month_label} is already over plan",
                body=(
                    f"{_money(spent)} spent against a {_money(planned)} plan, with "
                    f"{days_left} day{'s' if days_left != 1 else ''} still to go. "
                    f"At this rate the month closes near {_money(projected)}."
                ),
                marker_key=f"month_over_plan:{month}",
            )
        ]
    return [
        Alert(
            kind="month_projected_over_plan",
            severity="warning",
            title=f"{summary.month_label} is heading over plan",
            body=(
                f"{_money(spent)} in {days_elapsed} days projects to "
                f"{_money(projected)} by month end — {_money(overage)} over the "
                f"{_money(planned)} the plan leaves for spending. "
                f"{days_left} day{'s' if days_left != 1 else ''} left to change it."
            ),
            marker_key=f"month_projected_over_plan:{month}",
        )
    ]


def _category_cap_alerts(view: Any) -> list[Alert]:
    """Confirmed caps only, and reaching one counts — D19 said 100%, not 85%."""
    summary = view.summary
    confirmed = [
        category
        for category in getattr(view, "categories", [])
        if category.budget_source == "confirmed"
        and float(category.confirmed_monthly_budget or 0.0) > 0
    ]
    plan_total = sum(
        float(category.confirmed_monthly_budget or 0.0) for category in confirmed
    )
    minimum_cap = plan_total * MIN_CAP_SHARE_OF_PLAN

    breaches: list[tuple[float, Alert]] = []
    for category in confirmed:
        cap = float(category.confirmed_monthly_budget or 0.0)
        spent = float(category.total_spend or 0.0)
        if spent < cap or cap < minimum_cap:
            continue
        over = spent - cap
        days_left = max(
            int(summary.days_in_month or 0) - int(summary.days_elapsed or 0), 0
        )
        detail = (
            f"{_money(spent)} against a {_money(cap)} cap"
            if over <= 0.5
            else f"{_money(spent)} against a {_money(cap)} cap — {_money(over)} over"
        )
        breaches.append(
            (
                over,
                Alert(
                    kind="category_at_cap",
                    severity="warning",
                    title=f"{category.category} has reached its cap",
                    body=(
                        f"{detail}, with {days_left} "
                        f"day{'s' if days_left != 1 else ''} left in "
                        f"{summary.month_label}."
                    ),
                    marker_key=f"category_at_cap:{summary.month}:{category.category}",
                    subject=category.category,
                ),
            )
        )
    breaches.sort(key=lambda item: item[0], reverse=True)
    return [alert for _over, alert in breaches[:MAX_CATEGORY_ALERTS_PER_PASS]]


def _novel_purchase_alerts(view: Any, *, today: date) -> list[Alert]:
    """A purchase the ledger has no precedent for, near enough to still matter.

    ``one_time_purchases`` is already computed for the screen, on a test that is
    deliberately conservative: over $1,000, a fifth of the month, and no earlier
    charge from that merchant at anything like the size. One substitution is made
    here — **the fifth is measured against a normal month, not this one.** The
    screen's denominator is the month so far, which on the 3rd is three days
    long, so a $1,200 charge would be most of "the month" and would alert every
    time; against a typical month it is what it actually is.
    """
    summary = view.summary
    typical = float(summary.average_monthly_spend or 0.0)
    if typical <= 0:
        return []

    alerts: list[Alert] = []
    for purchase in getattr(view, "one_time_purchases", []):
        amount = float(purchase.amount or 0.0)
        share = amount / typical
        if share < MIN_SHARE_OF_MONTH:
            continue
        purchased_on = _as_date(purchase.date)
        if purchased_on is None:
            continue
        if (today - purchased_on).days > NOVEL_PURCHASE_WINDOW_DAYS:
            continue
        merchant = purchase.merchant or "an unrecognised merchant"
        category = f" · {purchase.category}" if purchase.category else ""
        alerts.append(
            Alert(
                kind="novel_purchase",
                severity="warning",
                title=f"Unusual purchase: {_money(amount)} at {merchant}",
                body=(
                    f"{purchased_on.strftime('%b %-d')}{category}. That is "
                    f"{share:.0%} of a normal month, and nothing like it has "
                    f"been charged by this merchant before."
                ),
                # Once per purchase, ever — a charge does not become news again
                # because another pass ran.
                marker_key=f"novel_purchase:{purchase.transaction_id}",
                subject=purchase.transaction_id,
            )
        )
    return alerts
