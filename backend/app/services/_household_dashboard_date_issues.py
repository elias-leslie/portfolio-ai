from __future__ import annotations

from typing import Any

from app.models.household_finance import HouseholdTransactionDateIssue
from app.services._household_dashboard_queries_shared import (
    _date_iso,
    _float_or_zero,
    _short_excerpt,
)

_TRANSACTION_DATE_ISSUES_SQL = """
    SELECT
        t.id,
        t.document_id,
        d.filename,
        d.source_type,
        d.document_type,
        t.transaction_date,
        d.uploaded_at,
        COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
        t.description,
        t.amount,
        t.account_label,
        t.confidence,
        d.metadata->'structured_data'->>'text_preview' AS source_excerpt
    FROM household_transactions t
    JOIN household_documents d ON d.id = t.document_id
    LEFT JOIN household_merchants m ON m.id = t.merchant_id
    WHERE t.transaction_date > CURRENT_DATE
      AND COALESCE(t.metadata->'date_quality_resolution'->>'status', '')
          NOT IN ('resolved', 'superseded', 'excluded')
    ORDER BY t.transaction_date ASC, CAST(t.amount AS DOUBLE PRECISION) DESC
    LIMIT %s
"""

_DOCUMENT_DATE_ISSUES_SQL = """
    SELECT
        d.id,
        d.filename,
        d.source_type,
        d.document_type,
        d.uploaded_at,
        d.metadata->'date_quality_summary'->'future_transactions' AS future_transactions,
        d.metadata->'structured_data'->>'text_preview' AS source_excerpt
    FROM household_documents d
    WHERE d.metadata->'date_quality_summary'->>'status' = 'needs_review'
    ORDER BY d.uploaded_at DESC
    LIMIT %s
"""


def _transaction_issue(row: Any) -> HouseholdTransactionDateIssue | None:
    transaction_date = _date_iso(row[5])
    if transaction_date is None:
        return None
    return HouseholdTransactionDateIssue(
        id=f"future-date-{row[0]}",
        transaction_id=str(row[0]),
        document_id=str(row[1]),
        filename=str(row[2]),
        source_type=str(row[3]),
        document_type=str(row[4]),
        transaction_date=transaction_date,
        uploaded_at=_date_iso(row[6]),
        merchant=str(row[7]),
        description=str(row[8]),
        amount=round(float(row[9] or 0.0), 2),
        account_label=str(row[10]) if row[10] is not None else None,
        confidence=float(row[11]) if row[11] is not None else None,
        reason="Extracted transaction date is after today, so Jenny is holding it out of current money calculations.",
        source_excerpt=_short_excerpt(row[12]),
    )


def _document_issue(row: Any, transaction: dict[str, Any], index: int) -> HouseholdTransactionDateIssue | None:
    transaction_date = str(transaction.get("transaction_date") or "")
    if not transaction_date:
        return None
    return HouseholdTransactionDateIssue(
        id=f"future-date-document-{row[0]}-{index}",
        transaction_id=None,
        document_id=str(row[0]),
        filename=str(row[1]),
        source_type=str(row[2]),
        document_type=str(row[3]),
        transaction_date=transaction_date,
        uploaded_at=_date_iso(row[4]),
        merchant=str(transaction.get("merchant") or "Unknown merchant"),
        description=str(transaction.get("description") or "Future-dated transaction"),
        amount=round(_float_or_zero(transaction.get("amount")), 2),
        account_label=str(transaction.get("account_label")) if transaction.get("account_label") else None,
        confidence=_float_or_zero(transaction.get("confidence")) if transaction.get("confidence") is not None else None,
        reason="Extracted transaction date is after today, so Jenny held it out instead of inserting it into the current ledger.",
        source_excerpt=_short_excerpt(row[6]),
    )


def fetch_transaction_date_issues(storage: Any, limit: int = 12) -> list[HouseholdTransactionDateIssue]:
    with storage.connection() as conn:
        rows = conn.execute(_TRANSACTION_DATE_ISSUES_SQL, [limit]).fetchall()
        document_rows = conn.execute(_DOCUMENT_DATE_ISSUES_SQL, [limit]).fetchall()
    issues = [issue for row in rows if (issue := _transaction_issue(row)) is not None]
    existing_document_ids = {issue.document_id for issue in issues}
    for row in document_rows:
        if len(issues) >= limit or str(row[0]) in existing_document_ids:
            continue
        remaining_limit = limit - len(issues)
        future_transactions = row[5] if isinstance(row[5], list) else []
        for index, transaction in enumerate(future_transactions[:remaining_limit]):
            if not isinstance(transaction, dict):
                continue
            issue = _document_issue(row, transaction, index)
            if issue is None:
                continue
            issues.append(issue)
            if len(issues) >= limit:
                break
    return issues
