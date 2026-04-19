"""Database query helpers for the household dashboard (require storage access)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdCategorizationCandidate,
    HouseholdProfile,
    HouseholdRecurringCommitment,
    HouseholdReports,
)
from app.services._household_dashboard_builders import (
    build_recurring_commitment,
    suggest_category,
    suggest_essentiality,
)
from app.services._household_dashboard_queries_shared import (
    _date_value,
    _days_since,
    _fetch_scalar_float,
)
from app.services._household_spend_filters import non_spend_sql_predicate

logger = get_logger(__name__)


def _current_transaction_date_predicate(alias: str | None = None) -> str:
    qualifier = f"{alias}." if alias else ""
    return f"{qualifier}transaction_date <= CURRENT_DATE"


_NON_SPEND_TRANSACTION_SQL = non_spend_sql_predicate(
    text_expressions=["t.description", "t.raw_merchant"],
    category_expression="t.category",
)

_CATEGORIZATION_SQL = f"""
    SELECT
        t.id,
        COALESCE(t.raw_merchant, t.description) AS merchant,
        t.description,
        t.amount,
        t.transaction_date,
        t.category,
        t.essentiality,
        t.confidence,
        COALESCE(similar_txns.similar_count, 0) AS similar_count,
        COALESCE(t.metadata->'audit'->>'reason', '') AS audit_reason,
        COALESCE(t.metadata->'audit'->>'suggested_category', '') AS audit_suggested_category,
        COALESCE(t.metadata->'audit'->>'suggested_essentiality', '') AS audit_suggested_essentiality
    FROM household_transactions t
    LEFT JOIN (
        SELECT t.merchant_id, COUNT(*) AS similar_count
        FROM household_transactions t
        WHERE t.flow_type = 'expense'
          AND {_current_transaction_date_predicate("t")}
          AND NOT {_NON_SPEND_TRANSACTION_SQL}
        GROUP BY merchant_id
    ) similar_txns ON similar_txns.merchant_id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND {_current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
      AND (
            COALESCE(t.confidence, 0) < 0.60
         OR COALESCE(t.metadata->'audit'->>'status', '') = 'needs_review'
      )
    ORDER BY CAST(t.amount AS DOUBLE PRECISION) DESC, COALESCE(similar_txns.similar_count, 0) DESC
    LIMIT %s
"""

_RECURRING_SQL = f"""
    SELECT
        COALESCE(m.canonical_name, t.raw_merchant, t.description) AS merchant,
        COALESCE(t.category, 'Household') AS category,
        AVG(CAST(t.amount AS DOUBLE PRECISION)) AS average_amount,
        COUNT(*) AS transaction_count,
        MAX(t.transaction_date) AS last_seen
    FROM household_transactions t
    LEFT JOIN household_merchants m ON m.id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND {_current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
    GROUP BY 1, 2
    HAVING COUNT(*) >= 2
    ORDER BY average_amount DESC
    LIMIT %s
"""

_RETIREMENT_CONTRIBUTION_SQL = f"""
    SELECT AVG(month_total)
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type IN ('transfer_out', 'expense')
          AND {_current_transaction_date_predicate()}
          AND (
            COALESCE(account_label, '') ILIKE '%ira%'
            OR COALESCE(account_label, '') ILIKE '%401%'
            OR COALESCE(account_label, '') ILIKE '%roth%'
            OR COALESCE(account_label, '') ILIKE '%hsa%'
          )
        GROUP BY 1
    ) monthly_contributions
"""

_MONTH_SPEND_SQL = f"""
    SELECT COALESCE(SUM(CAST(amount AS DOUBLE PRECISION)), 0)
    FROM household_transactions t
    WHERE t.flow_type = 'expense'
      AND t.transaction_date >= date_trunc('month', CURRENT_DATE)
      AND {_current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
"""

_STATEMENT_FRESHNESS_SQL = f"""
    SELECT
        MAX(transaction_date) AS most_recent_date,
        COUNT(DISTINCT date_trunc('month', transaction_date)) AS coverage_months,
        MIN(transaction_date) AS earliest_date
    FROM household_transactions t
    WHERE t.flow_type = 'expense'
      AND {_current_transaction_date_predicate("t")}
      AND NOT {_NON_SPEND_TRANSACTION_SQL}
"""

_FUTURE_TRANSACTION_QUALITY_SQL = """
    SELECT
        COUNT(*) AS future_transaction_count,
        MIN(transaction_date) AS earliest_future_date,
        MAX(transaction_date) AS latest_future_date
    FROM household_transactions
    WHERE transaction_date > CURRENT_DATE
"""

_DOCUMENT_FUTURE_TRANSACTION_QUALITY_SQL = """
    SELECT
        COUNT(*) AS future_transaction_count,
        MIN((future_txn->>'transaction_date')::date) AS earliest_future_date,
        MAX((future_txn->>'transaction_date')::date) AS latest_future_date
    FROM household_documents d
    CROSS JOIN LATERAL jsonb_array_elements(
        COALESCE(d.metadata->'date_quality_summary'->'future_transactions', '[]'::jsonb)
    ) AS future_txn
    WHERE d.metadata->'date_quality_summary'->>'status' = 'needs_review'
      AND NOT EXISTS (
          SELECT 1
          FROM household_transactions t
          WHERE t.document_id = d.id
            AND t.transaction_date > CURRENT_DATE
      )
"""

_CONFIRMED_FACTS_SQL = """
    SELECT fact_key, fact_value
    FROM household_confirmed_facts
"""

_LATEST_TRANSACTION_DATE_SQL = {
    "document_id": """
        SELECT document_id, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE document_id IS NOT NULL
        GROUP BY document_id
    """,
    "account_label": """
        SELECT account_label, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE account_label IS NOT NULL
        GROUP BY account_label
    """,
    "household_account_id": """
        SELECT household_account_id, MAX(transaction_date) AS latest_transaction_date
        FROM household_transactions
        WHERE household_account_id IS NOT NULL
        GROUP BY household_account_id
    """,
}

_INCOME_MONTHLY_AVG_SQL = f"""
    SELECT
        COUNT(*) AS months_with_income,
        AVG(month_total) AS avg_monthly_income
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type = 'income'
          AND {_current_transaction_date_predicate()}
        GROUP BY 1
    ) monthly_income
"""


def _fetch_future_transaction_quality(storage: Any) -> dict[str, Any]:
    with storage.connection() as conn:
        transaction_row = conn.execute(_FUTURE_TRANSACTION_QUALITY_SQL).fetchone()
        document_row = conn.execute(_DOCUMENT_FUTURE_TRANSACTION_QUALITY_SQL).fetchone()
    if transaction_row is None and document_row is None:
        return {
            "future_transaction_count": 0,
            "earliest_future_date": None,
            "latest_future_date": None,
        }
    transaction_count = int(transaction_row[0] or 0) if transaction_row is not None else 0
    document_count = int(document_row[0] or 0) if document_row is not None else 0
    earliest_candidates = [
        _date_value(row[1])
        for row in (transaction_row, document_row)
        if row is not None and row[1] is not None
    ]
    latest_candidates = [
        _date_value(row[2])
        for row in (transaction_row, document_row)
        if row is not None and row[2] is not None
    ]
    return {
        "future_transaction_count": transaction_count + document_count,
        "earliest_future_date": min(earliest_candidates).isoformat() if earliest_candidates else None,
        "latest_future_date": max(latest_candidates).isoformat() if latest_candidates else None,
    }


def _gap_months(most_recent_date: date, coverage_months: int, earliest_raw: Any) -> list[str]:
    if earliest_raw is None or coverage_months <= 0:
        return []
    earliest_date = _date_value(earliest_raw)
    total_months = (
        (most_recent_date.year - earliest_date.year) * 12
        + (most_recent_date.month - earliest_date.month)
        + 1
    )
    if total_months <= coverage_months:
        return []
    gap_months_count = total_months - coverage_months
    return [f"{gap_months_count} month{'s' if gap_months_count != 1 else ''} missing in range"]


def check_statement_freshness(storage: Any) -> dict[str, Any]:
    future_quality = _fetch_future_transaction_quality(storage)
    with storage.connection() as conn:
        row = conn.execute(_STATEMENT_FRESHNESS_SQL).fetchone()
    if row is None or row[0] is None:
        return {
            "most_recent_date": None,
            "days_since_latest": None,
            "coverage_months": 0,
            "gap_months": [],
            **future_quality,
        }
    most_recent_date = _date_value(row[0])
    coverage_months = int(row[1] or 0)
    return {
        "most_recent_date": most_recent_date.isoformat(),
        "days_since_latest": _days_since(most_recent_date),
        "coverage_months": coverage_months,
        "gap_months": _gap_months(most_recent_date, coverage_months, row[2]),
        **future_quality,
    }


def fetch_confirmed_facts(storage: Any) -> dict[str, str]:
    with storage.connection() as conn:
        rows = conn.execute(_CONFIRMED_FACTS_SQL).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def fetch_categorization_queue(storage: Any, limit: int = 10) -> list[HouseholdCategorizationCandidate]:
    with storage.connection() as conn:
        rows = conn.execute(_CATEGORIZATION_SQL, [limit]).fetchall()
    return [_categorization_candidate(row) for row in rows]


def _categorization_candidate(row: Any) -> HouseholdCategorizationCandidate:
    if len(row) < 12:
        raise ValueError(f"fetch_categorization_queue: expected 12 columns, got {len(row)}")
    audit_reason = str(row[9] or "").strip()
    audit_suggested_category = str(row[10] or "").strip()
    audit_suggested_essentiality = str(row[11] or "").strip()
    merchant = str(row[1])
    description = str(row[2])
    return HouseholdCategorizationCandidate(
        id=str(row[0]),
        merchant=merchant,
        description=description,
        amount=float(row[3]),
        transaction_date=row[4].isoformat(),
        current_category=str(row[5] or "Household"),
        current_essentiality=str(row[6] or "mixed"),
        suggested_category=audit_suggested_category or suggest_category(merchant, description),
        suggested_essentiality=audit_suggested_essentiality or suggest_essentiality(merchant, description),
        confidence=float(row[7] or 0.0),
        similar_transaction_count=max(int(row[8] or 0) - 1, 0),
        reason=audit_reason or "Low-confidence classification (below 60%) needs a human pass before Jenny hardens the budget lane.",
    )


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
        cadence_info = transaction_service.infer_merchant_cadence(merchant=str(row[0])) or {}
        cadence = str(cadence_info.get("label") or "irregular")
        commitment = build_recurring_commitment(row, cadence, cadence_info, today)
        if commitment is not None:
            commitments.append(commitment)
    return commitments[:limit]


def fetch_monthly_retirement_contributions(storage: Any) -> float:
    return _fetch_scalar_float(storage, _RETIREMENT_CONTRIBUTION_SQL)


def fetch_current_month_spend(storage: Any) -> float:
    return _fetch_scalar_float(storage, _MONTH_SPEND_SQL)


def _latest_transaction_dates(storage: Any, column: str) -> dict[str, date]:
    with storage.connection() as conn:
        rows = conn.execute(_LATEST_TRANSACTION_DATE_SQL[column]).fetchall()
    latest: dict[str, date] = {}
    for key_raw, latest_raw in rows:
        key = str(key_raw).strip() if key_raw is not None else ""
        if not key or latest_raw is None:
            continue
        latest[key] = _date_value(latest_raw)
    return latest


def fetch_latest_transaction_dates_by_document(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "document_id")


def fetch_latest_transaction_dates_by_account_label(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "account_label")


def fetch_latest_transaction_dates_by_household_account(storage: Any) -> dict[str, date]:
    return _latest_transaction_dates(storage, "household_account_id")


def _confidence_for_months(month_count: int) -> float:
    if month_count <= 0:
        return 0.0
    if month_count == 1:
        return 0.6
    if month_count == 2:
        return 0.75
    return 0.85


def _build_inferences(
    avg_monthly_income: float,
    income_months: int,
    income_confidence: float,
    avg_essential: float,
    avg_discretionary: float,
    avg_savings: float,
    coverage_months: int,
    confidence: float,
) -> list[tuple[str, float, float, str]]:
    inferences: list[tuple[str, float, float, str]] = []
    if avg_monthly_income > 0:
        inferences.append((
            "monthly_net_income_target", avg_monthly_income, income_confidence,
            f"I see ~${avg_monthly_income:,.0f}/mo income across {income_months} month{'s' if income_months != 1 else ''} of deposit data.",
        ))
    if avg_essential > 0:
        inferences.append((
            "monthly_essential_target", avg_essential, confidence,
            f"I see ~${avg_essential:,.0f}/mo in essential spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))
    if avg_discretionary > 0:
        inferences.append((
            "monthly_discretionary_target", avg_discretionary, confidence,
            f"I see ~${avg_discretionary:,.0f}/mo in discretionary spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))
    if avg_savings > 0:
        total_spending = avg_essential + avg_discretionary
        inferences.append((
            "monthly_savings_target", avg_savings, min(income_confidence, confidence),
            f"Based on ~${avg_monthly_income:,.0f}/mo income minus ~${total_spending:,.0f}/mo spending, implied savings capacity is ~${avg_savings:,.0f}/mo.",
        ))
    return inferences


def _upsert_transaction_inference(
    conn: Any,
    *,
    field_name: str,
    value: float,
    confidence: float,
    rationale: str,
    existing_inferences: dict[str, dict[str, Any]],
    profile: HouseholdProfile,
) -> bool:
    if getattr(profile, field_name, None) is not None:
        return False
    existing = existing_inferences.get(field_name)
    if existing is not None:
        existing_confidence = float(existing.get("confidence") or 0.0)
        if existing_confidence >= confidence and existing.get("source", "") != "transaction_inference":
            return False
    rounded_value = round(value, 2)
    now = datetime.now(UTC).isoformat()
    metadata_json = json.dumps({"source": "transaction_inference"})
    if existing is not None and existing.get("source") == "transaction_inference":
        conn.execute(
            """
            UPDATE household_inferred_values
            SET value_text = %s, confidence = %s, rationale = %s,
                metadata = %s::jsonb, updated_at = %s
            WHERE field_name = %s
              AND metadata->>'source' = 'transaction_inference'
            """,
            [str(rounded_value), confidence, rationale, metadata_json, now, field_name],
        )
        return True
    conn.execute(
        """
        INSERT INTO household_inferred_values (
            id, field_name, value_text, confidence, status, rationale,
            source_document_id, metadata, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """,
        [
            str(uuid.uuid4()), field_name, str(rounded_value),
            confidence, "inferred", rationale, None, metadata_json, now, now,
        ],
    )
    return True


def infer_profile_from_transactions(
    storage: Any,
    *,
    profile: HouseholdProfile,
    reports: HouseholdReports,
    existing_inferences: dict[str, dict[str, Any]],
) -> None:
    coverage_months = reports.executive.coverage_months
    if coverage_months < 1:
        return
    with storage.connection() as conn:
        income_row = conn.execute(_INCOME_MONTHLY_AVG_SQL).fetchone()
    income_months = int(income_row[0] or 0) if income_row else 0
    avg_monthly_income = float(income_row[1] or 0.0) if income_row else 0.0
    avg_essential = reports.executive.average_monthly_essentials
    avg_discretionary = reports.executive.average_monthly_discretionary
    inferences = _build_inferences(
        avg_monthly_income,
        income_months,
        _confidence_for_months(income_months),
        avg_essential,
        avg_discretionary,
        max(avg_monthly_income - avg_essential - avg_discretionary, 0.0) if avg_monthly_income > 0 else 0.0,
        coverage_months,
        _confidence_for_months(coverage_months),
    )
    if not inferences:
        return
    updated = False
    with storage.connection() as conn:
        for field_name, value, conf, rationale in inferences:
            if _upsert_transaction_inference(
                conn,
                field_name=field_name,
                value=value,
                confidence=conf,
                rationale=rationale,
                existing_inferences=existing_inferences,
                profile=profile,
            ):
                updated = True
                logger.info("transaction_inference_upserted", field_name=field_name, value=round(value, 2), confidence=conf)
        if updated:
            conn.commit()


def fetch_inferred_value_rows(storage: Any) -> dict[str, dict[str, Any]]:
    with storage.connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (field_name)
                field_name, value_text, confidence, status, rationale,
                source_document_id, metadata->>'source' AS inference_source
            FROM household_inferred_values
            ORDER BY field_name, updated_at DESC
            """
        ).fetchall()
    return {
        str(row[0]): {
            "value": row[1], "confidence": row[2], "status": row[3],
            "rationale": row[4], "source_document_id": row[5],
            "source": row[6] if len(row) > 6 else None,
        }
        for row in rows
    }
