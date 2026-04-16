"""Pure utility helpers for household document pipeline (no I/O, no DB)."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.household_finance import HouseholdDocument

_MONEY_SOURCE_TYPES = frozenset({"bank", "credit_card", "brokerage", "retirement"})
_SOURCE_DOCUMENT_TYPES = {
    "bank": "statement",
    "credit_card": "statement",
    "brokerage": "brokerage_statement",
    "retirement": "retirement_statement",
}
_BANK_ACCOUNT_TYPES = frozenset({"bank", "checking", "savings"})
_BROKERAGE_ACCOUNT_TYPES = frozenset({"brokerage", "529"})
_RETIREMENT_ACCOUNT_TYPES = frozenset(
    {"retirement", "ira", "roth_ira", "401k", "403b", "403_b", "457b", "457_b", "pension"}
)
_TRANSACTION_ACTIVITY_TERMS = (
    "activity",
    "amount",
    "cash balance",
    "debit",
    "description",
    "merchant",
    "posted transactions",
    "running balance",
    "transaction",
    "transactions",
)


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def infer_financial_account_source_type(
    account: dict[str, object],
    *,
    fallback_source_type: str | None = None,
) -> str | None:
    source_type = _clean_text(account.get("source_type"))
    account_type = _clean_text(account.get("account_type"))
    asset_group = _clean_text(account.get("asset_group"))
    institution_name = _clean_text(account.get("institution_name"))
    account_name = _clean_text(account.get("account_name") or account.get("account_hint"))
    fallback = _clean_text(fallback_source_type)

    resolved_source: str | None = None
    if source_type in _MONEY_SOURCE_TYPES:
        resolved_source = source_type
    elif account_type == "credit_card" or asset_group == "credit":
        resolved_source = "credit_card"
    elif account_type in _RETIREMENT_ACCOUNT_TYPES or asset_group == "retirement":
        resolved_source = "retirement"
    elif account_type in _BANK_ACCOUNT_TYPES:
        resolved_source = "bank"
    elif account_type in _BROKERAGE_ACCOUNT_TYPES or asset_group in {"taxable", "education"}:
        resolved_source = "brokerage"
    elif institution_name in {"chase", "american express", "amex", "discover", "capital one", "citi"}:
        if account_name and any(token in account_name for token in ("card", "visa", "mastercard", "amex")):
            resolved_source = "credit_card"
    elif institution_name in {"wells fargo", "bank of america", "regions", "ally", "truist"}:
        if account_name and any(token in account_name for token in ("checking", "savings", "bank")):
            resolved_source = "bank"
    elif institution_name in {"fidelity", "vanguard", "schwab", "etrade", "e*trade"}:
        resolved_source = "brokerage"
    elif fallback in _MONEY_SOURCE_TYPES:
        resolved_source = fallback

    return resolved_source


def looks_like_transaction_activity(
    *,
    source_type: str | None,
    document_type: str | None,
    extracted_text: str | None,
) -> bool:
    normalized_source = _clean_text(source_type)
    normalized_document = _clean_text(document_type)
    if normalized_source in {"bank", "credit_card"} and normalized_document == "statement":
        return True
    preview = (extracted_text or "")[:6000].lower()
    if not preview:
        return False
    signal_count = sum(1 for term in _TRANSACTION_ACTIVITY_TERMS if term in preview)
    if signal_count >= 2:
        return True
    return bool(
        re.search(
            r"date[^a-z0-9]{0,20}(description|merchant|amount|balance)",
            preview,
        )
    )


def normalize_financial_document_classification(
    *,
    reviewed: dict[str, object],
    fallback_source_type: str | None,
    fallback_document_type: str | None,
    filename: str | None = None,
    extracted_text: str | None = None,
) -> tuple[str, str]:
    current_source = _clean_text(reviewed.get("source_type")) or _clean_text(fallback_source_type) or "other"
    current_document = (
        _clean_text(reviewed.get("document_type")) or _clean_text(fallback_document_type) or "other"
    )
    structured_data = reviewed.get("structured_data")
    structured = structured_data if isinstance(structured_data, dict) else {}
    raw_accounts = structured.get("financial_accounts")
    accounts = (
        [account for account in raw_accounts if isinstance(account, dict)]
        if isinstance(raw_accounts, list)
        else []
    )

    source_counts = Counter(
        inferred
        for inferred in (
            infer_financial_account_source_type(account, fallback_source_type=current_source)
            for account in accounts
        )
        if inferred in _MONEY_SOURCE_TYPES
    )
    promoted_source: str | None = None
    if source_counts:
        if len(source_counts) == 1:
            promoted_source = next(iter(source_counts))
        else:
            most_common = source_counts.most_common()
            top_source, top_count = most_common[0]
            next_count = most_common[1][1]
            if top_count > next_count:
                promoted_source = top_source
            elif current_source in source_counts:
                promoted_source = current_source
    elif looks_like_transaction_activity(
        source_type=current_source,
        document_type=current_document,
        extracted_text=extracted_text,
    ):
        context = " ".join(
            str(value or "")
            for value in (
                filename,
                structured.get("provider_name"),
                structured.get("merchant"),
                structured.get("account_hint"),
            )
        ).lower()
        if any(token in context for token in ("chase", "visa", "mastercard", "amex", "discover")):
            promoted_source = "credit_card"
        elif any(token in context for token in ("wells fargo", "checking", "savings", "bank")):
            promoted_source = "bank"
        elif any(token in context for token in ("fidelity", "schwab", "vanguard", "brokerage")):
            promoted_source = "brokerage"
        elif "retirement" in context:
            promoted_source = "retirement"

    if promoted_source is not None:
        promoted_document = _SOURCE_DOCUMENT_TYPES[promoted_source]
        if current_source == "other" or current_document == "other" or current_source not in _MONEY_SOURCE_TYPES or (len(source_counts) == 1 and current_source != promoted_source):
            current_source = promoted_source
            current_document = promoted_document
        elif current_source == promoted_source and current_document != promoted_document:
            current_document = promoted_document

    if current_source in {"bank", "credit_card"} and looks_like_transaction_activity(
        source_type=current_source,
        document_type=current_document,
        extracted_text=extracted_text,
    ):
        current_document = "statement"

    return current_source, current_document


def classify_document(
    *,
    filename: str,
    content_type: str | None,
    source_type: str | None,
    document_type: str | None,
) -> tuple[str, str, float]:
    """Return (inferred_source, inferred_type, confidence) for an upload."""
    if source_type and document_type:
        return source_type, document_type, 0.99

    lowered = filename.lower()
    inferred_source = source_type or "other"
    inferred_type = document_type or "other"
    confidence = 0.55

    rules: list[tuple[list[str], str, str, float]] = [
        (["checking", "bank", "statement"], "bank", "statement", 0.82),
        (["visa", "mastercard", "amex", "credit"], "credit_card", "statement", 0.88),
        (["brokerage", "fidelity", "schwab", "vanguard"], "brokerage", "brokerage_statement", 0.9),
        (["ira", "401k", "roth", "retirement"], "retirement", "retirement_statement", 0.9),
        (["pay stub", "paystub", "payroll"], "income", "pay_stub", 0.92),
        (["w-2", "w2", "1099"], "tax", "w2_1099", 0.94),
        (["1040", "tax return", "taxreturn"], "tax", "tax_return", 0.94),
        (["mortgage"], "housing", "mortgage_statement", 0.92),
        (["heloc"], "debt", "heloc_statement", 0.92),
        (["student loan", "nelnet", "mohela", "aidvantage"], "debt", "student_loan_statement", 0.92),
        (["auto loan", "car loan"], "debt", "auto_loan_statement", 0.92),
        (["declarations", "policy summary"], "insurance", "insurance_declarations", 0.92),
        (["insurance policy", "policy"], "insurance", "insurance_policy", 0.86),
        (["social security", "ssa"], "retirement_income", "social_security_statement", 0.94),
        (["pension"], "retirement_income", "pension_statement", 0.92),
        (["benefits summary", "open enrollment", "benefits"], "benefits", "benefits_summary", 0.9),
        (["estimate", "quote", "contract"], "billing", "major_expense_support", 0.82),
        (["receipt", "walmart", "target", "costco"], "receipt", "receipt", 0.8),
        (["invoice", "bill", "utility", "insurance"], "billing", "invoice", 0.8),
    ]
    for tokens, src, doc_type, conf in rules:
        if any(t in lowered for t in tokens) and conf >= confidence:
            inferred_source = source_type or src
            inferred_type = document_type or doc_type
            confidence = conf

    if content_type and content_type.startswith("image/") and inferred_type == "other":
        inferred_type = "receipt"
        inferred_source = source_type or "receipt"
        confidence = max(confidence, 0.72)

    return inferred_source, inferred_type, confidence


def parse_row_date(value: str | None) -> str | None:
    """Parse an ISO-ish date string; return None on failure."""
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError:
        return None


def parse_decimal(value: str | None) -> str | None:
    """Parse a currency string to a plain Decimal string; return None on failure."""
    if value is None:
        return None
    normalized = value.strip().replace(",", "").replace("$", "")
    if not normalized or normalized.lower() in {"not available", "not applicable"}:
        return None
    if normalized.startswith("'") and normalized.endswith("'"):
        normalized = normalized[1:-1]
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return str(Decimal(normalized))
    except InvalidOperation:
        return None


def detect_import_dataset(
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> str | None:
    """Return dataset type key if the document should be imported as CSV rows."""
    if not document.filename.lower().endswith(".csv"):
        return None
    structured_data = reviewed.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}
    merchant = structured_data.get("merchant")
    if document.filename.lower() == "order history.csv" and merchant == "Amazon":
        return "amazon_order_history"
    return None


def build_import_row_hash(
    *,
    dataset_type: str,
    row: dict[str, str | None],
) -> str | None:
    """Compute a dedup hash for a CSV import row; return None if key fields are missing."""
    if dataset_type != "amazon_order_history":
        return None
    order_id = (row.get("Order ID") or "").strip()
    asin = (row.get("ASIN") or "").strip()
    order_date = (row.get("Order Date") or "").strip()
    if not order_id or not asin or not order_date:
        return None
    quantity = (row.get("Original Quantity") or "").strip()
    fingerprint = "|".join([dataset_type, order_id, asin, order_date, quantity])
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


# Expose datetime UTC for use from this module
__all__ = [
    "build_import_row_hash",
    "classify_document",
    "detect_import_dataset",
    "infer_financial_account_source_type",
    "looks_like_transaction_activity",
    "normalize_financial_document_classification",
    "parse_decimal",
    "parse_row_date",
]
