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
)
from app.services._household_dashboard_builders import (
    build_recurring_commitment,
    suggest_category,
    suggest_essentiality,
)

logger = get_logger(__name__)

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
      AND COALESCE(t.confidence, 0) < 0.60
    ORDER BY CAST(t.amount AS DOUBLE PRECISION) DESC, COALESCE(similar_txns.similar_count, 0) DESC
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


_UNKNOWN_ACCOUNT_SQL = """
    SELECT DISTINCT
        t.description,
        t.flow_type
    FROM household_transactions t
    WHERE t.flow_type IN ('transfer_out', 'payment')
    ORDER BY t.description
    LIMIT 500
"""

_STATEMENT_FRESHNESS_SQL = """
    SELECT
        MAX(transaction_date) AS most_recent_date,
        COUNT(DISTINCT date_trunc('month', transaction_date)) AS coverage_months,
        MIN(transaction_date) AS earliest_date
    FROM household_transactions
    WHERE flow_type = 'expense'
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
        institution = match.group(0).split()[0].upper()
        # Normalize multi-word institutions
        for known in _KNOWN_INSTITUTIONS:
            if known.upper() in description.upper():
                institution = known
                break
        partial_account = match.group(1) or ""
        key = f"{institution}_{partial_account}" if partial_account else institution

        # Skip if this matches a known document
        if institution in known_labels:
            continue
        if partial_account and partial_account in known_hints:
            continue

        if key not in detected:
            detected[key] = {
                "institution": institution,
                "partial_account": partial_account,
                "key": key,
            }

    return list(detected.values())


def check_statement_freshness(storage: Any) -> dict[str, Any]:
    """Check transaction coverage freshness."""
    with storage.connection() as conn:
        row = conn.execute(_STATEMENT_FRESHNESS_SQL).fetchone()

    if row is None or row[0] is None:
        return {
            "most_recent_date": None,
            "days_since_latest": None,
            "coverage_months": 0,
            "gap_months": [],
        }

    most_recent = row[0]
    coverage_months = int(row[1] or 0)
    earliest = row[2]
    today = datetime.now(UTC).date()
    most_recent_date = most_recent.date() if hasattr(most_recent, "date") else most_recent
    days_since_latest = (today - most_recent_date).days

    # Calculate gap months
    gap_months: list[str] = []
    if earliest is not None and coverage_months > 0:
        earliest_date = earliest.date() if hasattr(earliest, "date") else earliest
        total_months = (most_recent_date.year - earliest_date.year) * 12 + (most_recent_date.month - earliest_date.month) + 1
        if total_months > coverage_months:
            gap_months_count = total_months - coverage_months
            gap_months = [f"{gap_months_count} month{'s' if gap_months_count != 1 else ''} missing in range"]

    return {
        "most_recent_date": most_recent_date.isoformat(),
        "days_since_latest": days_since_latest,
        "coverage_months": coverage_months,
        "gap_months": gap_months,
    }


def fetch_confirmed_facts(storage: Any) -> dict[str, str]:
    """Fetch all confirmed household facts as a dict."""
    with storage.connection() as conn:
        rows = conn.execute(_CONFIRMED_FACTS_SQL).fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def fetch_categorization_queue(
    storage: Any,
    limit: int = 10,
) -> list[HouseholdCategorizationCandidate]:
    # _CATEGORIZATION_SQL always returns exactly 9 columns:
    # 0:id, 1:merchant, 2:description, 3:amount, 4:transaction_date,
    # 5:category, 6:essentiality, 7:confidence, 8:similar_count
    expected_columns = 9
    with storage.connection() as conn:
        rows = conn.execute(_CATEGORIZATION_SQL, [limit]).fetchall()
    results: list[HouseholdCategorizationCandidate] = []
    for row in rows:
        if len(row) < expected_columns:
            raise ValueError(
                f"fetch_categorization_queue: expected {expected_columns} columns, got {len(row)}"
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
    with storage.connection() as conn:
        row = conn.execute(_RETIREMENT_CONTRIBUTION_SQL).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0


def fetch_current_month_spend(storage: Any) -> float:
    with storage.connection() as conn:
        row = conn.execute(_MONTH_SPEND_SQL).fetchone()
    return round(float(row[0] or 0.0), 2) if row is not None else 0.0


# ---------------------------------------------------------------------------
# Transaction-based profile field inference
# ---------------------------------------------------------------------------

_INCOME_MONTHLY_AVG_SQL = """
    SELECT
        COUNT(*) AS months_with_income,
        AVG(month_total) AS avg_monthly_income
    FROM (
        SELECT
            date_trunc('month', transaction_date) AS month_bucket,
            SUM(CAST(amount AS DOUBLE PRECISION)) AS month_total
        FROM household_transactions
        WHERE flow_type = 'income'
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
    manual_value = getattr(profile, field_name, None)
    if manual_value is not None:
        return False

    existing = existing_inferences.get(field_name)
    if existing is not None:
        existing_confidence = float(existing.get("confidence") or 0.0)
        existing_source = existing.get("source", "")
        # Don't overwrite higher-confidence inferences from document review
        if existing_confidence >= confidence and existing_source != "transaction_inference":
            return False

    rounded_value = round(value, 2)
    now = datetime.now(UTC).isoformat()
    metadata_json = json.dumps({"source": "transaction_inference"})

    if existing is not None and existing.get("source") == "transaction_inference":
        # Update existing transaction inference row
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
                str(uuid.uuid4()),
                field_name,
                str(rounded_value),
                confidence,
                "inferred",
                rationale,
                None,
                metadata_json,
                now,
                now,
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
    """Infer profile field values from transaction data and upsert into household_inferred_values.

    Uses the reports executive summary for expense averages, and queries income
    transactions directly. Only writes inferences when no manual value exists and
    no existing inference has higher confidence.
    """
    coverage_months = reports.executive.coverage_months
    if coverage_months < 1:
        return

    confidence = _confidence_for_months(coverage_months)

    # Query income from transactions directly
    with storage.connection() as conn:
        income_row = conn.execute(_INCOME_MONTHLY_AVG_SQL).fetchone()
        income_months = int(income_row[0] or 0) if income_row else 0
        avg_monthly_income = float(income_row[1] or 0.0) if income_row else 0.0
        income_confidence = _confidence_for_months(income_months)

    avg_essential = reports.executive.average_monthly_essentials
    avg_discretionary = reports.executive.average_monthly_discretionary
    total_spending = avg_essential + avg_discretionary

    # Calculate savings as income minus total spending (only if we have income data)
    avg_savings = max(avg_monthly_income - total_spending, 0.0) if avg_monthly_income > 0 else 0.0

    inferences: list[tuple[str, float, float, str]] = []

    if avg_monthly_income > 0:
        inferences.append((
            "monthly_net_income_target",
            avg_monthly_income,
            income_confidence,
            f"I see ~${avg_monthly_income:,.0f}/mo income across {income_months} month{'s' if income_months != 1 else ''} of deposit data.",
        ))

    if avg_essential > 0:
        inferences.append((
            "monthly_essential_target",
            avg_essential,
            confidence,
            f"I see ~${avg_essential:,.0f}/mo in essential spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))

    if avg_discretionary > 0:
        inferences.append((
            "monthly_discretionary_target",
            avg_discretionary,
            confidence,
            f"I see ~${avg_discretionary:,.0f}/mo in discretionary spending across {coverage_months} month{'s' if coverage_months != 1 else ''} of transaction data.",
        ))

    if avg_savings > 0:
        inferences.append((
            "monthly_savings_target",
            avg_savings,
            min(income_confidence, confidence),
            f"Based on ~${avg_monthly_income:,.0f}/mo income minus ~${total_spending:,.0f}/mo spending, implied savings capacity is ~${avg_savings:,.0f}/mo.",
        ))

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
                logger.info(
                    "transaction_inference_upserted",
                    field_name=field_name,
                    value=round(value, 2),
                    confidence=conf,
                )
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
