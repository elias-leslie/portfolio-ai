"""Drop review questions the household has already settled.

A review regenerates its questions from scratch every time it runs. Without
this filter the same merchant or account question came back on every receipt
and statement, even after the household answered it, and an unanswered copy
held the document out of the ledger. A question is settled when a prior answer
covers the same family for the same merchant or account, or when existing
data already answers it: ledger frequency for a merchant, recorded spend for an
account, or the account's type for retirement tracking.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.household_question_classifier import clean_source_value, question_family

# Families answered once per merchant or per account rather than per document.
_MERCHANT_FAMILIES = frozenset({"shopping_channel", "merchant_cadence"})
_ACCOUNT_FAMILIES = frozenset({"core_spending"})
# Ledger history that already shows a merchant is part of routine shopping.
_RECURRING_MIN_TRANSACTIONS = 3
_RECURRING_MIN_MONTHS = 2
# An account with this much recorded spend is already part of the household budget.
_CORE_MIN_EXPENSES = 10
_GENERIC_TOKENS = frozenset({"the", "store", "shop", "wholesale", "market", "online", "com", "inc"})


def merchant_match_token(merchant: str) -> str | None:
    """Return the distinctive word used to match a merchant across sources."""
    for token in re.findall(r"[a-z]+", merchant.lower()):
        if len(token) >= 4 and token not in _GENERIC_TOKENS:
            return token
    return None


def _answered_keys(conn: Any) -> set[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT q.question, q.field_name,
               d.metadata->'structured_data'->>'merchant',
               d.metadata->'structured_data'->>'account_hint'
        FROM household_questions q
        LEFT JOIN household_documents d ON d.id = q.source_document_id
        WHERE q.status = 'answered' AND COALESCE(q.answer_text, '') <> ''
        """
    ).fetchall()
    keys: set[tuple[str, str]] = set()
    for question, field_name, merchant, account_hint in rows:
        family = question_family(str(question or ""), field_name)
        if family in _MERCHANT_FAMILIES and isinstance(merchant, str):
            token = merchant_match_token(merchant)
            if token:
                keys.add(("merchant", token))
        if family in _ACCOUNT_FAMILIES:
            hint = clean_source_value(account_hint)
            if hint:
                keys.add(("account", hint))
    return keys


def _merchant_is_recurring_in_ledger(conn: Any, token: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT date_trunc('month', transaction_date))
        FROM household_transactions
        WHERE removed IS NOT TRUE
          AND flow_type = 'expense'
          AND lower(COALESCE(raw_merchant, description, '')) LIKE %s
        """,
        [f"%{token}%"],
    ).fetchone()
    if not row:
        return False
    return int(row[0] or 0) >= _RECURRING_MIN_TRANSACTIONS and int(row[1] or 0) >= _RECURRING_MIN_MONTHS


def _matched_account(conn: Any, structured: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return (id, asset_group, account_type) for the one account the document names."""
    hints = " ".join(
        str(structured.get(key) or "") for key in ("account_hint", "account_mask", "account_label")
    )
    masks = set(re.findall(r"(?<!\d)(\d{4})(?!\d)", hints))
    if len(masks) != 1:
        return None
    rows = conn.execute(
        "SELECT id, asset_group, account_type FROM household_accounts WHERE account_mask = %s",
        [masks.pop()],
    ).fetchall()
    if len(rows) != 1:
        return None
    account_id, asset_group, account_type = rows[0]
    return str(account_id), str(asset_group or ""), str(account_type or "")


def _account_carries_household_spending(conn: Any, account_id: str) -> bool:
    row = conn.execute(
        """
        SELECT COUNT(*), COUNT(DISTINCT date_trunc('month', transaction_date))
        FROM household_transactions
        WHERE household_account_id = %s AND removed IS NOT TRUE AND flow_type = 'expense'
        """,
        [account_id],
    ).fetchone()
    return bool(row) and int(row[0] or 0) >= _CORE_MIN_EXPENSES and int(row[1] or 0) >= _RECURRING_MIN_MONTHS


def _is_retirement_tracking_question(text: str) -> bool:
    return "retirement readiness" in text.lower()


def drop_settled_questions(conn: Any, reviewed: dict[str, Any]) -> list[str]:
    """Remove settled questions from ``reviewed`` in place; return their texts."""
    questions = reviewed.get("questions")
    if not isinstance(questions, list) or not questions:
        return []
    structured = reviewed.get("structured_data")
    structured = structured if isinstance(structured, dict) else {}
    merchant = structured.get("merchant")
    token = merchant_match_token(merchant) if isinstance(merchant, str) else None
    account_hint = clean_source_value(structured.get("account_hint"))
    answered: set[tuple[str, str]] | None = None
    recurring: bool | None = None
    account: tuple[str, str, str] | None | bool = False  # False: not looked up yet

    kept: list[Any] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for question in questions:
        if not isinstance(question, dict):
            continue
        text = str(question.get("question") or "").strip()
        field_name = question.get("field_name")
        family = question_family(text, field_name if isinstance(field_name, str) else None)
        settled = text.lower() in seen
        if not settled and family in _MERCHANT_FAMILIES and token:
            answered = _answered_keys(conn) if answered is None else answered
            if ("merchant", token) in answered:
                settled = True
            else:
                recurring = _merchant_is_recurring_in_ledger(conn, token) if recurring is None else recurring
                settled = recurring
        elif not settled and family in _ACCOUNT_FAMILIES:
            if account_hint:
                answered = _answered_keys(conn) if answered is None else answered
                settled = ("account", account_hint) in answered
            if not settled:
                account = _matched_account(conn, structured) if account is False else account
                settled = isinstance(account, tuple) and _account_carries_household_spending(conn, account[0])
        elif not settled and _is_retirement_tracking_question(text):
            # The account type already answers this; only taxable accounts are ambiguous.
            account = _matched_account(conn, structured) if account is False else account
            settled = isinstance(account, tuple) and account[1] in {"retirement", "education"}
        if settled:
            dropped.append(text)
            continue
        seen.add(text.lower())
        kept.append(question)
    reviewed["questions"] = kept

    checks = reviewed.get("review_checks")
    if dropped and isinstance(checks, dict) and checks.get("ambiguity_remaining"):
        reason = str(checks.get("ambiguity_reason") or "").strip()
        if not reason or reason in dropped:
            checks["ambiguity_remaining"] = None
            checks.pop("ambiguity_reason", None)
    return dropped
