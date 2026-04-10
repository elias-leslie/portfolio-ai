"""Database query helpers for the household dashboard (require storage access)."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdCategorizationCandidate,
    HouseholdProfile,
    HouseholdRecurringCommitment,
    HouseholdReports,
    HouseholdTransactionDateIssue,
)
from app.services._household_dashboard_builders import (
    build_recurring_commitment,
    suggest_category,
    suggest_essentiality,
)

logger = get_logger(__name__)

def _current_transaction_date_predicate(alias: str | None = None) -> str:
    qualifier = f"{alias}." if alias else ""
    return f"{qualifier}transaction_date <= CURRENT_DATE"


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
        COALESCE(similar_txns.similar_count, 0) AS similar_count
    FROM household_transactions t
    LEFT JOIN (
        SELECT merchant_id, COUNT(*) AS similar_count
        FROM household_transactions
        WHERE flow_type = 'expense'
          AND {_current_transaction_date_predicate()}
        GROUP BY merchant_id
    ) similar_txns ON similar_txns.merchant_id = t.merchant_id
    WHERE t.flow_type = 'expense'
      AND {_current_transaction_date_predicate("t")}
      AND COALESCE(t.confidence, 0) < 0.60
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
    FROM household_transactions
    WHERE flow_type = 'expense'
      AND transaction_date >= date_trunc('month', CURRENT_DATE)
      AND {_current_transaction_date_predicate()}
"""

_UNKNOWN_ACCOUNT_SQL = f"""
    SELECT DISTINCT
        t.description,
        t.flow_type
    FROM household_transactions t
    WHERE t.flow_type IN ('transfer_out', 'payment')
      AND {_current_transaction_date_predicate("t")}
    ORDER BY t.description
    LIMIT 500
"""

_STATEMENT_FRESHNESS_SQL = f"""
    SELECT
        MAX(transaction_date) AS most_recent_date,
        COUNT(DISTINCT date_trunc('month', transaction_date)) AS coverage_months,
        MIN(transaction_date) AS earliest_date
    FROM household_transactions
    WHERE flow_type = 'expense'
      AND {_current_transaction_date_predicate()}
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

_CONFIRMED_FACTS_SQL = """
    SELECT fact_key, fact_value
    FROM household_confirmed_facts
