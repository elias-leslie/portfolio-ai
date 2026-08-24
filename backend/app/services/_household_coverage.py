"""How much of this household's money the system can actually see.

`visibility_score` reported **99 / "Strong household visibility"** while the
dashboard beside it said net worth was stale, three accounts needed refreshing
and one spending feed had gone quiet. It scored 99 because it was never a
coverage measure at all -- it was a setup checklist, awarding points for having
*told* the system a retirement age or an income target. Answering questions is
not the same as being visible, so the confidence signal moved opposite to the
actual coverage.

This measures observable facts instead: whose balances are current, which
spending feeds are still reporting, which known accounts are connected, and how
much spend carries a real category. Every component is published with the score
so the number can be checked rather than trusted -- the same reason the spend
exclusions publish their roll-up.
"""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdCoverage,
    HouseholdCoverageComponent,
)

# Balances carry the most weight because net worth is the number most often
# read, and a stale balance misstates it silently. Spending feeds carry the
# same weight because every budget figure on the page is built from them.
_WEIGHT_BALANCES = 30
_WEIGHT_SPENDING_FEEDS = 30
_WEIGHT_CONNECTED = 20
_WEIGHT_CLASSIFIED = 20

DEGRADED_FRESHNESS = frozenset({"aging", "stale", "needs_evidence"})
SPEND_DRIVER = "spend_driver"

STRONG_THRESHOLD = 85
PARTIAL_THRESHOLD = 60


def _share(part: float, whole: float) -> float:
    return part / whole if whole > 0 else 0.0


def _pct(value: float, *, perfect: bool = True) -> int:
    """A component only reaches 100 when nothing about it is wrong.

    Money-weighting alone would round $6,793 of stale balances against $1.56M to
    100%, printing a perfect score directly above a line naming two stale
    accounts -- which is the anti-correlation this module exists to remove. Small
    is not the same as absent.
    """
    score = round(max(0.0, min(1.0, value)) * 100)
    if not perfect:
        return min(score, 99)
    return score


