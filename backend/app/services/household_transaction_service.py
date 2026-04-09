"""Household transaction extraction, merchant normalization, and report generation."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from types import SimpleNamespace
from typing import Any

from app.logging_config import get_logger
from app.models.household_finance import (
    HouseholdReports,
)
from app.services._household_report_builder import (
    _merchant_aliases,
    _merchant_root,
    build_household_reports,
)
from app.storage import get_storage

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Amount-range heuristics for classifying unrecognized merchants
MIN_SUBSCRIPTION_AMOUNT = 5.0
MAX_SUBSCRIPTION_AMOUNT = 25.0
BILLS_AMOUNT_THRESHOLD = 800.0

# Confidence levels assigned to extracted transactions by source
MANUAL_RULE_CONFIDENCE = 0.90
RECEIPT_CONFIDENCE = 0.9
CHASE_STATEMENT_CONFIDENCE = 0.88
WELLS_FARGO_STATEMENT_CONFIDENCE = 0.82

# Cadence inference thresholds (median interval in days)
WEEKLY_INTERVAL_MAX = 10
BIWEEKLY_INTERVAL_MAX = 20
MONTHLY_INTERVAL_MAX = 45

# Minimum observed dates needed before inferring a billing cadence
MIN_DATES_FOR_CADENCE = 3

# Cadence confidence based on sample size
CADENCE_CONFIDENCE_MINIMAL = 0.72  # exactly MIN_DATES_FOR_CADENCE observations
CADENCE_CONFIDENCE_STANDARD = 0.82  # more than MIN_DATES_FOR_CADENCE observations


# ---------------------------------------------------------------------------
# Pure module-level helpers (no instance state)
# ---------------------------------------------------------------------------


def _canonical_merchant_name(raw_merchant: str) -> str:
    root = _merchant_root(raw_merchant)
    if not root:
        return raw_merchant.strip() or "Unknown merchant"
    collapsed = root.replace(" ", "")
    if "walmart" in collapsed or "wmsupercenter" in collapsed:
        store_match = re.search(r"#\s?(\d{4})", raw_merchant)
        location_match = re.search(r"(LARGO|CLEARWATER|BELLEAIR BLUF|BELLEAIR BLF)\s+FL", raw_merchant, flags=re.IGNORECASE)
        store_suffix = f" (Store #{store_match.group(1)})" if store_match else ""
        location_suffix = f", {location_match.group(1).title()}, FL" if location_match else ""
        return f"Walmart{store_suffix}{location_suffix}"
    if "amazon" in collapsed or "amzn" in collapsed:
        return "Amazon"
    if "wholefoods" in collapsed:
        return "Whole Foods"
    return re.sub(r"\s+", " ", raw_merchant).strip()


def _classify_statement_flow(description: str) -> str:
    normalized = description.lower()
    if "payment thank you" in normalized or normalized.startswith("payment"):
        return "payment"
    if "refund" in normalized or "return" in normalized:
        return "refund"
    return "expense"


def _classify_wells_flow(description: str) -> str:
    normalized = description.lower()
    if "payroll" in normalized or "deposit" in normalized:
        return "income"
    if "transfer from" in normalized:
        return "transfer_in"
    if "transfer to" in normalized or "zelle to" in normalized:
        return "transfer_out"
    return "expense"


def _classify_merchant(*, raw_merchant: str, description: str, amount: float | None = None) -> tuple[str, str]:
    normalized = _merchant_root(f"{raw_merchant} {description}")
    rules = [
        (["walmart", "wal mart", "wm supercenter", "publix", "whole foods", "food patch", "aldi", "kroger", "costco", "trader joe"], ("Groceries", "essential")),
        (["dukeenergy", "duke energy", "utilities", "mortgage", "comcast", "xfinity", "att", "a t t", "verizon", "tmobile", "t mobile", "spectrum"], ("Bills", "essential")),
        (["geico", "statefarm", "state farm", "progressive", "allstate", "insurance"], ("Insurance", "essential")),
        (["cvs", "walgreens", "urgent care", "pharmacy", "medical", "healthcare", "doctor", "dental"], ("Healthcare", "essential")),
        (["shell", "speedway", "gas", "chevron", "exxon", "bp"], ("Gas", "essential")),
        (["uber", "lyft", "parking", "toll"], ("Transportation", "discretionary")),
        (["lowes", "lowe s", "home depot", "menards", "ace hardware"], ("Home", "discretionary")),
        (["planet fitness", "gym", "ymca", "fitness"], ("Fitness", "discretionary")),
        (["spotify", "cloudflare", "prime", "netflix", "hulu", "disney", "hbo", "apple music", "youtube"], ("Subscriptions", "discretionary")),
        (["target", "tjmaxx", "american eagle", "sephora", "amazon"], ("Retail", "discretionary")),
        (["chipotle", "bonefish", "cantina", "mcdonald", "starbucks", "dunkin", "chick fil", "wendy", "taco bell", "subway", "pizza", "grubhub", "doordash", "ubereats"], ("Dining", "discretionary")),
        (["payroll"], ("Income", "essential")),
        (["transfer", "payment thank you", "payment"], ("Transfers", "mixed")),
    ]
    for keywords, classification in rules:
        if any(keyword in normalized for keyword in keywords):
            return classification

    # Amount-range heuristics as a secondary signal for unrecognized merchants
    if amount is not None:
        if MIN_SUBSCRIPTION_AMOUNT <= amount <= MAX_SUBSCRIPTION_AMOUNT:
            return ("Subscriptions", "discretionary")
        if amount >= BILLS_AMOUNT_THRESHOLD:
            return ("Bills", "essential")

    return ("Household", "mixed")


def _parse_date_value(raw_value: str) -> date | None:
    value = raw_value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _extract_statement_date(extracted_text: str) -> date | None:
    match = re.search(r"Statement Date:\s*(\d{2}/\d{2}/\d{2,4})", extracted_text, flags=re.IGNORECASE)
    if match:
        return _parse_date_value(match.group(1))
    match = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", extracted_text)
    if match:
        return _parse_date_value(match.group(1))
    return None


def _statement_transaction_date(*, raw_date: str, statement_date: date) -> date | None:
    month_text, day_text = raw_date.split("/", maxsplit=1)
    month = int(month_text)
    day = int(day_text)
    year = statement_date.year - 1 if month > statement_date.month else statement_date.year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_decimal(raw_value: str) -> Decimal | None:
    cleaned = raw_value.strip().replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ExtractedTransaction:
    transaction_date: date
    description: str
    raw_merchant: str | None
    amount: Decimal
    flow_type: str
    category: str
    essentiality: str
    confidence: float
    posted_date: date | None = None
    currency: str = "USD"
    account_label: str | None = None
    metadata: dict[str, object] | None = None


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

        transactions = self._extract_transactions(
            filename=document.filename,
            source_type=str(reviewed.get("source_type") or document.source_type),
            document_type=str(reviewed.get("document_type") or document.document_type),
            extracted_text=extracted_text,
            structured_data=structured_data,
            account_label=document.account_label,
            review_summary=str(reviewed.get("summary") or ""),
        )
        if not transactions:
            return {"inserted": 0, "updated": 0}

        inserted = 0
        updated = 0
        now = datetime.now(UTC).isoformat()

        with self.storage.connection() as conn:
            for transaction in transactions:
                merchant_id, canonical_name, category, essentiality, has_manual_rule = self._resolve_merchant(
                    conn=conn,
                    raw_merchant=transaction.raw_merchant or transaction.description,
                    category=transaction.category,
                    essentiality=transaction.essentiality,
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

            conn.execute(
                """
                UPDATE household_documents
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                """,
                [
                    json.dumps({"transaction_import_summary": {"inserted": inserted, "updated": updated}}),
                    document.id,
                ],
            )
            conn.commit()

        return {"inserted": inserted, "updated": updated}

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
                WHERE d.source_type IN ('bank', 'credit_card', 'receipt')
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
        with self.storage.connection() as conn:
            expense_rows = conn.execute(
                """
                SELECT
                    t.transaction_date,
                    t.description,
                    t.raw_merchant,
                    t.amount,
                    t.category,
                    t.essentiality,
                    t.account_label,
                    t.document_id,
                    COALESCE(m.canonical_name, t.raw_merchant, t.description) AS canonical_name,
                    d.document_type,
                    d.source_type
                FROM household_transactions t
                LEFT JOIN household_merchants m ON m.id = t.merchant_id
                LEFT JOIN household_documents d ON d.id = t.document_id
                WHERE t.flow_type = 'expense'
                ORDER BY t.transaction_date DESC
                """
            ).fetchall()
            import_rows = conn.execute(
                """
                SELECT
                    row_date,
                    COALESCE(merchant, 'Amazon') AS merchant,
                    COALESCE(description, merchant, 'Imported order') AS description,
                    amount,
                    dataset_type,
                    document_id
                FROM household_import_rows
                WHERE amount IS NOT NULL
                ORDER BY row_date DESC NULLS LAST
                """
            ).fetchall()

        report_rows: list[dict[str, Any]] = []
        for row in expense_rows:
            transaction_date = row[0]
            if not isinstance(transaction_date, datetime):
                continue
            try:
                amount: float | None = float(row[3]) if row[3] is not None else None
            except (TypeError, ValueError):
                amount = None
            if amount is None:
                continue
            report_rows.append(
                {
                    "date": transaction_date.date(),
                    "merchant": str(row[8] or row[2] or row[1]),
                    "description": str(row[1]),
                    "amount": amount,
                    "category": str(row[4] or "Uncategorized"),
                    "essentiality": str(row[5] or "mixed"),
                    "account_label": str(row[6]) if row[6] is not None else None,
                    "document_id": str(row[7]),
                    "document_type": str(row[9] or ""),
                    "source_type": str(row[10] or ""),
                    "source_kind": "transaction",
                }
            )

        for row in import_rows:
            row_date = row[0]
            if not isinstance(row_date, datetime):
                continue
            try:
                amount = float(row[3]) if row[3] is not None else None
            except (TypeError, ValueError):
                amount = None
            if amount is None:
                continue
            candidate_row = {
                "date": row_date.date(),
                "merchant": str(row[1]),
                "description": str(row[2]),
                "amount": amount,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": str(row[5]),
                "document_type": "import",
                "source_type": str(row[4] or "import"),
                "source_kind": "import",
            }
            report_rows.append(candidate_row)

        return build_household_reports(
            report_rows=report_rows,
            cadence_for_dates=self._dates_to_cadence,
            merchant_recommendation=self._merchant_recommendation,
        )

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

    def _extract_transactions(
        self,
        *,
        filename: str,
        source_type: str,
        document_type: str,
        extracted_text: str,
        structured_data: dict[str, Any],
        account_label: str | None,
        review_summary: str,
    ) -> list[ExtractedTransaction]:
        if not extracted_text and source_type != "receipt":
            return []

        transactions: list[ExtractedTransaction] = []
        if filename.lower().endswith((".ofx", ".qfx")) or "<stmttrn>" in extracted_text.lower():
            transactions.extend(self._parse_ofx_transactions(extracted_text, account_label, source_type))
        elif source_type == "credit_card" and document_type == "statement":
            transactions.extend(self._parse_chase_statement(extracted_text, account_label))
        elif source_type == "bank" and document_type == "statement":
            transactions.extend(self._parse_wells_fargo_statement(extracted_text, account_label))

        if (
            source_type == "receipt"
            and isinstance(structured_data.get("merchant"), str)
            and isinstance(structured_data.get("total_amount"), str)
        ):
            candidate = structured_data.get("statement_period")
            parsed_date = _parse_date_value(str(candidate)) if isinstance(candidate, str) else None
            if parsed_date is None:
                dm = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", extracted_text)
                parsed_date = _parse_date_value(dm.group(1)) if dm else None
            parsed_amount = _parse_decimal(str(structured_data.get("total_amount")))
            if parsed_date is not None and parsed_amount is not None:
                category, essentiality = _classify_merchant(
                    raw_merchant=str(structured_data["merchant"]),
                    description=review_summary or filename,
                    amount=float(parsed_amount),
                )
                transactions.append(
                    ExtractedTransaction(
                        transaction_date=parsed_date,
                        description=review_summary or filename,
                        raw_merchant=str(structured_data["merchant"]),
                        amount=parsed_amount,
                        flow_type="expense",
                        category=category,
                        essentiality=essentiality,
                        confidence=RECEIPT_CONFIDENCE,
                        account_label=account_label or str(structured_data.get("account_hint") or ""),
                        metadata={"source": "receipt_summary"},
                    )
                )

        return transactions

    def _parse_ofx_transactions(
        self,
        extracted_text: str,
        account_label: str | None,
        source_type: str,
    ) -> list[ExtractedTransaction]:
        rows: list[ExtractedTransaction] = []
        blocks = re.findall(r"(?is)<stmttrn>(.*?)(?:</stmttrn>|(?=<stmttrn>|$))", extracted_text)
        for raw_block in blocks:
            date_match = re.search(r"(?is)<dtposted>\s*([0-9]{8})", raw_block)
            amount_match = re.search(r"(?is)<trnamt>\s*([-+]?\d[\d.,]*)", raw_block)
            name_match = re.search(r"(?is)<name>\s*([^\n<]+)", raw_block)
            memo_match = re.search(r"(?is)<memo>\s*([^\n<]+)", raw_block)
            fitid_match = re.search(r"(?is)<fitid>\s*([^\n<]+)", raw_block)
            if not date_match or not amount_match:
                continue
            try:
                transaction_date = datetime.strptime(date_match.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            amount = _parse_decimal(amount_match.group(1))
            if amount is None:
                continue
            description = (
                name_match.group(1).strip()
                if name_match
                else memo_match.group(1).strip()
                if memo_match
                else "OFX transaction"
            )
            normalized_amount = abs(amount)
            if source_type == "credit_card":
                flow_type = "expense" if amount < 0 else "payment"
            else:
                flow_type = "expense" if amount < 0 else "income"
                if flow_type == "income" and "transfer" in description.lower():
                    flow_type = "transfer_in"
            category, essentiality = _classify_merchant(
                raw_merchant=description,
                description=description,
                amount=float(normalized_amount),
            )
            rows.append(
                ExtractedTransaction(
                    transaction_date=transaction_date,
                    description=description,
                    raw_merchant=description,
                    amount=normalized_amount,
                    flow_type=flow_type,
                    category=category,
                    essentiality=essentiality,
                    confidence=0.95,
                    account_label=account_label,
                    metadata={
                        "source": "ofx_export",
                        "fitid": fitid_match.group(1).strip() if fitid_match else None,
                    },
                )
            )
        return rows

    def _parse_chase_statement(
        self,
        extracted_text: str,
        account_label: str | None,
    ) -> list[ExtractedTransaction]:
        statement_date = _extract_statement_date(extracted_text)
        if statement_date is None:
            return []

        rows: list[ExtractedTransaction] = []
        in_activity = False
        for raw_line in extracted_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "Date of Transaction Merchant Name or Transaction Description" in line:
                in_activity = True
                continue
            if not in_activity:
                continue
            if line.startswith("Fees Charged") or line.startswith("Interest Charged"):
                break

            match = re.match(
                r"^(?P<date>\d{2}/\d{2})\s+(?:&\s+)?(?P<desc>.+?)\s+(?P<amount>-?\d[\d,]*\.\d{2})$",
                line,
            )
            if not match:
                continue

            transaction_date = _statement_transaction_date(
                raw_date=match.group("date"),
                statement_date=statement_date,
            )
            if transaction_date is None:
                continue

            description = match.group("desc").strip()
            amount = _parse_decimal(match.group("amount"))
            if amount is None:
                continue
            flow_type = _classify_statement_flow(description)
            if flow_type != "expense":
                amount = abs(amount)
            category, essentiality = _classify_merchant(raw_merchant=description, description=description, amount=float(abs(amount)))
            rows.append(
                ExtractedTransaction(
                    transaction_date=transaction_date,
                    description=description,
                    raw_merchant=description,
                    amount=abs(amount),
                    flow_type=flow_type,
                    category=category,
                    essentiality=essentiality,
                    confidence=CHASE_STATEMENT_CONFIDENCE,
                    account_label=account_label,
                    metadata={"source": "statement_activity"},
                )
            )
        return rows

    def _parse_wells_fargo_statement(
        self,
        extracted_text: str,
        account_label: str | None,
    ) -> list[ExtractedTransaction]:
        if "Transaction history" not in extracted_text:
            return []

        statement_date = _extract_statement_date(extracted_text)
        section = extracted_text.split("Transaction history", maxsplit=1)[1]
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        rows: list[ExtractedTransaction] = []
        current_date: date | None = None
        description_parts: list[str] = []

        for line in lines:
            if line.startswith("Totals") or line.startswith("Monthly service fee summary"):
                break

            date_match = re.match(r"^(?P<month>\d{1,2})/(?P<day>\d{1,2})\s+(?P<rest>.+)$", line)
            if date_match:
                month = int(date_match.group("month"))
                day = int(date_match.group("day"))
                rest = date_match.group("rest").strip()
                amounts = re.findall(r"\d[\d,]*\.\d{2}", rest)
                parsed_date = (
                    _statement_transaction_date(
                        raw_date=f"{month:02d}/{day:02d}",
                        statement_date=statement_date,
                    )
                    if statement_date is not None
                    else None
                )
                amount = (
                    _parse_decimal(amounts[-2] if len(amounts) >= 2 else amounts[0])
                    if parsed_date is not None and amounts
                    else None
                )
                if amount is not None and parsed_date is not None:
                    description = re.sub(r"\d[\d,]*\.\d{2}", "", rest).strip()
                    flow_type = _classify_wells_flow(description)
                    category, essentiality = _classify_merchant(raw_merchant=description, description=description, amount=float(amount))
                    rows.append(
                        ExtractedTransaction(
                            transaction_date=parsed_date,
                            description=description,
                            raw_merchant=description,
                            amount=amount,
                            flow_type=flow_type,
                            category=category,
                            essentiality=essentiality,
                            confidence=WELLS_FARGO_STATEMENT_CONFIDENCE,
                            account_label=account_label,
                            metadata={"source": "bank_statement"},
                        )
                    )
                    current_date = None
                    description_parts = []
                    continue
                current_date = parsed_date
                description_parts = [rest]
                continue

            if current_date is None:
                continue

            amounts = re.findall(r"\d[\d,]*\.\d{2}", line)
            if amounts:
                amount = _parse_decimal(amounts[0])
                if amount is None:
                    continue
                description = " ".join(description_parts).strip()
                flow_type = _classify_wells_flow(description)
                category, essentiality = _classify_merchant(raw_merchant=description, description=description, amount=float(amount))
                rows.append(
                    ExtractedTransaction(
                        transaction_date=current_date,
                        description=description,
                        raw_merchant=description,
                        amount=amount,
                        flow_type=flow_type,
                        category=category,
                        essentiality=essentiality,
                        confidence=0.82,
                        account_label=account_label,
                        metadata={"source": "bank_statement"},
                    )
                )
                current_date = None
                description_parts = []
                continue

            description_parts.append(line)
        return rows

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
            category = str(existing[2] or category)
            essentiality = str(existing[3] or essentiality)
            metadata = existing[4] if isinstance(existing[4], dict) else {}
            has_manual_rule = bool(metadata.get("manual_rule")) if isinstance(metadata, dict) else False
            merged_aliases = sorted({*(metadata.get("alias_keys", []) if isinstance(metadata, dict) else []), *alias_keys})
            conn.execute(
                """
                UPDATE household_merchants
                SET display_name = %s,
                    primary_category = COALESCE(primary_category, %s),
                    essentiality = COALESCE(essentiality, %s),
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
        if len(intervals) < 2:
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

        confidence = CADENCE_CONFIDENCE_MINIMAL if len(ordered_dates) == MIN_DATES_FOR_CADENCE else CADENCE_CONFIDENCE_STANDARD
        return {
            "label": label,
            "confidence": confidence,
            "rationale": (
                f"Jenny found {len(ordered_dates)} dated merchant events with a median gap of "
                f"{median_interval} days."
            ),
        }

    def _merchant_recommendation(self, *, merchant: str, category: str, cadence: str) -> str:
        if category == "Groceries" and cadence in {"likely weekly", "likely bi-weekly"}:
            return f"Use {merchant} as a budget anchor and compare it against Publix, Whole Foods, and Amazon for recurring essentials."
        if category == "Subscriptions":
            return f"Audit {merchant} for downgrade or cancellation opportunities."
        if category == "Retail":
            return f"Treat {merchant} as a discretionary merchant until Jenny proves it is mostly essentials."
        return f"Keep tracking {merchant} so Jenny can tighten category and card-optimization guidance."
