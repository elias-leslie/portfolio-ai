"""Shared helpers for deciding what counts as real household spend."""

from __future__ import annotations

from collections.abc import Iterable

_NON_SPEND_CATEGORIES = {"transfers", "income", "cash", "debt payments"}

_INVESTMENT_ACTIVITY_TEXT_PATTERNS = (
    "you bought",
    "you sold",
    "you redeemed",
    "reinvestment",
)

_NON_SPEND_TEXT_PATTERNS = (
    "payment thank you",
    "credit crd epay",
    "inst xfer",
    "online transfer",
    "recurring transfer",
    "moneyline",
    "zelle from",
    "zelle to",
    "ui benefit",
    "payroll",
    "atm withdrawal",
    *_INVESTMENT_ACTIVITY_TEXT_PATTERNS,
)

INCLUDE = "include"
EXCLUDE = "exclude"

# What each rule means in a sentence, for the roll-up that has to justify itself
# to the person whose money it dropped. Keyed by the rule string
# ``classify_cash_movement`` returns.
RULE_LABELS = {
    "category:transfers": "Moved between your own accounts",
    "category:income": "Money coming in",
    "category:cash": "Cash withdrawals",
    "category:debt payments": "Paying down a balance",
    "description:payment thank you": "Card payment",
    "description:credit crd epay": "Card payment",
    "description:inst xfer": "Account transfer",
    "description:online transfer": "Account transfer",
    "description:recurring transfer": "Standing transfer",
    "description:moneyline": "Account transfer",
    "description:zelle from": "Zelle received",
    "description:zelle to": "Zelle sent",
    "description:ui benefit": "Unemployment benefit",
    "description:payroll": "Paycheque",
    "description:atm withdrawal": "Cash withdrawals",
    "description:you bought": "Brokerage trade",
    "description:you sold": "Brokerage trade",
    "description:you redeemed": "Brokerage trade",
    "description:reinvestment": "Brokerage trade",
}

# Rules where the default is most often wrong for this household, and where an
# appeal is therefore worth inviting rather than merely permitting. A Zelle
# payment can be rent or a tutor; an ATM withdrawal becomes whatever it bought.
APPEALABLE_RULES = frozenset(
    {
        "description:zelle to",
        "description:atm withdrawal",
        "description:online transfer",
        "description:inst xfer",
        "category:cash",
    }
)


def rule_label(rule: str) -> str:
    """A person-readable name for a matched exclusion rule."""
    if rule in RULE_LABELS:
        return RULE_LABELS[rule]
    kind, _, value = rule.partition(":")
    if kind == "category":
        return f"Category: {value.title()}"
    if kind == "amount":
        return "Zero or credit amount"
    if kind == "override":
        return "You marked this as not spend"
    return f"Matched \u201c{value}\u201d"


def _normalized_text(*parts: str | None) -> str:
    return " ".join(
        part.strip().lower()
        for part in parts
        if isinstance(part, str) and part.strip()
    )


def looks_like_investment_activity(
    *,
    description: str | None,
    merchant: str | None,
) -> bool:
    """Return True when a row is brokerage trading activity, not household cash flow."""
    normalized_text = _normalized_text(description, merchant)
    return any(pattern in normalized_text for pattern in _INVESTMENT_ACTIVITY_TEXT_PATTERNS)


def matched_cash_movement_rule(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
) -> str | None:
    """The rule a row matches, ignoring anything the household has said about it.

    Kept separate from :func:`classify_cash_movement` because the roll-up has to
    show an appealed row *under the rule it was appealed from* -- "3 of the 41
    Zelle payments now count" is the sentence that makes an override checkable,
    and it needs the rule that would have applied.
    """
    normalized_category = (category or "").strip().lower()
    if normalized_category in _NON_SPEND_CATEGORIES:
        return f"category:{normalized_category}"

    normalized_text = _normalized_text(description, merchant)
    for pattern in _NON_SPEND_TEXT_PATTERNS:
        if pattern in normalized_text:
            return f"description:{pattern}"
    return None


def classify_cash_movement(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
    spend_override: str | None = None,
) -> str | None:
    """Name why a row is excluded from spend, or return None if it is real spend.

    Exclusion used to be a bare yes/no, which made it invisible: a Zelle payment
    to a tutor and an ATM withdrawal that became groceries both vanished from
    every total with nothing to point at and no way to appeal. Returning the
    matched rule instead lets a total say what it left out and lets a row say why
    it was dropped -- the difference between a filter that classifies and one
    that deletes.

    ``spend_override`` is the household's own verdict on this row and outranks
    every rule in both directions: ``include`` restores a row the list dropped,
    ``exclude`` drops one the list kept. A rule is a good guess about a string; a
    person knows what the money did.

    The returned string is the matched rule, suitable for grouping and display.
    """
    verdict = (spend_override or "").strip().lower()
    if verdict == INCLUDE:
        return None
    if verdict == EXCLUDE:
        return "override:excluded_by_you"

    return matched_cash_movement_rule(
        category=category,
        description=description,
        merchant=merchant,
    )


def looks_like_cash_movement(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
    spend_override: str | None = None,
) -> bool:
    """Return True when a row looks like cash movement, not true household spend."""
    return (
        classify_cash_movement(
            category=category,
            description=description,
            merchant=merchant,
            spend_override=spend_override,
        )
        is not None
    )


def is_budget_driving_expense(
    *,
    flow_type: str | None,
    category: str | None,
    description: str | None,
    merchant: str | None,
    spend_override: str | None = None,
) -> bool:
    """Return True when a row should count toward household spend analytics."""
    normalized_flow = (flow_type or "").strip().lower()
    if normalized_flow not in {"expense", "refund"}:
        return False
    return not looks_like_cash_movement(
        category=category,
        description=description,
        merchant=merchant,
        spend_override=spend_override,
    )


def non_spend_sql_predicate(
    *,
    text_expressions: Iterable[str],
    category_expression: str | None = None,
    override_expression: str | None = None,
) -> str:
    """Build a SQL predicate that matches known non-spend cash-movement rows.

    ``override_expression`` names the column holding the household's own verdict.
    It is applied here rather than by each caller because the alternative --
    every query remembering to check it -- is how a row comes to count on one
    surface and not another, which is the defect this phase exists to remove.
    """
    clauses: list[str] = []
    if category_expression is not None:
        clauses.append(
            f"LOWER(COALESCE({category_expression}, '')) IN ("
            + ", ".join(f"'{value}'" for value in sorted(_NON_SPEND_CATEGORIES))
            + ")"
        )

    for expression in text_expressions:
        for pattern in _NON_SPEND_TEXT_PATTERNS:
            clauses.append(f"COALESCE({expression}, '') ILIKE '%%{pattern}%%'")

    rules = "(" + " OR ".join(clauses) + ")"
    if override_expression is None:
        return rules
    return (
        f"(CASE WHEN {override_expression} = '{INCLUDE}' THEN FALSE"
        f" WHEN {override_expression} = '{EXCLUDE}' THEN TRUE"
        f" ELSE {rules} END)"
    )


def investment_activity_sql_predicate(
    *,
    text_expressions: Iterable[str],
) -> str:
    """Build a SQL predicate that matches brokerage trading rows."""
    clauses: list[str] = []
    for expression in text_expressions:
        for pattern in _INVESTMENT_ACTIVITY_TEXT_PATTERNS:
            clauses.append(f"COALESCE({expression}, '') ILIKE '%%{pattern}%%'")

    return "(" + " OR ".join(clauses) + ")"
