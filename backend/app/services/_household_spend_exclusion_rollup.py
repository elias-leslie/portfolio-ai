"""What the spend filters left out, grouped by the rule that left it out.

The filters were a literal string list applied silently: 138 of 996 ledger rows
were dropped from every total with no roll-up of what that cost and no way to
disagree. A total that cannot say what it excluded is not a total, it is a
claim -- so this builds the counterpart figure, per rule, with the merchants
under it named and the household's own overrides counted separately.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from app.models.household_finance import (
    HouseholdSpendExclusionRule,
    HouseholdSpendExclusions,
)
from app.services._household_spend_filters import (
    APPEALABLE_RULES,
    EXCLUDE,
    INCLUDE,
    matched_cash_movement_rule,
    rule_label,
)

# Enough names to recognise a rule's contents without listing forty of them.
_SAMPLE_MERCHANTS = 3

_WINDOW_SQL = """
    SELECT
        t.category,
        t.description,
        COALESCE(m.canonical_name, NULLIF(t.raw_merchant, ''), NULLIF(t.description, '')) AS merchant,
        CAST(t.amount AS DOUBLE PRECISION) AS amount,
        t.spend_override,
        LOWER(COALESCE(t.flow_type, 'expense')) AS flow_type
    FROM household_transactions t
    LEFT JOIN household_merchants m ON m.id = t.merchant_id
    WHERE t.removed IS NOT TRUE
      AND t.transaction_date >= %s
      AND t.transaction_date <= %s
