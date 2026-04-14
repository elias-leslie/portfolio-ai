"""Shared helpers for deciding what counts as real household spend."""

from __future__ import annotations

from collections.abc import Iterable

_NON_SPEND_CATEGORIES = {"transfers", "income", "cash"}

_NON_SPEND_TEXT_PATTERNS = (
    "payment thank you",
    "credit crd epay",
    "inst xfer",
    "online transfer",
    "recurring transfer",
    "moneyline",
    "venmo payment",
    "zelle from",
    "zelle to",
    "ui benefit",
    "payroll",
    "atm withdrawal",
)


def looks_like_cash_movement(
    *,
    category: str | None,
    description: str | None,
    merchant: str | None,
) -> bool:
    """Return True when a row looks like cash movement, not true household spend."""
    normalized_category = (category or "").strip().lower()
    if normalized_category in _NON_SPEND_CATEGORIES:
        return True

    normalized_text = " ".join(
        part.strip().lower()
        for part in [description or "", merchant or ""]
        if isinstance(part, str) and part.strip()
    )
    return any(pattern in normalized_text for pattern in _NON_SPEND_TEXT_PATTERNS)


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
