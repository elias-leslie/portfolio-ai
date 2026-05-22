"""Receipt line-item extraction helpers for the household document pipeline."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_utils import parse_decimal_value

_RECEIPT_RECONCILIATION_TOLERANCE = Decimal("0.05")


# ---------------------------------------------------------------------------
# Small scalar helpers
# ---------------------------------------------------------------------------


def _string_value(value: object) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _first_present_value(raw: dict[str, object], keys: tuple[str, ...]) -> object:
    for key in keys:
        value = raw.get(key)
        if value not in (None, ""):
            return value
    return None


def _decimal_value(value: object) -> Decimal | None:
    return parse_decimal_value(_string_value(value))


def _close_money(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= _RECEIPT_RECONCILIATION_TOLERANCE


# ---------------------------------------------------------------------------
# Line-item amount extraction
# ---------------------------------------------------------------------------


def _receipt_line_item_amounts(line_items: object) -> list[Decimal]:
    if not isinstance(line_items, list):
        return []
    amounts: list[Decimal] = []
    for raw_item in line_items:
        if not isinstance(raw_item, dict):
            continue
        description = _string_value(raw_item.get("description") or raw_item.get("name"))
        if not description:
            continue
        amount = _decimal_value(_first_present_value(raw_item, ("amount", "total", "price")))
        if amount is not None:
            amounts.append(amount)
    return amounts


def _receipt_line_item_quantity_total(line_items: object) -> Decimal:
    if not isinstance(line_items, list):
        return Decimal("0")
    total = Decimal("0")
    for raw_item in line_items:
        if not isinstance(raw_item, dict):
            continue
        description = _string_value(raw_item.get("description") or raw_item.get("name"))
        amount = _decimal_value(_first_present_value(raw_item, ("amount", "total", "price")))
        if not description or amount is None:
            continue
        quantity = _decimal_value(raw_item.get("quantity")) or Decimal("1")
        total += quantity
    return total


def _declared_item_count(value: object) -> Decimal | None:
    parsed = _decimal_value(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _receipt_items_cover_declared_count(
    *, line_items: object, declared_items_sold: object
) -> bool:
    declared = _declared_item_count(declared_items_sold)
    if declared is None:
        return True
    return _receipt_line_item_quantity_total(line_items) >= declared


# ---------------------------------------------------------------------------
# Reconciliation check
# ---------------------------------------------------------------------------


def _receipt_line_items_reconcile(
    *,
    line_items: object,
    receipt_total: object,
    subtotal: object,
    tax_amount: object,
    declared_items_sold: object = None,
) -> bool:
    if not _receipt_items_cover_declared_count(
        line_items=line_items,
        declared_items_sold=declared_items_sold,
    ):
        return False
    amounts = _receipt_line_item_amounts(line_items)
    if not amounts:
        return False
    line_total = sum(amounts, Decimal("0"))
    total = _decimal_value(receipt_total)
    subtotal_amount = _decimal_value(subtotal)
    tax = _decimal_value(tax_amount)
    candidates = [c for c in (total, subtotal_amount) if c is not None]
    if subtotal_amount is not None and tax is not None:
        candidates.append(subtotal_amount + tax)
    return any(_close_money(line_total, c) for c in candidates)


# ---------------------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------------------


def _receipt_line_item_row(
    *,
    document: HouseholdDocument,
    receipt_index: int,
    line_index: int,
    raw_item: dict[str, object],
    context: dict[str, str | None],
) -> dict[str, str | None] | None:
    description = _string_value(raw_item.get("description") or raw_item.get("name"))
    amount = _string_value(_first_present_value(raw_item, ("amount", "total", "price")))
    receipt_date = context["receipt_date"]
    if not description or not amount or not receipt_date:
        return None
    return {
        "Document ID": document.id,
        "External Row ID": f"{document.id}:{receipt_index}:{line_index}",
        "Receipt Index": str(receipt_index),
        "Line Index": str(line_index),
        "Order Date": receipt_date,
        "Merchant": context["merchant"],
        "Product Name": description,
        "Description": description,
        "Total Amount": amount,
        "Unit Price": _string_value(raw_item.get("unit_price")) or amount,
        "Original Quantity": _string_value(raw_item.get("quantity")) or "1",
        "Currency": context["currency"] or "USD",
        "Payment Method": context["payment_method"],
        "Account Mask": context["account_mask"],
        "Account Label": context["account_label"],
        "Receipt Total": context["receipt_total"],
        "Source": "receipt_line_item",
    }


def _append_receipt_line_item_rows(
    rows: list[dict[str, str | None]],
    *,
    document: HouseholdDocument,
    receipt_index: int,
    line_items: object,
    context: dict[str, str | None],
) -> None:
    if not isinstance(line_items, list):
        return
    if not _receipt_line_items_reconcile(
        line_items=line_items,
        receipt_total=context["receipt_total"],
        subtotal=context["subtotal"],
        tax_amount=context["tax_amount"],
        declared_items_sold=context["declared_items_sold"],
    ):
        return
    for line_index, raw_item in enumerate(line_items):
        if not isinstance(raw_item, dict):
            continue
        row = _receipt_line_item_row(
            document=document,
            receipt_index=receipt_index,
            line_index=line_index,
            raw_item=raw_item,
            context=context,
        )
        if row is not None:
            rows.append(row)


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------


def _structured_data_dict(reviewed: dict[str, object]) -> dict[str, object]:
    structured_data = reviewed.get("structured_data")
    return cast(dict[str, object], structured_data) if isinstance(structured_data, dict) else {}


def _review_checks_dict(reviewed: dict[str, object]) -> dict[str, object]:
    review_checks = reviewed.get("review_checks")
    return cast(dict[str, object], review_checks) if isinstance(review_checks, dict) else {}


def _build_transaction_context(
    raw_transaction: dict[str, object],
    structured_data: dict[str, object],
    review_declared_items_sold: object,
    structured_declared_items_sold: object,
) -> dict[str, str | None]:
    payment_method = _string_value(raw_transaction.get("payment_method"))
    account_mask = _string_value(raw_transaction.get("account_mask"))
    account_label = (
        _string_value(structured_data.get("upload_account_label"))
        or _string_value(structured_data.get("account_hint"))
        or " ".join(part for part in (payment_method, account_mask) if part)
        or None
    )
    return {
        "merchant": (
            _string_value(raw_transaction.get("merchant"))
            or _string_value(structured_data.get("merchant"))
        ),
        "receipt_date": _string_value(raw_transaction.get("date")),
        "receipt_total": _string_value(raw_transaction.get("amount")),
        "currency": (
            _string_value(raw_transaction.get("currency"))
            or _string_value(structured_data.get("currency"))
        ),
        "payment_method": payment_method,
        "account_mask": account_mask,
        "account_label": account_label,
        "subtotal": _string_value(
            _first_present_value(raw_transaction, ("subtotal", "subtotal_amount", "pre_tax_total"))
        ),
        "tax_amount": _string_value(
            _first_present_value(
                raw_transaction, ("tax_amount", "sales_tax", "tax", "total_tax")
            )
        ),
        "declared_items_sold": _string_value(
            _first_present_value(raw_transaction, ("declared_items_sold", "items_sold"))
            or review_declared_items_sold
            or structured_declared_items_sold
        ),
    }


def _build_top_level_context(
    structured_data: dict[str, object],
    review_declared_items_sold: object,
    structured_declared_items_sold: object,
) -> dict[str, str | None]:
    return {
        "merchant": _string_value(structured_data.get("merchant")),
        "receipt_date": _string_value(structured_data.get("statement_period")),
        "receipt_total": _string_value(structured_data.get("total_amount")),
        "currency": _string_value(structured_data.get("currency")),
        "payment_method": _string_value(structured_data.get("payment_method")),
        "account_mask": _string_value(structured_data.get("account_mask")),
        "account_label": (
            _string_value(structured_data.get("upload_account_label"))
            or _string_value(structured_data.get("account_hint"))
        ),
        "subtotal": _string_value(
            _first_present_value(structured_data, ("subtotal", "subtotal_amount", "pre_tax_total"))
        ),
        "tax_amount": _string_value(
            _first_present_value(
                structured_data, ("tax_amount", "sales_tax", "tax", "total_tax")
            )
        ),
        "declared_items_sold": _string_value(
            review_declared_items_sold or structured_declared_items_sold
        ),
    }


def receipt_line_item_rows(
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> list[dict[str, str | None]]:
    """Return validated receipt line-item rows ready for import."""
    structured_data = _structured_data_dict(reviewed)
    if str(reviewed.get("source_type") or document.source_type) != "receipt":
        return []

    rows: list[dict[str, str | None]] = []
    review_checks = _review_checks_dict(reviewed)
    itemization_checks = review_checks.get("itemization")
    itemization_checks = itemization_checks if isinstance(itemization_checks, dict) else {}

    structured_declared_items_sold = _first_present_value(
        structured_data, ("declared_items_sold", "items_sold")
    )
    review_declared_items_sold = _first_present_value(
        itemization_checks, ("declared_items_sold", "items_sold")
    )

    raw_transactions = structured_data.get("transactions")
    if isinstance(raw_transactions, list):
        for receipt_index, raw_transaction in enumerate(raw_transactions):
            if not isinstance(raw_transaction, dict):
                continue
            context = _build_transaction_context(
                raw_transaction,
                structured_data,
                review_declared_items_sold,
                structured_declared_items_sold,
            )
            _append_receipt_line_item_rows(
                rows,
                document=document,
                receipt_index=receipt_index,
                line_items=raw_transaction.get("line_items"),
                context=context,
            )

    _append_receipt_line_item_rows(
        rows,
        document=document,
        receipt_index=0,
        line_items=structured_data.get("line_items"),
        context=_build_top_level_context(
            structured_data,
            review_declared_items_sold,
            structured_declared_items_sold,
        ),
    )
    return rows