def _money(value: Any) -> float:
    try:
        return abs(float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def _balance_component(account_summaries: list[Any]) -> HouseholdCoverageComponent:
    """Weighted by money, not by account count.

    A $572,782 brokerage gone stale and a $0 rollover gone stale are not the
    same event, and counting accounts would call them equal.
    """
    tracked = [a for a in account_summaries if _money(a.current_value) > 0]
    total = sum(_money(a.current_value) for a in tracked)
    stale = [
        a
        for a in tracked
        if getattr(a, "balance_freshness_status", None) in DEGRADED_FRESHNESS
        or (
            getattr(a, "balance_freshness_status", None) is None
            and a.freshness_status in DEGRADED_FRESHNESS
        )
    ]
    stale_value = sum(_money(a.current_value) for a in stale)

    if total <= 0:
        return HouseholdCoverageComponent(
            key="balances",
            label="Balances current",
            score=0,
            weight=_WEIGHT_BALANCES,
            detail="No account is reporting a balance yet.",
        )

    score = _pct(_share(total - stale_value, total), perfect=not stale)
    if not stale:
        detail = (
            f"All {len(tracked)} accounts holding a balance are current."
        )
    else:
        verb = "is" if len(stale) == 1 else "are"
        detail = (
            f"{len(stale)} of {len(tracked)} accounts {verb} stale, "
            f"holding ${stale_value:,.0f} of ${total:,.0f}."
        )
    return HouseholdCoverageComponent(
        key="balances",
        label="Balances current",
        score=score,
        weight=_WEIGHT_BALANCES,
        detail=detail,
    )


def _spending_component(account_summaries: list[Any]) -> HouseholdCoverageComponent:
    """Counted by account, because every spending feed is a whole blind spot.

    Weighting these by balance would rank a card by what is owed on it rather
    than by how much spending flows through it, which is the wrong quantity --
    a paid-off card can still be the one the household actually uses.
    """
    drivers = [
        a for a in account_summaries if getattr(a, "money_role", None) == SPEND_DRIVER
    ]
    if not drivers:
        return HouseholdCoverageComponent(
            key="spending_feeds",
            label="Spending feeds reporting",
            score=0,
            weight=_WEIGHT_SPENDING_FEEDS,
            detail="No account is currently reporting transactions.",
        )

    quiet = [
        a
        for a in drivers
        if getattr(a, "transaction_freshness_status", None) in DEGRADED_FRESHNESS
        or (
            getattr(a, "transaction_freshness_status", None) is None
            and a.freshness_status in DEGRADED_FRESHNESS
        )
    ]
    score = _pct(_share(len(drivers) - len(quiet), len(drivers)), perfect=not quiet)
    if not quiet:
        detail = f"All {len(drivers)} spending accounts are reporting."
    else:
        names = ", ".join(str(a.label) for a in quiet[:2])
        verb = "has" if len(quiet) == 1 else "have"
        detail = (
            f"{len(quiet)} of {len(drivers)} spending accounts {verb} gone quiet ({names})."
        )
    return HouseholdCoverageComponent(
        key="spending_feeds",
        label="Spending feeds reporting",
        score=score,
        weight=_WEIGHT_SPENDING_FEEDS,
        detail=detail,
    )


def _connected_component(
    account_summaries: list[Any],
    discovered_accounts: list[Any],
) -> HouseholdCoverageComponent:
    """Accounts the household is known to have, against accounts it can see.

    A card named on five receipts that matches no account is a hole in coverage
    that no amount of freshness on the other accounts fills.
    """
    connected = len(account_summaries)
    unconnected = len(discovered_accounts)
    total = connected + unconnected
    if total == 0:
        return HouseholdCoverageComponent(
            key="connected_accounts",
            label="Known accounts connected",
            score=0,
            weight=_WEIGHT_CONNECTED,
            detail="No accounts are connected yet.",
        )

    score = _pct(_share(connected, total), perfect=unconnected == 0)
    if unconnected == 0:
        detail = f"All {connected} known accounts are connected."
    else:
        names = ", ".join(
            str(getattr(a, "suggested_label", None) or getattr(a, "key", ""))
            for a in discovered_accounts[:2]
        )
        detail = (
            f"{unconnected} account{'s' if unconnected != 1 else ''} "
            f"seen in evidence {'are' if unconnected != 1 else 'is'} not connected ({names})."
        )
    return HouseholdCoverageComponent(
        key="connected_accounts",
        label="Known accounts connected",
        score=score,
        weight=_WEIGHT_CONNECTED,
        detail=detail,
    )


def _classified_component(
    *,
    tracked_expense_count: int,
    unclassified_count: int,
) -> HouseholdCoverageComponent:
    if tracked_expense_count <= 0:
        return HouseholdCoverageComponent(
            key="classified_spend",
            label="Spend classified",
            score=0,
            weight=_WEIGHT_CLASSIFIED,
            detail="There is no tracked spending to classify yet.",
        )

    classified = max(tracked_expense_count - unclassified_count, 0)
    score = _pct(
        _share(classified, tracked_expense_count), perfect=unclassified_count == 0
    )
    if unclassified_count == 0:
        detail = f"All {tracked_expense_count:,} tracked expense rows carry a category."
    else:
        detail = (
            f"{unclassified_count:,} of {tracked_expense_count:,} expense rows "
            "are still waiting on a category."
        )
    return HouseholdCoverageComponent(
        key="classified_spend",
        label="Spend classified",
        score=score,
        weight=_WEIGHT_CLASSIFIED,
        detail=detail,
    )


def coverage_label(score: int) -> str:
    if score >= STRONG_THRESHOLD:
        return "Strong coverage"
    if score >= PARTIAL_THRESHOLD:
        return "Partial coverage"
    return "Limited coverage"


def build_coverage(
    *,
    account_summaries: list[Any],
    discovered_accounts: list[Any],
    tracked_expense_count: int,
    unclassified_count: int,
) -> HouseholdCoverage:
    """Score what the system can see, and publish the working."""
    components = [
        _balance_component(account_summaries),
        _spending_component(account_summaries),
        _connected_component(account_summaries, discovered_accounts),
        _classified_component(
            tracked_expense_count=tracked_expense_count,
            unclassified_count=unclassified_count,
        ),
    ]
    total_weight = sum(component.weight for component in components)
    score = round(
        sum(component.score * component.weight for component in components)
        / total_weight
    )

    # The sentence names the weakest component rather than restating the score.
    # "84%" tells nobody what to do; "two accounts are stale" does.
    weakest = min(components, key=lambda component: component.score)
    summary = (
        f"{coverage_label(score)}: {weakest.detail}"
        if weakest.score < 100
        else f"{coverage_label(score)}: every account is connected, current and classified."
    )
    return HouseholdCoverage(
        score=score,
        label=coverage_label(score),
        summary=summary,
        components=components,
    )