"""

_KNOWN_INSTITUTIONS = [
    "CHASE", "AMEX", "DISCOVER", "CITI", "CAPITAL ONE", "BANK OF AMERICA",
    "AMERICAN EXPRESS", "WELLS FARGO", "BARCLAYS", "US BANK", "PNC",
    "TD BANK", "NAVY FEDERAL", "USAA", "FIDELITY", "SCHWAB", "VANGUARD",
]

_INSTITUTION_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(inst) for inst in _KNOWN_INSTITUTIONS) + r")"
    r"(?:\s*(?:X+|[*]+)?\s*(\d{4}))?\b",
    re.IGNORECASE,
)


def _fetch_scalar_float(storage: Any, sql: str) -> float:
    """Execute a scalar-aggregate SQL query and return the result as a rounded float."""
    with storage.connection() as conn:
        row = conn.execute(sql).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0


def _date_value(value: Any) -> Any:
    return value.date() if hasattr(value, "date") else value


def _date_iso(value: Any) -> str | None:
    date_value = _date_value(value)
    return date_value.isoformat() if date_value is not None else None


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


def _short_excerpt(value: Any, *, max_length: int = 220) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split())
    if not compact:
        return None
    return compact[: max_length - 1] + "…" if len(compact) > max_length else compact


def _float_or_zero(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _canonicalize_institution(description: str, fallback: str) -> str:
    """Return the matching known institution name for *description*, or *fallback*."""
    desc_upper = description.upper()
    for known in _KNOWN_INSTITUTIONS:
        if known.upper() in desc_upper:
            return known
    return fallback


def detect_unknown_accounts(
    storage: Any,
    documents: list[Any],
) -> list[dict[str, str]]:
    """Detect references to external accounts in transaction descriptions not matched to any document."""
    with storage.connection() as conn:
        rows = conn.execute(_UNKNOWN_ACCOUNT_SQL).fetchall()

    known_labels: set[str] = set()
    known_hints: set[str] = set()
    for doc in documents:
        if hasattr(doc, "account_label") and doc.account_label:
            known_labels.add(doc.account_label.upper())
        meta = getattr(doc, "metadata", {}) or {}
        if isinstance(meta, dict):
            hint = meta.get("account_hint", "")
            if hint:
                known_hints.add(str(hint).upper())
            inst = meta.get("institution", "")
            if inst:
                known_labels.add(str(inst).upper())

    detected: dict[str, dict[str, str]] = {}
    for row in rows:
        description = str(row[0] or "")
        match = _INSTITUTION_PATTERN.search(description)
        if not match:
            continue
        institution = _canonicalize_institution(description, match.group(0).split()[0].upper())
        partial_account = match.group(1) or ""
        key = f"{institution}_{partial_account}" if partial_account else institution

        if institution in known_labels:
            continue
        if partial_account and partial_account in known_hints:
            continue
        if key not in detected:
            detected[key] = {"institution": institution, "partial_account": partial_account, "key": key}

    return list(detected.values())


def check_statement_freshness(storage: Any) -> dict[str, Any]:
    """Check transaction coverage freshness."""
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
    days_since_latest = (datetime.now(UTC).date() - most_recent_date).days

    gap_months: list[str] = []
    if row[2] is not None and coverage_months > 0:
        earliest_date = _date_value(row[2])
        total_months = (
            (most_recent_date.year - earliest_date.year) * 12
            + (most_recent_date.month - earliest_date.month)
            + 1
        )
        if total_months > coverage_months:
            gap_months_count = total_months - coverage_months
            gap_months = [f"{gap_months_count} month{'s' if gap_months_count != 1 else ''} missing in range"]

    return {
        "most_recent_date": most_recent_date.isoformat(),
        "days_since_latest": days_since_latest,
        "coverage_months": coverage_months,
        "gap_months": gap_months,
        **future_quality,
    }


def fetch_transaction_date_issues(storage: Any, limit: int = 12) -> list[HouseholdTransactionDateIssue]:
    """Return transactions whose extracted dates are after today and need review."""
    with storage.connection() as conn:
        rows = conn.execute(_TRANSACTION_DATE_ISSUES_SQL, [limit]).fetchall()
        document_rows = conn.execute(_DOCUMENT_DATE_ISSUES_SQL, [limit]).fetchall()

    issues: list[HouseholdTransactionDateIssue] = []
    for row in rows:
        transaction_date = _date_iso(row[5])
        if transaction_date is None:
            continue
        issues.append(
            HouseholdTransactionDateIssue(
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
        )
    existing_document_ids = {issue.document_id for issue in issues}
    remaining_limit = max(limit - len(issues), 0)
    for row in document_rows:
        if len(issues) >= limit:
            break
        document_id = str(row[0])
        if document_id in existing_document_ids:
            continue
        future_transactions = row[5] if isinstance(row[5], list) else []
        for index, transaction in enumerate(future_transactions[:remaining_limit]):
            if not isinstance(transaction, dict):
                continue
            transaction_date = str(transaction.get("transaction_date") or "")
            if not transaction_date:
                continue
            issues.append(
                HouseholdTransactionDateIssue(
                    id=f"future-date-document-{document_id}-{index}",
                    transaction_id=None,
                    document_id=document_id,
                    filename=str(row[1]),
                    source_type=str(row[2]),
                    document_type=str(row[3]),
                    transaction_date=transaction_date,
                    uploaded_at=_date_iso(row[4]),
                    merchant=str(transaction.get("merchant") or "Unknown merchant"),
                    description=str(transaction.get("description") or "Future-dated transaction"),
                    amount=round(_float_or_zero(transaction.get("amount")), 2),
                    account_label=(
                        str(transaction.get("account_label"))
                        if transaction.get("account_label")
                        else None
                    ),
                    confidence=(
                        _float_or_zero(transaction.get("confidence"))
                        if transaction.get("confidence") is not None
                        else None
                    ),
                    reason="Extracted transaction date is after today, so Jenny held it out instead of inserting it into the current ledger.",
                    source_excerpt=_short_excerpt(row[6]),
                )
            )
            if len(issues) >= limit:
                break
    return issues


def fetch_confirmed_facts(storage: Any) -> dict[str, str]:
    """Fetch all confirmed household facts as a dict."""
    with storage.connection() as conn:
        rows = conn.execute(_CONFIRMED_FACTS_SQL).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def fetch_categorization_queue(
    storage: Any,
    limit: int = 10,
) -> list[HouseholdCategorizationCandidate]:
    with storage.connection() as conn:
        rows = conn.execute(_CATEGORIZATION_SQL, [limit]).fetchall()
    results: list[HouseholdCategorizationCandidate] = []
    for row in rows:
        if len(row) < 9:
            raise ValueError(
                f"fetch_categorization_queue: expected 9 columns, got {len(row)}"
            )
        results.append(
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
                reason="Low-confidence classification (below 60%) needs a human pass before Jenny hardens the budget lane.",
            )
        )
    return results


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
    return _fetch_scalar_float(storage, _RETIREMENT_CONTRIBUTION_SQL)


def fetch_current_month_spend(storage: Any) -> float:
    return _fetch_scalar_float(storage, _MONTH_SPEND_SQL)


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


def _confidence_for_months(month_count: int) -> float:
    """Scale confidence with data coverage: 1 month=0.6, 2 months=0.75, 3+=0.85."""
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
    """Assemble (field_name, value, confidence, rationale) tuples from computed averages."""
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
    """Upsert a transaction-inferred value if no manual value exists and no higher-confidence inference exists."""
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
    else:
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
    """Infer profile field values from transaction data and upsert into household_inferred_values."""
    coverage_months = reports.executive.coverage_months
    if coverage_months < 1:
        return

    confidence = _confidence_for_months(coverage_months)
    with storage.connection() as conn:
        income_row = conn.execute(_INCOME_MONTHLY_AVG_SQL).fetchone()
        income_months = int(income_row[0] or 0) if income_row else 0
        avg_monthly_income = float(income_row[1] or 0.0) if income_row else 0.0
        income_confidence = _confidence_for_months(income_months)

    avg_essential = reports.executive.average_monthly_essentials
    avg_discretionary = reports.executive.average_monthly_discretionary
    avg_savings = max(avg_monthly_income - avg_essential - avg_discretionary, 0.0) if avg_monthly_income > 0 else 0.0

    inferences = _build_inferences(
        avg_monthly_income, income_months, income_confidence,
        avg_essential, avg_discretionary, avg_savings,
        coverage_months, confidence,
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
    """Return latest inferred value row per field_name, keyed by field_name."""
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
