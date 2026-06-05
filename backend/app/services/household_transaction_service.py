"""Household transaction extraction, merchant normalization, and report generation."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, date, datetime
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdReports,
    HouseholdSpendingCategory,
    HouseholdSpendingSummary,
    HouseholdSpendingTransaction,
    HouseholdSpendingView,
)
from app.services._household_merchants import (
    _canonical_merchant_name,
    _classification_for_flow,
    _effective_transaction_classification,
    _effective_transaction_flow,
)
from app.services._household_report_builder import (
    _merchant_aliases,
    _merchant_root,
    build_household_reports,
    collapse_report_rows,
)
from app.services._household_spend_filters import (
    investment_activity_sql_predicate,
    is_budget_driving_expense,
)
from app.services._household_time_windows import resolve_household_time_window
from app.services._household_transaction_parsers import (
    _parse_date_value,
    extract_transactions,
)
from app.services.household_account_identity import (
    account_masks_match,
    derive_account_mask,
)
from app.storage import get_storage

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Confidence level assigned to manually classified transactions.
MANUAL_RULE_CONFIDENCE = 0.90
CATEGORIZATION_VERSION = "2026-05-canonical"

# Cadence inference thresholds (median interval in days)
WEEKLY_INTERVAL_MAX = 10
BIWEEKLY_INTERVAL_MAX = 20
MONTHLY_INTERVAL_MAX = 45

# Minimum observed dates needed before inferring a provisional billing cadence
MIN_DATES_FOR_CADENCE = 2

# Cadence confidence based on sample size
CADENCE_CONFIDENCE_EARLY = 0.62  # exactly 2 observations
CADENCE_CONFIDENCE_MINIMAL = 0.72  # exactly 3 observations
CADENCE_CONFIDENCE_STANDARD = 0.82  # more than 3 observations

UNKNOWN_CATEGORY = "Unknown"
UNKNOWN_ESSENTIALITY = "mixed"
UNKNOWN_CATEGORY_LABELS = {"", "unknown", "uncategorized", "uncategorised", "needs review"}
CATEGORY_REVIEW_CONFIDENCE_THRESHOLD = 0.60


def _looks_like_mask_only(value: str | None) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value.strip())
    if len(cleaned) < 4:
        return False
    return " " not in value.strip() and any(char.isdigit() for char in cleaned)


def _row_value(row: Any, index: int, default: Any = None) -> Any:
    try:
        return row[index]
    except IndexError:
        return default


def _transaction_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _metadata_text(metadata: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return str(value).strip()
    return None


def _metadata_float(metadata: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metadata.get(key)
        if value in (None, "", [], {}):
            continue
        try:
            return float(str(value).replace(",", "").strip())
        except ValueError:
            continue
    return None


def _needs_category_review(
    *,
    stored_category: str | None,
    effective_category: str,
    confidence: float | None,
    metadata: dict[str, Any],
) -> bool:
    audit = metadata.get("audit")
    if isinstance(audit, dict) and audit.get("status") == "needs_review":
        return True
    if confidence is not None and confidence < CATEGORY_REVIEW_CONFIDENCE_THRESHOLD:
        return True

    stored_key = (stored_category or "").strip().lower()
    effective_key = effective_category.strip().lower()
    if stored_key in UNKNOWN_CATEGORY_LABELS and effective_key in {
        "household",
        "uncategorized",
        "unknown",
        "",
    }:
        return True
    return stored_key in UNKNOWN_CATEGORY_LABELS - {""}


# ---------------------------------------------------------------------------
# Service class (10 methods)
# ---------------------------------------------------------------------------


class HouseholdTransactionService:
    """Persist normalized household transactions and generate reporting views."""

    def __init__(self) -> None:
        self.storage = get_storage()

    def import_document_transactions(
        self,
        *,
        document: Any,
        reviewed: dict[str, Any],
    ) -> dict[str, int]:
        extracted_text = reviewed.get("extracted_text")
        if not isinstance(extracted_text, str):
            extracted_text = ""

        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}

        stored_path = self._document_stored_path(document)
        effective_account_label = self._resolved_account_label(
            document_label=getattr(document, "account_label", None),
            structured_data=structured_data,
        )

        transactions = extract_transactions(
            filename=document.filename,
            source_type=str(reviewed.get("source_type") or document.source_type),
            document_type=str(reviewed.get("document_type") or document.document_type),
            extracted_text=extracted_text,
            structured_data=structured_data,
            account_label=effective_account_label,
            review_summary=str(reviewed.get("summary") or ""),
            stored_path=stored_path,
        )
        if not transactions:
            return {"inserted": 0, "updated": 0}

        today = datetime.now(UTC).date()
        date_issues = [
            transaction
            for transaction in transactions
            if transaction.transaction_date > today
        ]
        transactions = [
            transaction
            for transaction in transactions
            if transaction.transaction_date <= today
        ]

        inserted = 0
        updated = 0
        deleted = 0
        now = datetime.now(UTC).isoformat()
        current_row_hashes: set[str] = set()

        with self.storage.connection() as conn:
            for transaction in transactions:
                transaction_metadata = transaction.metadata or {}
                original_category = transaction.category
                (
                    merchant_id,
                    canonical_name,
                    category,
                    essentiality,
                    has_manual_rule,
                    rule_id,
                ) = self._resolve_merchant(
                    conn=conn,
                    raw_merchant=transaction.raw_merchant or transaction.description,
                    category=transaction.category,
                    essentiality=transaction.essentiality,
                )
                applied_rule_id = rule_id
                categorization_source = "merchant_rule" if has_manual_rule else (
                    _metadata_text(transaction_metadata, "source") or "parser"
                )
                if transaction.flow_type in {"income", "payment", "transfer_in", "transfer_out", "investment"}:
                    category, essentiality = _classification_for_flow(
                        raw_merchant=transaction.raw_merchant or transaction.description,
                        description=transaction.description,
                        amount=float(transaction.amount),
                        flow_type=transaction.flow_type,
                    )
                    applied_rule_id = None
                    categorization_source = "flow_classifier"
                # Auto-apply prior manual categorization with high confidence
                if has_manual_rule:
                    transaction.confidence = max(transaction.confidence, MANUAL_RULE_CONFIDENCE)
                effective_account_label = transaction.account_label or document.account_label
                household_account_id = self._resolve_transaction_account_id(
                    conn,
                    account_label=effective_account_label,
                    metadata=transaction_metadata,
                )
                source_system = (
                    _metadata_text(transaction_metadata, "source")
                    or str(reviewed.get("source_type") or document.source_type or "")
                    or None
                )
                external_transaction_id = _metadata_text(
                    transaction_metadata,
                    "plaid_transaction_id",
                    "fitid",
                    "trace_number",
                    "auth_code",
                    "external_transaction_id",
                )
                balance_after = _metadata_float(transaction_metadata, "balance_after")
                row_hash = hashlib.sha256(
                    "|".join([
                        document.id,
                        transaction.transaction_date.isoformat(),
                        canonical_name.lower(),
                        transaction.description.lower(),
                        f"{transaction.amount:.4f}",
                        transaction.flow_type,
                    ]).encode("utf-8")
                ).hexdigest()
                current_row_hashes.add(row_hash)
                metadata = {
                    "filename": document.filename,
                    "canonical_name": canonical_name,
                    **transaction_metadata,
                }
                result = conn.execute(
                    """
                    INSERT INTO household_transactions (
                        id, document_id, household_account_id, merchant_id, row_hash,
                        transaction_date, posted_date, description, raw_merchant, account_label,
                        amount, currency, flow_type, category, essentiality, confidence,
                        metadata, source_system, external_transaction_id, original_category,
                        categorization_source, categorization_version, category_updated_at,
                        category_updated_by, transaction_rule_id, balance_after, pending,
                        removed, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE,
                        FALSE, %s, %s
                    )
                    ON CONFLICT (row_hash) DO UPDATE SET
                        household_account_id = COALESCE(EXCLUDED.household_account_id, household_transactions.household_account_id),
                        merchant_id = COALESCE(EXCLUDED.merchant_id, household_transactions.merchant_id),
                        posted_date = COALESCE(EXCLUDED.posted_date, household_transactions.posted_date),
                        description = EXCLUDED.description,
                        raw_merchant = COALESCE(EXCLUDED.raw_merchant, household_transactions.raw_merchant),
                        account_label = COALESCE(EXCLUDED.account_label, household_transactions.account_label),
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        flow_type = EXCLUDED.flow_type,
                        category = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.category
                            ELSE COALESCE(EXCLUDED.category, household_transactions.category)
                        END,
                        essentiality = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.essentiality
                            ELSE COALESCE(EXCLUDED.essentiality, household_transactions.essentiality)
                        END,
                        confidence = GREATEST(
                            COALESCE(household_transactions.confidence, 0),
                            COALESCE(EXCLUDED.confidence, 0)
                        ),
                        metadata = household_transactions.metadata || EXCLUDED.metadata,
                        source_system = COALESCE(EXCLUDED.source_system, household_transactions.source_system),
                        external_transaction_id = COALESCE(EXCLUDED.external_transaction_id, household_transactions.external_transaction_id),
                        original_category = COALESCE(household_transactions.original_category, EXCLUDED.original_category),
                        categorization_source = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.categorization_source
                            ELSE COALESCE(EXCLUDED.categorization_source, household_transactions.categorization_source)
                        END,
                        categorization_version = COALESCE(EXCLUDED.categorization_version, household_transactions.categorization_version),
                        category_updated_at = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.category_updated_at
                            ELSE EXCLUDED.category_updated_at
                        END,
                        category_updated_by = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.category_updated_by
                            ELSE EXCLUDED.category_updated_by
                        END,
                        transaction_rule_id = CASE
                            WHEN household_transactions.categorization_source IN ('manual', 'manual_rule', 'merchant_rule')
                                THEN household_transactions.transaction_rule_id
                            ELSE COALESCE(EXCLUDED.transaction_rule_id, household_transactions.transaction_rule_id)
                        END,
                        balance_after = COALESCE(EXCLUDED.balance_after, household_transactions.balance_after),
                        pending = FALSE,
                        removed = FALSE,
                        updated_at = EXCLUDED.updated_at
                    RETURNING xmax = 0
                    """,
                    [
                        str(uuid.uuid4()),
                        document.id,
                        household_account_id,
                        merchant_id,
                        row_hash,
                        datetime.combine(transaction.transaction_date, datetime.min.time(), tzinfo=UTC),
                        (
                            datetime.combine(transaction.posted_date, datetime.min.time(), tzinfo=UTC)
                            if transaction.posted_date is not None
                            else None
                        ),
                        transaction.description,
                        transaction.raw_merchant,
                        effective_account_label,
                        transaction.amount,
                        transaction.currency,
                        transaction.flow_type,
                        category,
                        essentiality,
                        transaction.confidence,
                        json.dumps(metadata),
                        source_system,
                        external_transaction_id,
                        original_category,
                        categorization_source,
                        CATEGORIZATION_VERSION,
                        now,
                        categorization_source,
                        applied_rule_id,
                        balance_after,
                        now,
                        now,
                    ],
                ).fetchone()
                if result and bool(result[0]):
                    inserted += 1
                else:
                    updated += 1

            deleted = len(
                conn.execute(
                    """
                    DELETE FROM household_transactions
                    WHERE document_id = %s
                      AND row_hash <> ALL(%s)
                    RETURNING id
                    """,
                    [
                        document.id,
                        list(current_row_hashes) if current_row_hashes else [""],
                    ],
                ).fetchall()
            )

            conn.execute(
                """
                UPDATE household_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                [
                    json.dumps(
                        {
                            "transaction_import_summary": {
                                "inserted": inserted,
                                "updated": updated,
                                "deleted": deleted,
                                "held_for_date_review": len(date_issues),
                            },
                            "date_quality_summary": (
                                {
                                    "status": "needs_review",
                                    "future_transaction_count": len(date_issues),
                                    "latest_future_date": max(
                                        issue.transaction_date for issue in date_issues
                                    ).isoformat(),
                                    "future_transactions": [
                                        {
                                            "transaction_date": issue.transaction_date.isoformat(),
                                            "merchant": issue.raw_merchant or issue.description,
                                            "description": issue.description,
                                            "amount": str(issue.amount),
                                            "account_label": issue.account_label,
                                            "confidence": issue.confidence,
                                        }
                                        for issue in date_issues[:12]
                                    ],
                                }
                                if date_issues
                                else {
                                    "status": "clear",
                                    "future_transaction_count": 0,
                                    "future_transactions": [],
                                }
                            ),
                        }
                    ),
                    document.id,
                ],
            )
            conn.commit()

        return {
            "inserted": inserted,
            "updated": updated,
            "deleted": deleted,
            "held_for_date_review": len(date_issues),
        }

    def backfill_from_latest_reviews(self, *, limit: int = 24) -> dict[str, int]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    d.id,
                    d.filename,
                    d.source_type,
                    d.document_type,
                    d.account_label,
                    COALESCE(r.summary, d.review_summary) AS summary,
                    r.extracted_text,
                    r.structured_data
                FROM household_documents d
                JOIN LATERAL (
                    SELECT summary, extracted_text, structured_data
                    FROM household_document_reviews
                    WHERE document_id = d.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) r ON TRUE
                WHERE d.source_type IN ('bank', 'credit_card', 'brokerage', 'receipt')
                  AND NOT EXISTS (
                      SELECT 1
                      FROM household_transactions t
                      WHERE t.document_id = d.id
                  )
                ORDER BY d.uploaded_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()

        inserted = 0
        updated = 0
        for row in rows:
            result = self.import_document_transactions(
                document=SimpleNamespace(
                    id=str(row[0]),
                    filename=str(row[1]),
                    source_type=str(row[2]),
                    document_type=str(row[3]),
                    account_label=str(row[4]) if row[4] is not None else None,
                ),
                reviewed={
                    "summary": row[5],
                    "extracted_text": row[6] if isinstance(row[6], str) else "",
                    "structured_data": row[7] if isinstance(row[7], dict) else {},
                    "source_type": row[2],
                    "document_type": row[3],
                },
            )
            inserted += result["inserted"]
            updated += result["updated"]
        return {"inserted": inserted, "updated": updated}

    def repair_transaction_system(self, *, limit: int = 5000) -> dict[str, int]:
        """Repair canonical categories, provenance fields, account links, and doc summaries."""
        with self.storage.connection() as conn:
            canonicalized = self._canonicalize_stored_categories(conn, limit=limit)
            rules_backfilled = self._backfill_merchant_rules(conn, limit=limit)
            provenance_backfilled = self._backfill_transaction_provenance(conn)
            account_linked = self._link_transactions_by_account_mask(conn, limit=limit)
            application_summaries_repaired = self._repair_application_summaries(
                conn,
                limit=limit,
            )
            conn.commit()
        return {
            "canonicalized": canonicalized,
            "rules_backfilled": rules_backfilled,
            "provenance_backfilled": provenance_backfilled,
            "account_linked": account_linked,
            "application_summaries_repaired": application_summaries_repaired,
        }

    def build_reports(self) -> HouseholdReports:
        return build_household_reports(
            report_rows=self._load_report_rows(),
            cadence_for_dates=self._dates_to_cadence,
            merchant_recommendation=self._merchant_recommendation,
        )

    def _spend_rows_between(
        self,
        *,
        start_date: date | None,
        end_date: date,
    ) -> list[dict[str, Any]]:
        report_rows = self._load_report_rows()
        filtered_rows = [
            row
            for row in report_rows
            if row["date"] <= end_date
            and (start_date is None or row["date"] >= start_date)
        ]
        analytics_rows = [
            row for row in filtered_rows if row.get("source_kind") != "import"
        ]
        return [
            row
            for row in collapse_report_rows(analytics_rows)
            if abs(float(row.get("signed_amount", row["amount"]))) > 0
        ]

    def spend_total_between(
        self,
        *,
        start_date: date | None,
        end_date: date,
    ) -> float:
        return round(
            sum(
                float(row.get("signed_amount", row["amount"]))
                for row in self._spend_rows_between(
                    start_date=start_date,
                    end_date=end_date,
                )
            ),
            2,
        )

    def _income_total_between(
        self,
        *,
        start_date: date | None,
        end_date: date,
    ) -> float:
        """Sum household income inflow in the window, excluding brokerage activity."""
        where = ["t.flow_type = 'income'", "t.removed IS NOT TRUE", "t.transaction_date <= %s"]
        params: list[Any] = [end_date]
        if start_date is not None:
            where.append("t.transaction_date >= %s")
            params.append(start_date)
        investment_predicate = investment_activity_sql_predicate(
            text_expressions=["t.description", "t.raw_merchant"],
        )
        sql = f"""
            SELECT COALESCE(SUM(CAST(t.amount AS DOUBLE PRECISION)), 0)
            FROM household_transactions t
            WHERE {" AND ".join(where)}
              AND NOT {investment_predicate}
        """
        with self.storage.connection() as conn:
            result = conn.execute(sql, params).fetchone()
        return float(result[0]) if result and result[0] is not None else 0.0

    def build_spending_view(self, *, window: str = "1m") -> HouseholdSpendingView:
        timeframe = resolve_household_time_window(window)
        spend_rows = self._spend_rows_between(
            start_date=timeframe.start_date,
            end_date=timeframe.end_date,
        )

        if not spend_rows:
            return HouseholdSpendingView(
                generated_at=datetime.now(UTC).isoformat(),
                summary=HouseholdSpendingSummary(
                    timeframe_key=timeframe.key,
                    timeframe_label=timeframe.label,
                    start_date=timeframe.start_date.isoformat() if timeframe.start_date else None,
                    end_date=timeframe.end_date.isoformat(),
                ),
            )

        monthly_totals: dict[str, float] = {}
        monthly_counts: dict[str, int] = {}
        category_totals: dict[tuple[str, str], float] = {}
        category_gross: dict[tuple[str, str], float] = {}
        category_refund: dict[tuple[str, str], float] = {}
        category_counts: dict[tuple[str, str], int] = {}
        category_monthly_totals: dict[tuple[str, str, str], float] = {}
        category_monthly_counts: dict[tuple[str, str, str], int] = {}
        account_labels = {
            str(row["account_label"]).strip()
            for row in spend_rows
            if row.get("account_label")
        }
        current_month_key = timeframe.end_date.strftime("%Y-%m")

        for row in spend_rows:
            month_key = row["date"].strftime("%Y-%m")
            signed_amount = float(row.get("signed_amount", row["amount"]))
            # A refund posts as a negative signed_amount; keep gross spend and refund
            # credits apart so caps key off gross, not net.
            gross = max(signed_amount, 0.0)
            refund = max(-signed_amount, 0.0)
            monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + signed_amount
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            category_key = (str(row["category"]), str(row["essentiality"]))
            category_totals[category_key] = category_totals.get(category_key, 0.0) + signed_amount
            category_gross[category_key] = category_gross.get(category_key, 0.0) + gross
            category_refund[category_key] = category_refund.get(category_key, 0.0) + refund
            category_counts[category_key] = category_counts.get(category_key, 0) + 1
            category_month_key = (month_key, str(row["category"]), str(row["essentiality"]))
            category_monthly_totals[category_month_key] = (
                category_monthly_totals.get(category_month_key, 0.0) + signed_amount
            )
            category_monthly_counts[category_month_key] = (
                category_monthly_counts.get(category_month_key, 0) + 1
            )

        coverage_months = (
            timeframe.window_months
            if timeframe.window_months is not None
            else max(len(monthly_totals), 1)
        )
        total_spend = round(
            sum(float(row.get("signed_amount", row["amount"])) for row in spend_rows),
            2,
        )
        gross_spend = round(sum(category_gross.values()), 2)
        refund_total = round(sum(category_refund.values()), 2)
        month_to_date_spend = round(monthly_totals.get(current_month_key, 0.0), 2)
        total_income = self._income_total_between(
            start_date=timeframe.start_date,
            end_date=timeframe.end_date,
        )
        average_monthly_income = round(total_income / coverage_months, 2)
        net_cash_flow = round(total_income - total_spend, 2)
        savings_rate = (
            round(net_cash_flow / total_income, 4) if total_income > 0 else None
        )

        return HouseholdSpendingView(
            generated_at=datetime.now(UTC).isoformat(),
            summary=HouseholdSpendingSummary(
                timeframe_key=timeframe.key,
                timeframe_label=timeframe.label,
                start_date=timeframe.start_date.isoformat() if timeframe.start_date else None,
                end_date=timeframe.end_date.isoformat(),
                total_spend=total_spend,
                average_monthly_spend=round(total_spend / coverage_months, 2),
                transaction_count=len(spend_rows),
                coverage_months=coverage_months,
                account_count=len(account_labels),
                gross_spend=gross_spend,
                refund_total=refund_total,
                total_income=round(total_income, 2),
                average_monthly_income=average_monthly_income,
                net_cash_flow=net_cash_flow,
                savings_rate=savings_rate,
                month_to_date_spend=month_to_date_spend,
            ),
            categories=[
                HouseholdSpendingCategory(
                    category=category,
                    essentiality=essentiality,
                    total_spend=round(amount, 2),
                    average_monthly_spend=round(amount / coverage_months, 2),
                    share_of_spend=round(amount / total_spend if total_spend > 0 else 0.0, 4),
                    transaction_count=category_counts[(category, essentiality)],
                    gross_monthly_spend=round(
                        category_gross[(category, essentiality)] / coverage_months, 2
                    ),
                    refund_total=round(category_refund[(category, essentiality)], 2),
                )
                for (category, essentiality), amount in sorted(
                    category_totals.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ],
            monthly_trend=[
                {
                    "month": month,
                    "total_spend": round(monthly_totals[month], 2),
                    "transaction_count": monthly_counts[month],
                }
                for month in sorted(monthly_totals.keys())
            ],
            category_monthly_trend=[
                {
                    "month": month,
                    "category": category,
                    "essentiality": essentiality,
                    "total_spend": round(amount, 2),
                    "transaction_count": category_monthly_counts[(month, category, essentiality)],
                }
                for (month, category, essentiality), amount in sorted(
                    category_monthly_totals.items(),
                    key=lambda item: (item[0][0], item[0][1]),
                )
            ],
            transactions=[
                HouseholdSpendingTransaction(
                    id=str(row["id"]),
                    date=row["date"].isoformat(),
                    merchant=str(row["merchant"]),
                    description=str(row["description"]),
                    amount=round(float(row.get("signed_amount", row["amount"])), 2),
                    category=str(row["category"]),
                    essentiality=str(row["essentiality"]),
                    original_category=(
                        str(row["original_category"]) if row.get("original_category") else None
                    ),
                    categorization_source=(
                        str(row["categorization_source"]) if row.get("categorization_source") else None
                    ),
                    source_system=(
                        str(row["source_system"]) if row.get("source_system") else None
                    ),
                    external_transaction_id=(
                        str(row["external_transaction_id"])
                        if row.get("external_transaction_id")
                        else None
                    ),
                    transaction_rule_id=(
                        str(row["transaction_rule_id"]) if row.get("transaction_rule_id") else None
                    ),
                    category_confidence=(
                        round(float(row["confidence"]), 4)
                        if row.get("confidence") is not None
                        else None
                    ),
                    needs_category_review=bool(row.get("needs_category_review")),
                    account_label=(
                        str(row["account_label"]) if row.get("account_label") else None
                    ),
                    source_document_id=str(row["document_id"]),
                    source_kind=str(row.get("source_kind") or ""),
                    source_type=str(row.get("source_type") or ""),
                    document_type=str(row.get("document_type") or ""),
                )
                for row in sorted(
                    spend_rows,
                    key=lambda item: (
                        item["date"],
                        abs(float(item.get("signed_amount", item["amount"]))),
                    ),
                    reverse=True,
                )
            ],
        )

    def _load_report_rows(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            expense_rows = conn.execute(
                """
                SELECT
                    t.id,
                    t.household_account_id,
                    t.transaction_date,
                    t.description,
                    t.raw_merchant,
                    t.amount,
                    t.category,
                    t.essentiality,
                    t.flow_type,
                    COALESCE(ap.display_label, a.canonical_label, t.account_label) AS account_label,
                    t.document_id,
                    COALESCE(m.canonical_name, t.raw_merchant, t.description) AS canonical_name,
                    d.document_type,
                    d.source_type,
                    d.filename,
                    t.row_hash,
                    m.metadata,
                    t.confidence,
                    t.metadata,
                    t.original_category,
                    t.categorization_source,
                    t.source_system,
                    t.external_transaction_id,
                    t.transaction_rule_id
                FROM household_transactions t
                LEFT JOIN household_merchants m ON m.id = t.merchant_id
                LEFT JOIN household_accounts a ON a.id = t.household_account_id
                LEFT JOIN LATERAL (
                    SELECT display_label
                    FROM household_account_preferences ap
                    WHERE ap.household_account_id = t.household_account_id
                      AND ap.hidden_at IS NULL
                    ORDER BY ap.updated_at DESC
                    LIMIT 1
                ) ap ON TRUE
                LEFT JOIN household_documents d ON d.id = t.document_id
                WHERE t.flow_type IN ('expense', 'payment', 'refund')
                  AND t.removed IS NOT TRUE
                ORDER BY t.transaction_date DESC
                """
            ).fetchall()
            import_rows = conn.execute(
                """
                SELECT
                    r.id,
                    row_date,
                    COALESCE(merchant, 'Amazon') AS merchant,
                    COALESCE(description, merchant, 'Imported order') AS description,
                    amount,
                    dataset_type,
                    document_id,
                    row_metadata,
                    d.filename,
                    r.row_hash
                FROM household_import_rows r
                JOIN household_documents d ON d.id = r.document_id
                WHERE amount IS NOT NULL
                ORDER BY row_date DESC NULLS LAST
                """
            ).fetchall()

        report_rows: list[dict[str, Any]] = []
        for row in expense_rows:
            transaction_date = row[2]
            if not isinstance(transaction_date, datetime):
                continue
            try:
                amount: float | None = float(row[5]) if row[5] is not None else None
            except (TypeError, ValueError):
                amount = None
            if amount is None:
                continue
            merchant_metadata = _row_value(row, 16)
            confidence = _row_value(row, 17)
            transaction_metadata = _transaction_metadata(_row_value(row, 18))
            effective_flow = _effective_transaction_flow(
                flow_type=str(row[8] or "expense"),
                raw_merchant=str(row[11] or row[4] or row[3]),
                description=str(row[3]),
                source_type=str(row[13] or ""),
            )
            effective_category, effective_essentiality = _effective_transaction_classification(
                flow_type=effective_flow,
                raw_merchant=str(row[11] or row[4] or row[3]),
                description=str(row[3]),
                amount=amount,
                stored_category=str(row[6] or ""),
                stored_essentiality=str(row[7] or ""),
                merchant_metadata=merchant_metadata if isinstance(merchant_metadata, dict) else None,
            )
            needs_category_review = _needs_category_review(
                stored_category=str(row[6] or ""),
                effective_category=effective_category,
                confidence=float(confidence) if confidence is not None else None,
                metadata=transaction_metadata,
            )
            if needs_category_review:
                effective_category = UNKNOWN_CATEGORY
                effective_essentiality = UNKNOWN_ESSENTIALITY
            if not is_budget_driving_expense(
                flow_type=effective_flow,
                category=effective_category,
                description=str(row[3]),
                merchant=str(row[11] or row[4] or row[3]),
            ):
                continue
            report_rows.append(
                {
                    "id": str(row[0]),
                    "household_account_id": str(row[1]) if row[1] is not None else None,
                    "date": transaction_date.date(),
                    "merchant": str(row[11] or row[4] or row[3]),
                    "description": str(row[3]),
                    "amount": amount,
                    "signed_amount": -amount if effective_flow == "refund" else amount,
                    "category": effective_category,
                    "essentiality": effective_essentiality,
                    "flow_type": effective_flow,
                    "account_label": str(row[9]) if row[9] is not None else None,
                    "document_id": str(row[10]),
                    "document_type": str(row[12] or ""),
                    "source_type": str(row[13] or ""),
                    "source_document_filename": str(row[14] or ""),
                    "row_hash": str(row[15]),
                    "source_kind": "transaction",
                    "confidence": float(confidence) if confidence is not None else None,
                    "needs_category_review": needs_category_review,
                    "original_category": (
                        str(_row_value(row, 19)) if _row_value(row, 19) is not None else None
                    ),
                    "categorization_source": (
                        str(_row_value(row, 20)) if _row_value(row, 20) is not None else None
                    ),
                    "source_system": (
                        str(_row_value(row, 21)) if _row_value(row, 21) is not None else None
                    ),
                    "external_transaction_id": (
                        str(_row_value(row, 22)) if _row_value(row, 22) is not None else None
                    ),
                    "transaction_rule_id": (
                        str(_row_value(row, 23)) if _row_value(row, 23) is not None else None
                    ),
                }
            )

        for row in import_rows:
            row_date = row[1]
            if not isinstance(row_date, datetime):
                continue
            try:
                amount = float(row[4]) if row[4] is not None else None
            except (TypeError, ValueError):
                amount = None
            if amount is None:
                continue
            candidate_row = {
                "id": str(row[0]),
                "date": row_date.date(),
                "merchant": str(row[2]),
                "description": str(row[3]),
                "amount": amount,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": str(row[6]),
                "document_type": "import",
                "source_type": str(row[5] or "import"),
                "source_document_filename": str(row[8] or ""),
                "row_hash": str(row[9]),
                "source_kind": "import",
                "metadata": row[7] if len(row) > 7 else None,
            }
            report_rows.append(candidate_row)

        return report_rows

    def infer_merchant_cadence(self, *, merchant: str) -> dict[str, object] | None:
        with self.storage.connection() as conn:
            row_dates: list[date] = []
            rows = conn.execute(
                """
                SELECT transaction_date
                FROM household_transactions t
                LEFT JOIN household_merchants m ON m.id = t.merchant_id
                WHERE lower(COALESCE(m.canonical_name, t.raw_merchant, '')) LIKE %s
                  AND t.flow_type = 'expense'
                ORDER BY transaction_date ASC
                """,
                [f"%{_merchant_root(merchant)}%"],
            ).fetchall()
            for row in rows:
                if isinstance(row[0], datetime):
                    row_dates.append(row[0].date())

            document_rows = conn.execute(
                """
                SELECT metadata->'structured_data'->>'merchant', metadata->'structured_data'->>'statement_period'
                FROM household_documents
                WHERE metadata->'structured_data'->>'merchant' IS NOT NULL
                  AND metadata->'structured_data'->>'statement_period' IS NOT NULL
                """
            ).fetchall()
            for raw_merchant, raw_period in document_rows:
                if not isinstance(raw_merchant, str) or not isinstance(raw_period, str):
                    continue
                observed_aliases = _merchant_aliases(raw_merchant)
                target_aliases = _merchant_aliases(merchant)
                if not (observed_aliases & target_aliases) and _merchant_root(raw_merchant) != _merchant_root(merchant):
                    continue
                parsed_period = _parse_date_value(raw_period)
                if parsed_period is not None:
                    row_dates.append(parsed_period)

        row_dates = sorted(set(row_dates))
        if len(row_dates) < MIN_DATES_FOR_CADENCE:
            return None
        return self._dates_to_cadence(row_dates)

    @staticmethod
    def _document_stored_path(document: Any) -> Path | None:
        metadata = getattr(document, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        stored_path = metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return None
        path = Path(stored_path)
        return path if path.exists() else None

    @staticmethod
    def _resolved_account_label(
        *,
        document_label: str | None,
        structured_data: dict[str, Any],
    ) -> str | None:
        hint = str(structured_data.get("account_hint") or "").strip() or None
        mask = str(structured_data.get("account_mask") or "").strip() or None
        if hint and (_looks_like_mask_only(document_label) or document_label == mask):
            return hint
        return document_label or hint or None

    def _canonicalize_stored_categories(self, conn: Any, *, limit: int) -> int:
        rows = conn.execute(
            """
            SELECT
                t.id,
                t.flow_type,
                COALESCE(m.canonical_name, t.raw_merchant, t.description),
                t.description,
                t.amount,
                t.category,
                t.essentiality,
                COALESCE(m.metadata, '{}'::jsonb),
                d.source_type,
                t.categorization_source
            FROM household_transactions t
            LEFT JOIN household_merchants m ON m.id = t.merchant_id
            LEFT JOIN household_documents d ON d.id = t.document_id
            WHERE COALESCE(t.categorization_source, '') NOT IN (
                'manual',
                'manual_rule',
                'merchant_rule',
                'transaction_audit',
                'transaction_audit_agent'
            )
              AND NOT EXISTS (
                  SELECT 1
                  FROM household_transaction_rules r
                  WHERE r.merchant_id = t.merchant_id
                    AND r.enabled IS TRUE
              )
            ORDER BY COALESCE(t.updated_at, t.created_at) DESC
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        updated = 0
        now = datetime.now(UTC).isoformat()
        for row in rows:
            merchant_metadata = row[7] if isinstance(row[7], dict) else {}
            if isinstance(merchant_metadata.get("manual_rule"), dict):
                continue
            amount = float(row[4]) if row[4] is not None else None
            effective_flow = _effective_transaction_flow(
                flow_type=str(row[1] or "expense"),
                raw_merchant=str(row[2] or row[3] or ""),
                description=str(row[3] or row[2] or ""),
                source_type=str(row[8] or ""),
            )
            category, essentiality = _effective_transaction_classification(
                flow_type=effective_flow,
                raw_merchant=str(row[2] or row[3] or ""),
                description=str(row[3] or row[2] or ""),
                amount=amount,
                stored_category=str(row[5] or ""),
                stored_essentiality=str(row[6] or ""),
                merchant_metadata=merchant_metadata,
            )
            if (str(row[5] or ""), str(row[6] or "")) == (category, essentiality):
                continue
            conn.execute(
                """
                UPDATE household_transactions
                SET original_category = COALESCE(original_category, category),
                    category = %s,
                    essentiality = %s,
                    categorization_source = %s,
                    categorization_version = %s,
                    category_updated_at = %s,
                    category_updated_by = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    category,
                    essentiality,
                    "canonical_backfill",
                    CATEGORIZATION_VERSION,
                    now,
                    "transaction_system_repair",
                    now,
                    row[0],
                ],
            )
            updated += 1
        return updated

    @staticmethod
    def _backfill_merchant_rules(conn: Any, *, limit: int) -> int:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.normalized_key,
                m.metadata->'manual_rule' AS manual_rule,
                COUNT(t.id) AS applied_count
            FROM household_merchants m
            LEFT JOIN household_transactions t ON t.merchant_id = m.id
            WHERE m.metadata->'manual_rule' IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM household_transaction_rules r
                  WHERE r.merchant_id = m.id
                    AND r.enabled IS TRUE
              )
            GROUP BY m.id
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        now = datetime.now(UTC).isoformat()
        inserted = 0
        for row in rows:
            manual_rule = row[2] if isinstance(row[2], dict) else {}
            category = _metadata_text(manual_rule, "category")
            essentiality = _metadata_text(manual_rule, "essentiality") or "mixed"
            if not category:
                continue
            rule_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO household_transaction_rules (
                    id, rule_type, merchant_id, normalized_merchant_key,
                    category, essentiality, enabled, source, applied_count,
                    metadata, created_at, updated_at
                ) VALUES (
                    %s, 'merchant', %s, %s, %s, %s, TRUE, 'legacy_manual_rule',
                    %s, %s::jsonb, %s, %s
                )
                """,
                [
                    rule_id,
                    row[0],
                    row[1],
                    category,
                    essentiality,
                    int(row[3] or 0),
                    json.dumps({"legacy_manual_rule": manual_rule}),
                    now,
                    now,
                ],
            )
            conn.execute(
                """
                UPDATE household_transactions
                SET transaction_rule_id = %s,
                    categorization_source = CASE
                        WHEN categorization_source = 'manual' THEN categorization_source
                        ELSE 'merchant_rule'
                    END,
                    category_updated_at = COALESCE(category_updated_at, %s),
                    category_updated_by = COALESCE(category_updated_by, 'legacy_manual_rule'),
                    updated_at = %s
                WHERE merchant_id = %s
                  AND category = %s
                  AND essentiality = %s
                """,
                [rule_id, now, now, row[0], category, essentiality],
            )
            inserted += 1
        return inserted

    @staticmethod
    def _backfill_transaction_provenance(conn: Any) -> int:
        result = conn.execute(
            """
            UPDATE household_transactions
            SET source_system = COALESCE(
                    source_system,
                    metadata->>'source',
                    CASE
                        WHEN NULLIF(metadata->>'plaid_transaction_id', '') IS NOT NULL THEN 'plaid'
                        ELSE NULL
                    END
                ),
                external_transaction_id = COALESCE(
                    external_transaction_id,
                    metadata->>'plaid_transaction_id',
                    metadata->>'fitid',
                    metadata->>'trace_number',
                    metadata->>'auth_code'
                ),
                original_category = COALESCE(original_category, category),
                categorization_source = COALESCE(
                    categorization_source,
                    CASE
                        WHEN NULLIF(metadata->>'plaid_transaction_id', '') IS NOT NULL THEN 'plaid'
                        ELSE NULL
                    END,
                    metadata->>'source',
                    'parser'
                ),
                categorization_version = COALESCE(categorization_version, %s),
                balance_after = COALESCE(
                    balance_after,
                    CASE
                        WHEN COALESCE(metadata->>'balance_after', '') ~ '^-{0,1}[0-9,]+([.][0-9]+){0,1}$'
                            THEN replace(metadata->>'balance_after', ',', '')::numeric
                        ELSE NULL
                    END
                )
            WHERE (
                    source_system IS NULL
                    AND NULLIF(COALESCE(metadata->>'source', metadata->>'plaid_transaction_id'), '') IS NOT NULL
                )
               OR (
                    external_transaction_id IS NULL
                    AND NULLIF(
                        COALESCE(
                            metadata->>'plaid_transaction_id',
                            metadata->>'fitid',
                            metadata->>'trace_number',
                            metadata->>'auth_code'
                        ),
                        ''
                    ) IS NOT NULL
                )
               OR original_category IS NULL
               OR categorization_source IS NULL
               OR categorization_version IS NULL
               OR (
                    balance_after IS NULL
                    AND COALESCE(metadata->>'balance_after', '') ~ '^-{0,1}[0-9,]+([.][0-9]+){0,1}$'
                )
            """,
            [CATEGORIZATION_VERSION],
        )
        return int(getattr(result, "rowcount", 0) or 0)

    def _link_transactions_by_account_mask(self, conn: Any, *, limit: int) -> int:
        transactions = conn.execute(
            """
            SELECT t.id, t.account_label, t.metadata, d.account_label
            FROM household_transactions t
            LEFT JOIN household_documents d ON d.id = t.document_id
            WHERE t.household_account_id IS NULL
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        account_rows = conn.execute(
            """
            SELECT id, account_mask
            FROM household_accounts
            WHERE account_mask IS NOT NULL
            """,
        ).fetchall()
        updated = 0
        now = datetime.now(UTC).isoformat()
        for row in transactions:
            metadata = _transaction_metadata(row[2])
            labels = [str(value) for value in (row[1], row[3]) if value]
            candidate_masks = [
                mask
                for mask in (
                    _metadata_text(metadata, "account_mask"),
                    *(derive_account_mask(None, label, label) for label in labels),
                )
                if mask
            ]
            matched = {
                str(account_row[0])
                for account_row in account_rows
                if account_row[0] is not None
                and any(account_masks_match(account_row[1], mask) for mask in candidate_masks)
            }
            if len(matched) != 1:
                continue
            conn.execute(
                """
                UPDATE household_transactions
                SET household_account_id = %s,
                    updated_at = %s
                WHERE id = %s
                """,
                [next(iter(matched)), now, row[0]],
            )
            updated += 1
        return updated

    @staticmethod
    def _repair_application_summaries(conn: Any, *, limit: int) -> int:
        rows = conn.execute(
            """
            SELECT
                d.id,
                d.metadata,
                COALESCE(tx.transaction_count, 0),
                COALESCE(imports.import_count, 0),
                imports.dataset_type,
                COALESCE(accounts.evidence_account_count, 0),
                COALESCE(inferred.inferred_count, 0)
            FROM household_documents d
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS transaction_count
                FROM household_transactions
                GROUP BY document_id
            ) tx ON tx.document_id = d.id
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS import_count, MIN(dataset_type) AS dataset_type
                FROM household_import_rows
                GROUP BY document_id
            ) imports ON imports.document_id = d.id
            LEFT JOIN (
                SELECT document_id, COUNT(*) AS evidence_account_count
                FROM household_evidence_accounts
                GROUP BY document_id
            ) accounts ON accounts.document_id = d.id
            LEFT JOIN (
                SELECT source_document_id AS document_id, COUNT(*) AS inferred_count
                FROM household_inferred_values
                WHERE status IN ('inferred', 'confirmed')
                GROUP BY source_document_id
            ) inferred ON inferred.document_id = d.id
            WHERE d.metadata->'application_summary' IS NOT NULL
            ORDER BY d.uploaded_at DESC
            LIMIT %s
            """,
            [max(limit, 1)],
        ).fetchall()
        repaired = 0
        for row in rows:
            metadata = _transaction_metadata(row[1])
            existing_summary = metadata.get("application_summary")
            if not isinstance(existing_summary, dict):
                continue
            existing_transactions = existing_summary.get("transactions")
            existing_transactions = existing_transactions if isinstance(existing_transactions, dict) else {}
            transaction_count = int(row[2] or 0)
            import_count = int(row[3] or 0)
            evidence_account_count = int(row[5] or 0)
            inferred_count = int(row[6] or 0)
            held_value = existing_transactions.get("held_for_date_review")
            transaction_import_summary = metadata.get("transaction_import_summary")
            if held_value in (None, "") and isinstance(transaction_import_summary, dict):
                held_value = transaction_import_summary.get("held_for_date_review")
            held_count = int(held_value or 0)
            impacts: list[str] = []
            if import_count:
                impacts.append("imports")
            if transaction_count:
                impacts.append("transactions")
            if evidence_account_count:
                impacts.append("accounts")
            if inferred_count:
                impacts.append("inferences")
            if held_count and not impacts:
                impacts.append("date_review")
            status = "applied" if impacts and impacts != ["date_review"] else (
                "needs_date_review" if held_count else "incomplete"
            )
            next_summary = {
                **existing_summary,
                "status": status,
                "impacts": impacts,
                "imports": {
                    **(
                        existing_summary.get("imports")
                        if isinstance(existing_summary.get("imports"), dict)
                        else {}
                    ),
                    "dataset_type": row[4],
                    "inserted": import_count,
                },
                "transactions": {
                    **existing_transactions,
                    "inserted": transaction_count,
                    "held_for_date_review": held_count,
                },
                "evidence_accounts": evidence_account_count,
                "inferred_values": inferred_count,
                "needs_follow_up": status != "applied",
            }
            if next_summary == existing_summary:
                continue
            conn.execute(
                """
                UPDATE household_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                [json.dumps({"application_summary": next_summary}), row[0]],
            )
            repaired += 1
        return repaired

    @staticmethod
    def _resolve_transaction_account_id(
        conn: Any,
        *,
        account_label: str | None,
        metadata: dict[str, Any],
    ) -> str | None:
        account_mask = _metadata_text(metadata, "account_mask")
        label_mask = derive_account_mask(None, account_label, account_label)
        candidate_masks = [mask for mask in (account_mask, label_mask) if mask]
        if not candidate_masks:
            return None
        rows = conn.execute(
            """
            SELECT id, account_mask
            FROM household_accounts
            WHERE account_mask IS NOT NULL
            """,
        ).fetchall()
        matched = {
            str(row[0])
            for row in rows
            if row[0] is not None
            and any(account_masks_match(row[1], candidate) for candidate in candidate_masks)
        }
        if len(matched) == 1:
            return next(iter(matched))
        return None

    def _resolve_merchant(
        self,
        *,
        conn: Any,
        raw_merchant: str,
        category: str,
        essentiality: str,
    ) -> tuple[str | None, str, str, str, bool, str | None]:
        alias_keys = sorted(_merchant_aliases(raw_merchant))
        normalized_key = alias_keys[0] if alias_keys else _merchant_root(raw_merchant)
        if not normalized_key:
            normalized_key = "unknown"
        existing = conn.execute(
            """
            SELECT id, canonical_name, primary_category, essentiality, metadata
            FROM household_merchants
            WHERE normalized_key = ANY(%s)
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [alias_keys or [normalized_key]],
        ).fetchone()
        canonical_name = _canonical_merchant_name(raw_merchant)
        if existing is not None:
            merchant_id = str(existing[0])
            canonical_name = str(existing[1])
            metadata = existing[4] if isinstance(existing[4], dict) else {}
            rule_row = self._active_merchant_rule(conn, merchant_id)
            rule_id = str(rule_row[0]) if rule_row is not None else None
            has_manual_rule = rule_row is not None or (
                bool(metadata.get("manual_rule")) if isinstance(metadata, dict) else False
            )
            if has_manual_rule:
                category = str(rule_row[1] if rule_row is not None else existing[2] or category)
                essentiality = str(rule_row[2] if rule_row is not None else existing[3] or essentiality)
            merged_aliases = sorted({*(metadata.get("alias_keys", []) if isinstance(metadata, dict) else []), *alias_keys})
            conn.execute(
                """
                UPDATE household_merchants
                SET display_name = %s,
                    primary_category = %s,
                    essentiality = %s,
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = %s
                WHERE id = %s
                """,
                [
                    canonical_name,
                    category,
                    essentiality,
                    json.dumps({"alias_keys": merged_aliases}),
                    datetime.now(UTC).isoformat(),
                    merchant_id,
                ],
            )
            return merchant_id, canonical_name, category, essentiality, has_manual_rule, rule_id

        merchant_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO household_merchants (
                id, canonical_name, normalized_key, display_name, primary_category,
                essentiality, metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            [
                merchant_id,
                canonical_name,
                normalized_key,
                canonical_name,
                category,
                essentiality,
                json.dumps({"alias_keys": alias_keys}),
                datetime.now(UTC).isoformat(),
                datetime.now(UTC).isoformat(),
            ],
        )
        return merchant_id, canonical_name, category, essentiality, False, None

    @staticmethod
    def _active_merchant_rule(conn: Any, merchant_id: str) -> Any:
        return conn.execute(
            """
            SELECT id, category, essentiality
            FROM household_transaction_rules
            WHERE merchant_id = %s
              AND enabled IS TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            [merchant_id],
        ).fetchone()

    def _dates_to_cadence(self, observed_dates: list[date]) -> dict[str, object] | None:
        ordered_dates = sorted(set(observed_dates))
        if len(ordered_dates) < MIN_DATES_FOR_CADENCE:
            return None

        intervals = [
            (later - earlier).days
            for earlier, later in pairwise(ordered_dates)
            if (later - earlier).days > 0
        ]
        if len(intervals) < 1:
            return None

        median_interval = sorted(intervals)[len(intervals) // 2]
        if median_interval <= WEEKLY_INTERVAL_MAX:
            label = "likely weekly"
        elif median_interval <= BIWEEKLY_INTERVAL_MAX:
            label = "likely bi-weekly"
        elif median_interval <= MONTHLY_INTERVAL_MAX:
            label = "likely monthly"
        else:
            label = "less frequent"

        if len(ordered_dates) == 2:
            confidence = CADENCE_CONFIDENCE_EARLY
        elif len(ordered_dates) == 3:
            confidence = CADENCE_CONFIDENCE_MINIMAL
        else:
            confidence = CADENCE_CONFIDENCE_STANDARD
        return {
            "label": label,
            "confidence": confidence,
            "rationale": (
                f"Jenny found {len(ordered_dates)} dated merchant events with a median gap of "
                f"{median_interval} days."
            ),
        }

    def _merchant_recommendation(self, *, merchant: str, category: str, cadence: str) -> str:
        merchant_key = _merchant_root(merchant)
        recommendation = "Keep tracking {merchant} so Jenny can tighten category and card-optimization guidance."
        if merchant_key == "amazon":
            recommendation = "Track repeat Amazon items against Walmart, Target, and Subscribe & Save so Jenny can flag cheaper substitutions."
        elif merchant_key.startswith("walmart"):
            recommendation = "Use Walmart basket history as a price anchor and compare it against Amazon, Aldi, Publix, and warehouse-club equivalents."
        elif category == "Groceries" and cadence in {"likely weekly", "likely bi-weekly"}:
            recommendation = f"Use {merchant} as a budget anchor and compare it against Publix, Whole Foods, and Amazon for recurring essentials."
        elif category == "Subscriptions":
            recommendation = f"Audit {merchant} for downgrade or cancellation opportunities."
        elif category == "Bills" and cadence in {"likely monthly", "less frequent"}:
            recommendation = f"Watch {merchant} for month-over-month bill creep and renegotiation opportunities."
        elif category == "Retail":
            recommendation = f"Treat {merchant} as a discretionary merchant until Jenny proves it is mostly essentials."
        else:
            recommendation = recommendation.format(merchant=merchant)
        return recommendation