"""

# A row can leave the spend totals for three different reasons, and only one of
# them is the literal string list. Reporting just that one would answer "why is
# this Zelle payment missing?" while leaving "why is my spend total smaller than
# my transactions?" unanswered -- and the second question is the one a person
# actually arrives with.
_FLOW_LABELS = {
    "income": "Money coming in",
    # In and out are deliberately the same line. The card answers "why is this
    # not in my spend total?", and "it moved between your own accounts" answers
    # it whole -- splitting by direction adds a second row and no decision.
    "transfer": "Moved between your own accounts",
    "transfer_in": "Moved between your own accounts",
    "transfer_out": "Moved between your own accounts",
    "payment": "Paying a card or a loan",
    "investment": "Brokerage activity",
    "fee": "Fees",
}
_SPEND_FLOWS = frozenset({"expense", "refund"})


def _flow_rule_label(flow_type: str) -> str:
    return _FLOW_LABELS.get(flow_type, f"Not an expense ({flow_type})")


def _money(value: float) -> float:
    return round(value, 2)


def fetch_spend_exclusions(
    storage: Any,
    *,
    start_date: date,
    end_date: date,
) -> HouseholdSpendExclusions:
    """Roll up the excluded rows over one window, keyed by matched rule."""
    with storage.connection() as conn:
        rows = conn.execute(_WINDOW_SQL, [start_date, end_date]).fetchall()

    counts: dict[str, int] = {}
    amounts: dict[str, float] = {}
    merchants: dict[str, list[str]] = {}
    restored_counts: dict[str, int] = {}
    restored_amounts: dict[str, float] = {}

    excluded_count = 0
    excluded_amount = 0.0
    included_count = 0
    included_amount = 0.0
    overridden_count = 0

    for category, description, merchant, amount_raw, override_raw, flow_raw in rows:
        amount = float(amount_raw or 0.0)
        override = str(override_raw).strip().lower() if override_raw else None
        flow_type = str(flow_raw or "expense").strip().lower()
        if flow_type not in _SPEND_FLOWS:
            matched: str | None = f"flow:{flow_type}"
        elif amount <= 0:
            matched = "amount:non_positive"
        else:
            matched = matched_cash_movement_rule(
                category=str(category) if category is not None else None,
                description=str(description) if description is not None else None,
                merchant=str(merchant) if merchant is not None else None,
            )
        if override in {INCLUDE, EXCLUDE}:
            overridden_count += 1

        is_excluded = matched is not None
        if override == INCLUDE:
            is_excluded = False
        elif override == EXCLUDE:
            is_excluded = True

        if is_excluded:
            excluded_count += 1
            excluded_amount += amount
        else:
            included_count += 1
            included_amount += amount

        # A row restored by hand is still reported under the rule it was
        # restored from -- "3 of 41 Zelle payments now count" is what makes an
        # override checkable rather than merely applied.
        if matched is None:
            continue
        counts[matched] = counts.get(matched, 0) + 1
        amounts[matched] = amounts.get(matched, 0.0) + amount
        if override == INCLUDE:
            restored_counts[matched] = restored_counts.get(matched, 0) + 1
            restored_amounts[matched] = restored_amounts.get(matched, 0.0) + amount
        name = str(merchant or description or "").strip()
        names = merchants.setdefault(matched, [])
        if name and name not in names and len(names) < _SAMPLE_MERCHANTS:
            names.append(name)

    # Grouped by what the rule *means*, not by which rule matched: "income" is
    # reachable both as a flow type and as a category, and listing "Money coming
    # in" twice would reproduce, in this card, the doubled legend that task 1.6
    # existed to remove.
    grouped: dict[str, HouseholdSpendExclusionRule] = {}
    for rule, rule_count in counts.items():
        label = (
            _flow_rule_label(rule.removeprefix("flow:"))
            if rule.startswith("flow:")
            else rule_label(rule)
        )
        existing = grouped.get(label)
        if existing is None:
            grouped[label] = HouseholdSpendExclusionRule(
                rule=rule,
                label=label,
                transaction_count=rule_count,
                total_amount=_money(amounts[rule]),
                appealable=rule in APPEALABLE_RULES,
                restored_count=restored_counts.get(rule, 0),
                restored_amount=_money(restored_amounts.get(rule, 0.0)),
                sample_merchants=list(merchants.get(rule, [])),
            )
            continue
        existing.transaction_count += rule_count
        existing.total_amount = _money(existing.total_amount + amounts[rule])
        existing.appealable = existing.appealable or rule in APPEALABLE_RULES
        existing.restored_count += restored_counts.get(rule, 0)
        existing.restored_amount = _money(
            existing.restored_amount + restored_amounts.get(rule, 0.0)
        )
        for name in merchants.get(rule, []):
            if (
                name not in existing.sample_merchants
                and len(existing.sample_merchants) < _SAMPLE_MERCHANTS
            ):
                existing.sample_merchants.append(name)

    rules = list(grouped.values())
    # Biggest first: the rule worth arguing with is the one holding the most money.
    rules.sort(key=lambda entry: (-entry.total_amount, entry.label))

    return HouseholdSpendExclusions(
        excluded_count=excluded_count,
        excluded_amount=_money(excluded_amount),
        included_count=included_count,
        included_amount=_money(included_amount),
        overridden_count=overridden_count,
        rules=rules,
        summary=_summary(
            excluded_count=excluded_count,
            excluded_amount=excluded_amount,
            included_count=included_count,
            overridden_count=overridden_count,
            rules=rules,
        ),
    )


def _summary(
    *,
    excluded_count: int,
    excluded_amount: float,
    included_count: int,
    overridden_count: int,
    rules: list[HouseholdSpendExclusionRule],
) -> str:
    total_rows = excluded_count + included_count
    if excluded_count == 0:
        return f"Every one of the {total_rows:,} rows in this window counts as spend."

    lead = (
        f"{excluded_count:,} of {total_rows:,} rows "
        f"(${excluded_amount:,.0f}) are held out of spend totals"
    )
    biggest = rules[0] if rules else None
    if biggest is not None:
        lead += f", most of it {biggest.label.lower()} (${biggest.total_amount:,.0f})"
    lead += "."
    if overridden_count:
        lead += f" You have decided {overridden_count:,} of these by hand."
    return lead


def fetch_current_window_spend_exclusions(storage: Any) -> HouseholdSpendExclusions:
    """The roll-up over the last complete calendar month plus the month to date.

    Two months rather than one: a single month is too small a sample to show
    that a rule is systematically wrong, and the whole history is too large to
    act on.
    """
    today = date.today()
    month_start = today.replace(day=1)
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    return fetch_spend_exclusions(
        storage,
        start_date=previous_month_start,
        end_date=today.replace(day=calendar.monthrange(today.year, today.month)[1]),
    )
