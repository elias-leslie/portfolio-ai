"""What the household's cards commit it to, in the place the plan is read.

The Cards tab already knows the renewal dates and the welcome deadlines; the
Plan screen, where the household decides what it can spend, knew only the
balance -- and even that arrived through the affordability check rather than as
a commitment (P0-20). This builds one view of both: what is owed, what the
cards cost to keep, and which bonus is still open.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdCardCommitment,
    HouseholdCardCommitments,
)


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _card_label(card: HouseholdCardCommitment) -> str:
    """Name a card the way the household would: whose it is, and the last four."""
    parts = [card.owner_name.split()[0]] if card.owner_name else []
    if card.account_mask:
        parts.append(f"·{card.account_mask}")
    if not parts:
        return card.product_name
    return f"{card.product_name} ({' '.join(parts)})"


def _days_word(days: int) -> str:
    return "1 day" if days == 1 else f"{days} days"


def build_card_commitments(
    *,
    cards: list[Any],
    account_values: dict[str, float | None] | None = None,
    today: date | None = None,
) -> HouseholdCardCommitments:
    """Collect the commitments on every open card.

    ``cards`` are ``HouseholdCreditCard`` rows with their product hydrated;
    ``account_values`` maps a card's linked account to what it currently holds.
    A card whose account nothing reports is listed as unknown rather than
    counted as $0 -- a card with no feed is exactly the one whose balance is
    most likely to be a surprise.
    """
    account_values = account_values or {}
    today = today or date.today()
    plan = HouseholdCardCommitments()

    rows: list[HouseholdCardCommitment] = []
    for card in cards:
        if str(getattr(card, "status", "")) != "active":
            continue
        product = getattr(card, "product", None)
        row = HouseholdCardCommitment(
            card_id=str(card.id),
            product_name=str(getattr(product, "product_name", "") or "Card"),
            account_label=getattr(card, "account_label", None),
            account_mask=getattr(card, "account_mask", None),
            owner_name=getattr(card, "account_owner", None),
            role=str(getattr(card, "role", "") or "rotating"),
        )

        account_id = str(getattr(card, "household_account_id", "") or "")
        value = account_values.get(account_id)
        if account_id and value is not None:
            row.balance_owed = round(abs(float(value)), 2)
            row.balance_detail = f"{_money(row.balance_owed)} owed right now."
        else:
            row.balance_detail = (
                "No balance is reaching this card, so what it owes is unknown rather than zero."
            )

        row.annual_fee = round(float(getattr(product, "annual_fee", 0.0) or 0.0), 2)
        due = _as_date(getattr(card, "annual_fee_due_date", None))
        if row.annual_fee <= 0:
            row.annual_fee_detail = "No annual fee."
        elif due is None:
            row.annual_fee_detail = (
                f"The {_money(row.annual_fee)} fee has no recorded renewal date, "
                "so nothing can warn before it posts."
            )
        else:
            row.annual_fee_due_date = due.isoformat()
            row.annual_fee_days_away = (due - today).days
            row.annual_fee_detail = (
                f"{_money(row.annual_fee)} renews {due.strftime('%b %d, %Y')}, "
                f"{_days_word(max(row.annual_fee_days_away, 0))} away."
                if row.annual_fee_days_away >= 0
                else f"{_money(row.annual_fee)} renewed {due.strftime('%b %d, %Y')}."
            )

        row.welcome_min_spend = round(float(getattr(product, "welcome_min_spend", 0.0) or 0.0), 2)
        row.welcome_progress = round(float(getattr(card, "welcome_progress_amount", 0.0) or 0.0), 2)
        deadline = _as_date(getattr(card, "welcome_deadline", None))
        status = str(getattr(card, "welcome_status", "") or "not_started")
        if row.welcome_min_spend <= 0:
            row.welcome_status = "none"
            row.welcome_detail = "No welcome bonus on this card."
        elif status == "earned":
            row.welcome_status = "earned"
            row.welcome_detail = (
                f"Bonus earned -- {_money(row.welcome_progress)} against a "
                f"{_money(row.welcome_min_spend)} minimum."
            )
        elif status == "missed":
            row.welcome_status = "missed"
            row.welcome_detail = (
                f"Missed: {_money(row.welcome_progress)} of "
                f"{_money(row.welcome_min_spend)} by the deadline."
            )
        elif deadline is None:
            row.welcome_status = status
            row.welcome_detail = (
                f"{_money(row.welcome_progress)} of "
                f"{_money(row.welcome_min_spend)} spent, but no deadline is "
                "recorded -- nothing here can tell whether it is still winnable."
            )
        else:
            remaining = max(row.welcome_min_spend - row.welcome_progress, 0.0)
            days_left = (deadline - today).days
            row.welcome_status = status
            row.welcome_deadline = deadline.isoformat()
            row.welcome_days_left = days_left
            if days_left < 0:
                row.welcome_detail = (
                    f"The deadline passed on {deadline.strftime('%b %d, %Y')} "
                    f"with {_money(row.welcome_progress)} of "
                    f"{_money(row.welcome_min_spend)} spent."
                )
            elif remaining <= 0:
                row.welcome_detail = (
                    f"{_money(row.welcome_progress)} of "
                    f"{_money(row.welcome_min_spend)} is already spent; the "
                    "bonus is not marked earned yet."
                )
            else:
                per_day = remaining / max(days_left, 1)
                row.welcome_detail = (
                    f"{_money(remaining)} to go by "
                    f"{deadline.strftime('%b %d, %Y')} -- "
                    f"{_days_word(days_left)} left, about "
                    f"{_money(per_day)}/day. Route household spend here."
                )
        rows.append(row)

    plan.cards = rows
    if not rows:
        plan.status = "no_cards"
        plan.headline = "No open cards are recorded."
        plan.detail = (
            "Card rotation is routine here, so a card the household is using "
            "and the plan cannot see is a balance, a fee and a deadline that "
            "nothing is tracking. Add it on the Cards tab."
        )
        return plan

    known = [row.balance_owed for row in rows if row.balance_owed is not None]
    plan.balance_total = round(sum(known), 2) if known else None
    plan.balance_unknown_labels = [_card_label(row) for row in rows if row.balance_owed is None]
    plan.annual_fee_yearly = round(sum(row.annual_fee for row in rows), 2)
    plan.annual_fee_monthly = round(plan.annual_fee_yearly / 12, 2)

    soonest = sorted(
        (row for row in rows if row.annual_fee > 0 and (row.annual_fee_days_away or -1) >= 0),
        key=lambda row: row.annual_fee_days_away or 0,
    )
    if not plan.annual_fee_yearly:
        plan.next_fee_detail = "None of these cards charges an annual fee."
    elif not soonest:
        plan.next_fee_detail = (
            f"{_money(plan.annual_fee_yearly)}/yr of fees, but no renewal date "
            "is recorded on any of them."
        )
    else:
        first = soonest[0]
        same_day = [row for row in soonest if row.annual_fee_due_date == first.annual_fee_due_date]
        due_label = date.fromisoformat(first.annual_fee_due_date or "").strftime("%b %d, %Y")
        days_away = _days_word(max(first.annual_fee_days_away or 0, 0))
        if len(same_day) > 1:
            total = sum(row.annual_fee for row in same_day)
            plan.next_fee_detail = (
                f"{len(same_day)} fees totalling {_money(total)} land together on "
                f"{due_label}, {days_away} away."
            )
        else:
            plan.next_fee_detail = (
                f"Next up: {_money(first.annual_fee)} on {_card_label(first)} on "
                f"{due_label}, {days_away} away."
            )

    open_bonuses = [row for row in rows if row.welcome_status in {"not_started", "in_progress"}]
    plan.welcome_open_count = len(open_bonuses)
    if open_bonuses:
        plan.welcome_detail = min(
            open_bonuses,
            key=lambda row: row.welcome_days_left if row.welcome_days_left is not None else 10**6,
        ).welcome_detail
    else:
        earned = [row for row in rows if row.welcome_status == "earned"]
        plan.welcome_detail = (
            f"{len(earned)} welcome bonus{'es' if len(earned) != 1 else ''} already "
            "earned; nothing is open."
            if earned
            else "No welcome bonus is open."
        )

    plan.status = "committed"
    owed = (
        f"{_money(plan.balance_total)} owed"
        if plan.balance_total is not None
        else "Nothing is reporting a balance"
    )
    plan.headline = (
        f"{owed} across {len(rows)} card{'s' if len(rows) != 1 else ''}, and "
        f"{_money(plan.annual_fee_yearly)}/yr to keep them."
    )
    fee_line = (
        f"The fees are {_money(plan.annual_fee_monthly)}/mo of income already "
        "spoken for, so the caps come out after them."
        if plan.annual_fee_yearly > 0
        else "These cards cost nothing to keep."
    )
    unknown_line = (
        f" No balance is reaching {', '.join(plan.balance_unknown_labels)}, so what "
        "it owes is not in that total."
        if plan.balance_unknown_labels
        else ""
    )
    plan.detail = f"{fee_line}{unknown_line}"
    return plan
