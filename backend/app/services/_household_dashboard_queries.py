"""Database query helpers for the household dashboard (require storage access)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.models.household_finance import (
    HouseholdCategorizationCandidate,
    HouseholdRecurringCommitment,
)
from app.services._household_dashboard_builders import (
    build_recurring_commitment,
    suggest_category,
    suggest_essentiality,
)

_CATEGORIZATION_SQL = """
    SELECT
        t.id,
        COALESCE(t.raw_merchant, t.description) AS merchant,
        t.description,
        t.amount,
        t.transaction_date,
        t.category,
        t.essentiality,
        t.confidence,
        COALESCE(similar_txns.similar_count, 0) AS similar_count
    FROM household_transactions t
    LEFT JOIN (
        SELECT merchant_id, COUNT(*) AS similar_count
        FROM household_transactions
        WHERE flow_type = 'expense'
        GROUP BY merchant_id
    ) similar_txns ON similar_txns.merchant_id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND (
        COALESCE(t.category, 'Household') = 'Household'
        OR COALESCE(t.essentiality, 'mixed') = 'mixed'
        OR COALESCE(t.confidence, 0) < 0.85
      )
    ORDER BY COALESCE(t.confidence, 0) ASC, t.transaction_date DESC
    LIMIT %s
"""

_RECURRING_SQL = """
    SELECT
        COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
        COALESCE(t.category, 'Household') AS category,
        AVG(CAST(t.amount AS DOUBLE PRECISION)) AS average_amount,
        COUNT(*) AS transaction_count,
        MAX(t.transaction_date) AS last_seen
    FROM household_transactions t
    LEFT JOIN household_merchants m ON m.id = t.merchant_id
    WHERE t.flow_type = 'expense'
    GROUP BY 1, 2
    HAVING COUNT(*) >= 2
    ORDER BY average_amount DESC
    LIMIT %s
"""

_RETIREMENT_CONTRIBUTION_SQL = """
    SELECT AVG(month_total)
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type IN ('transfer_out', 'expense')
          AND (
            COALESCE(account_label, '') ILIKE '%ira%'
            OR COALESCE(account_label, '') ILIKE '%401%'
            OR COALESCE(account_label, '') ILIKE '%roth%'
            OR COALESCE(account_label, '') ILIKE '%hsa%'
          )
        GROUP BY 1
    ) monthly_contributions
"""

_MONTH_SPEND_SQL = """
    SELECT COALESCE(SUM(CAST(amount AS DOUBLE PRECISION)), 0)
    FROM household_transactions
    WHERE flow_type = 'expense'
      AND transaction_date >= date_trunc('month', CURRENT_DATE)
"""


def fetch_categorization_queue(
    storage: Any,
    transaction_service: Any,
    limit: int = 6,
) -> list[HouseholdCategorizationCandidate]:
    with storage.connection() as conn:
        rows = conn.execute(_CATEGORIZATION_SQL, [limit]).fetchall()
    return [
        HouseholdCategorizationCandidate(
            id=str(row[0]),
            merchant=str(row[1]),
            description=str(row[2]),
            amount=float(row[3]),
            transaction_date=row[4].isoformat(),
            current_category=str(row[5] or "Household"),
            current_essentiality=str(row[6] or "mixed"),
            suggested_category=suggest_category(str(row[1]), str(row[2])),
            suggested_essentiality=suggest_essentiality(str(row[1]), str(row[2])),
            confidence=float(row[7] or 0.0),
            similar_transaction_count=max(int(row[8] or 0) - 1, 0),
            reason="Low-confidence or mixed classification needs a human pass before Jenny hardens the budget lane.",
        )
        for row in rows
    ]


def fetch_recurring_commitments(
    storage: Any,
    transaction_service: Any,
    limit: int = 6,
) -> list[HouseholdRecurringCommitment]:
    today = datetime.now(UTC).date()
    with storage.connection() as conn:
        rows = conn.execute(_RECURRING_SQL, [limit * 2]).fetchall()
    commitments: list[HouseholdRecurringCommitment] = []
    for row in rows:
        merchant = str(row[0])
        cadence_info = transaction_service.infer_merchant_cadence(merchant=merchant) or {}
        cadence = str(cadence_info.get("label") or "irregular")
        commitment = build_recurring_commitment(row, cadence, cadence_info, today)
        if commitment is not None:
            commitments.append(commitment)
    return commitments[:limit]


def fetch_monthly_retirement_contributions(storage: Any) -> float:
    with storage.connection() as conn:
        row = conn.execute(_RETIREMENT_CONTRIBUTION_SQL).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0


def fetch_current_month_spend(storage: Any) -> float:
    with storage.connection() as conn:
        row = conn.execute(_MONTH_SPEND_SQL).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0
