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


def classify_cash_movement(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
) -> str | None:
    """Name why a row is excluded from spend, or return None if it is real spend.

    Exclusion used to be a bare yes/no, which made it invisible: a Zelle payment
    to a tutor and an ATM withdrawal that became groceries both vanished from
    every total with nothing to point at and no way to appeal. Returning the
    matched rule instead lets a total say what it left out and lets a row say why
    it was dropped -- the difference between a filter that classifies and one
    that deletes.

    The returned string is the matched rule, suitable for grouping and display.
    """
    normalized_category = (category or "").strip().lower()
    if normalized_category in _NON_SPEND_CATEGORIES:
        return f"category:{normalized_category}"

    normalized_text = _normalized_text(description, merchant)
    for pattern in _NON_SPEND_TEXT_PATTERNS:
        if pattern in normalized_text:
            return f"description:{pattern}"
    return None


def looks_like_cash_movement(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
) -> bool:
    """Return True when a row looks like cash movement, not true household spend."""
    return (
        classify_cash_movement(
            category=category,
            description=description,
            merchant=merchant,
        )
        is not None
    )


def is_budget_driving_expense(
    *,
    flow_type: str | None,
    category: str | None,
    description: str | None,
    merchant: str | None,
) -> bool:
    """Return True when a row should count toward household spend analytics."""
    normalized_flow = (flow_type or "").strip().lower()
    if normalized_flow not in {"expense", "refund"}:
        return False
    return not looks_like_cash_movement(
        category=category,
        description=description,
        merchant=merchant,
    )


def non_spend_sql_predicate(
    *,
    text_expressions: Iterable[str],
    category_expression: str | None = None,
) -> str:
    """Build a SQL predicate that matches known non-spend cash-movement rows."""
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

    return "(" + " OR ".join(clauses) + ")"


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
