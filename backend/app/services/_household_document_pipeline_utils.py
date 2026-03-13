"""Pure utility helpers for household document pipeline (no I/O, no DB)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.household_finance import HouseholdDocument


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
    "parse_decimal",
    "parse_row_date",
]
