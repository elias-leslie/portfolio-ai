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
from app.services._household_spend_filters import is_budget_driving_expense
from app.services._household_time_windows import resolve_household_time_window
from app.services._household_transaction_parsers import (
    _parse_date_value,
    extract_transactions,
)
from app.storage import get_storage

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Confidence level assigned to manually classified transactions.
MANUAL_RULE_CONFIDENCE = 0.90

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


def _looks_like_mask_only(value: str | None) -> bool:
    if not value:
        return False
    cleaned = re.sub(r"[^A-Za-z0-9]+", "", value.strip())
    if len(cleaned) < 4:
        return False
    return " " not in value.strip() and any(char.isdigit() for char in cleaned)


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
                merchant_id, canonical_name, category, essentiality, has_manual_rule = self._resolve_merchant(
                    conn=conn,
                    raw_merchant=transaction.raw_merchant or transaction.description,
                    category=transaction.category,
                    essentiality=transaction.essentiality,
                )
                if transaction.flow_type in {"income", "payment", "transfer_in", "transfer_out", "investment"}:
                    category, essentiality = _classification_for_flow(
                        raw_merchant=transaction.raw_merchant or transaction.description,
                        description=transaction.description,
                        amount=float(transaction.amount),
                        flow_type=transaction.flow_type,
                    )
                # Auto-apply prior manual categorization with high confidence
                if has_manual_rule:
                    transaction.confidence = max(transaction.confidence, MANUAL_RULE_CONFIDENCE)
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
                    **(transaction.metadata or {}),
                }
                result = conn.execute(
                    """
                    INSERT INTO household_transactions (
                        id, document_id, merchant_id, row_hash, transaction_date, posted_date,
                        description, raw_merchant, account_label, amount, currency, flow_type,
                        category, essentiality, confidence, metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
                    )
                    ON CONFLICT (row_hash) DO UPDATE SET
                        merchant_id = COALESCE(EXCLUDED.merchant_id, household_transactions.merchant_id),
                        posted_date = COALESCE(EXCLUDED.posted_date, household_transactions.posted_date),
                        description = EXCLUDED.description,
                        raw_merchant = COALESCE(EXCLUDED.raw_merchant, household_transactions.raw_merchant),
                        account_label = COALESCE(EXCLUDED.account_label, household_transactions.account_label),
                        amount = EXCLUDED.amount,
                        currency = EXCLUDED.currency,
                        flow_type = EXCLUDED.flow_type,
                        category = COALESCE(EXCLUDED.category, household_transactions.category),
                        essentiality = COALESCE(EXCLUDED.essentiality, household_transactions.essentiality),
                        confidence = GREATEST(
                            COALESCE(household_transactions.confidence, 0),
                            COALESCE(EXCLUDED.confidence, 0)
                        ),
                        metadata = household_transactions.metadata || EXCLUDED.metadata,
                        updated_at = EXCLUDED.updated_at
                    RETURNING xmax = 0
                    """,
                    [
                        str(uuid.uuid4()),
                        document.id,
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
                        transaction.account_label or document.account_label,
                        transaction.amount,
                        transaction.currency,
                        transaction.flow_type,
                        category,
                        essentiality,
                        transaction.confidence,
                        json.dumps(metadata),
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

    def build_reports(self) -> HouseholdReports:
        return build_household_reports(
            report_rows=self._load_report_rows(),
            cadence_for_dates=self._dates_to_cadence,
            merchant_recommendation=self._merchant_recommendation,
        )

    def build_spending_view(self, *, window: str = "1m") -> HouseholdSpendingView:
        timeframe = resolve_household_time_window(window)
        report_rows = self._load_report_rows()
        filtered_rows = [
            row
            for row in report_rows
            if row["date"] <= timeframe.end_date
            and (timeframe.start_date is None or row["date"] >= timeframe.start_date)
        ]
        analytics_rows = [
            row for row in filtered_rows if row.get("source_kind") != "import"
        ]
        spend_rows = [
            row
            for row in collapse_report_rows(analytics_rows)
            if abs(float(row.get("signed_amount", row["amount"]))) > 0
        ]

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
        category_counts: dict[tuple[str, str], int] = {}
        account_labels = {
            str(row["account_label"]).strip()
            for row in spend_rows
            if row.get("account_label")
        }

        for row in spend_rows:
            month_key = row["date"].strftime("%Y-%m")
            signed_amount = float(row.get("signed_amount", row["amount"]))
            monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + signed_amount
            monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
            category_key = (str(row["category"]), str(row["essentiality"]))
            category_totals[category_key] = category_totals.get(category_key, 0.0) + signed_amount
            category_counts[category_key] = category_counts.get(category_key, 0) + 1

        coverage_months = (
            timeframe.window_months
            if timeframe.window_months is not None
            else max(len(monthly_totals), 1)
        )
        total_spend = round(
            sum(float(row.get("signed_amount", row["amount"])) for row in spend_rows),
            2,
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
            ),
            categories=[
                HouseholdSpendingCategory(
                    category=category,
                    essentiality=essentiality,
                    total_spend=round(amount, 2),
                    average_monthly_spend=round(amount / coverage_months, 2),
                    share_of_spend=round(amount / total_spend if total_spend > 0 else 0.0, 4),
                    transaction_count=category_counts[(category, essentiality)],
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
            transactions=[
                HouseholdSpendingTransaction(
                    date=row["date"].isoformat(),
                    merchant=str(row["merchant"]),
                    description=str(row["description"]),
                    amount=round(float(row.get("signed_amount", row["amount"])), 2),
                    category=str(row["category"]),
                    essentiality=str(row["essentiality"]),
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
                    m.metadata
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
                merchant_metadata=row[16] if isinstance(row[16], dict) else None,
            )
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

    def _resolve_merchant(
        self,
        *,
        conn: Any,
        raw_merchant: str,
        category: str,
        essentiality: str,
    ) -> tuple[str | None, str, str, str, bool]:
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
            has_manual_rule = bool(metadata.get("manual_rule")) if isinstance(metadata, dict) else False
            if has_manual_rule:
                category = str(existing[2] or category)
                essentiality = str(existing[3] or essentiality)
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
            return merchant_id, canonical_name, category, essentiality, has_manual_rule

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
        return merchant_id, canonical_name, category, essentiality, False

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
