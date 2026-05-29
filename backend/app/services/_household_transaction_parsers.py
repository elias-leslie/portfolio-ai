"""Document transaction parsers for household finance imports."""

from __future__ import annotations

import re
from csv import reader as csv_reader
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.services._household_document_pipeline_utils import parse_decimal_value
from app.services._household_merchants import (
    _classification_for_flow,
    _classify_merchant,
    _classify_statement_flow,
    _classify_wells_flow,
    _is_refund_like_text,
)
from app.services._household_spend_filters import looks_like_investment_activity

RECEIPT_CONFIDENCE = 0.9
CHASE_STATEMENT_CONFIDENCE = 0.88
WELLS_FARGO_STATEMENT_CONFIDENCE = 0.82


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


def _parse_date_value(raw_value: str) -> date | None:
    value = raw_value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _receipt_account_label(
    *,
    account_label: str | None,
    structured_data: dict[str, Any],
    transaction: dict[str, Any] | None = None,
) -> str | None:
    if account_label:
        return account_label
    if transaction is not None:
        payment_method = transaction.get("payment_method")
        account_mask = transaction.get("account_mask")
        if payment_method or account_mask:
            return " ".join(str(part) for part in (payment_method, account_mask) if part)
    hint = structured_data.get("account_hint")
    return str(hint) if hint else None


def _receipt_transaction_metadata(transaction: dict[str, Any]) -> dict[str, object]:
    metadata: dict[str, object] = {"source": "receipt_transaction"}
    for key in (
        "auth_code",
        "auth_time",
        "line_items",
        "payment_method",
        "trace_number",
        "transaction_type",
    ):
        value = transaction.get(key)
        if value not in (None, "", []):
            metadata[key] = value
    return metadata


def _extract_structured_receipt_transactions(
    *,
    transactions: object,
    structured_data: dict[str, Any],
    account_label: str | None,
    review_summary: str,
    filename: str,
) -> list[ExtractedTransaction]:
    if not isinstance(transactions, list):
        return []

    extracted: list[ExtractedTransaction] = []
    for raw_transaction in transactions:
        if not isinstance(raw_transaction, dict):
            continue
        merchant = str(raw_transaction.get("merchant") or structured_data.get("merchant") or "").strip()
        raw_date = raw_transaction.get("date")
        raw_amount = raw_transaction.get("amount")
        parsed_date = _parse_date_value(str(raw_date)) if raw_date is not None else None
        parsed_amount = parse_decimal_value(str(raw_amount)) if raw_amount is not None else None
        if not merchant or parsed_date is None or parsed_amount is None:
            continue
        description = str(raw_transaction.get("description") or review_summary or f"{merchant} receipt" or filename)
        category, essentiality = _classification_for_flow(
            raw_merchant=merchant,
            description=description,
            amount=float(parsed_amount),
            flow_type="expense",
        )
        extracted.append(
            ExtractedTransaction(
                transaction_date=parsed_date,
                description=description,
                raw_merchant=merchant,
                amount=parsed_amount,
                flow_type="expense",
                category=category,
                essentiality=essentiality,
                confidence=RECEIPT_CONFIDENCE,
                currency=str(raw_transaction.get("currency") or structured_data.get("currency") or "USD"),
                account_label=_receipt_account_label(
                    account_label=account_label,
                    structured_data=structured_data,
                    transaction=raw_transaction,
                ),
                metadata=_receipt_transaction_metadata(raw_transaction),
            )
        )
    return extracted


def _extract_statement_date(extracted_text: str) -> date | None:
    match = re.search(
        r"Statement Date:\s*(\d{2}/\d{2}/\d{2,4})",
        extracted_text,
        flags=re.IGNORECASE,
    )
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


def _normalize_csv_header(raw_value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", raw_value.strip().lower())
    return normalized.strip("_")


def _pick_csv_column(
    row: dict[str, str],
    *,
    exact: tuple[str, ...] = (),
    contains: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> str | None:
    for key in row:
        if key in exact:
            return key
    for key in row:
        if contains and not all(token in key for token in contains):
            continue
        if any(token in key for token in exclude):
            continue
        return key
    return None


def _looks_like_statement_csv(row: dict[str, str]) -> bool:
    date_key = _pick_csv_column(
        row,
        exact=("date", "transaction_date", "run_date", "activity_date", "trade_date", "posted_date"),
        contains=("date",),
        exclude=("settlement", "download"),
    )
    amount_key = _pick_csv_column(
        row,
        exact=("amount", "transaction_amount", "net_amount"),
        contains=("amount",),
        exclude=("subtotal", "price", "fee", "commission", "interest"),
    )
    description_key = _pick_csv_column(
        row,
        exact=("action", "description", "merchant", "memo", "payee", "name"),
        contains=("description",),
    )
    return date_key is not None and amount_key is not None and description_key is not None


def _extract_csv_signed_amount(row: dict[str, str]) -> Decimal | None:
    amount_key = _pick_csv_column(
        row,
        exact=("amount", "transaction_amount", "net_amount"),
        contains=("amount",),
        exclude=("subtotal", "price", "fee", "commission", "interest", "balance"),
    )
    if amount_key is not None:
        amount = parse_decimal_value(row.get(amount_key, ""))
        if amount is not None:
            return amount

    debit_key = _pick_csv_column(
        row,
        exact=("debit", "withdrawal", "outflow"),
        contains=("debit",),
        exclude=("card",),
    )
    credit_key = _pick_csv_column(
        row,
        exact=("credit", "deposit", "inflow"),
        contains=("credit",),
    )
    debit = parse_decimal_value(row.get(debit_key, "")) if debit_key is not None else None
    credit = parse_decimal_value(row.get(credit_key, "")) if credit_key is not None else None
    if debit is not None and debit != 0:
        return -abs(debit)
    if credit is not None and credit != 0:
        return abs(credit)
    return None


def _extract_csv_transaction_date(row: dict[str, str]) -> date | None:
    date_key = _pick_csv_column(
        row,
        exact=("date", "transaction_date", "run_date", "activity_date", "trade_date", "posted_date"),
        contains=("date",),
        exclude=("settlement", "download"),
    )
    if date_key is None:
        return None
    return _parse_date_value(row.get(date_key, ""))


def _extract_csv_posted_date(row: dict[str, str]) -> date | None:
    posted_key = _pick_csv_column(
        row,
        exact=("settlement_date", "posted_date", "posting_date"),
        contains=("settlement",),
    )
    if posted_key is None:
        return None
    return _parse_date_value(row.get(posted_key, ""))


def _compose_csv_description(row: dict[str, str]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for key in ("action", "description", "merchant", "payee", "name", "memo", "symbol", "type"):
        raw = row.get(key, "").strip()
        if not raw:
            continue
        normalized = raw.lower()
        if normalized in {"no description", "n/a", "na"}:
            continue
        if key == "type" and normalized in {"cash", "checking", "savings", "debit", "credit"}:
            continue
        dedupe_key = re.sub(r"\s+", " ", normalized)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        values.append(raw)
    return " | ".join(values) if values else "CSV transaction"


def _classify_statement_csv_flow(
    *,
    description: str,
    source_type: str,
    signed_amount: Decimal,
    category: str,
    essentiality: str,
) -> tuple[str, str, str]:
    normalized = description.lower()
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    is_positive = signed_amount > 0
    is_refund_like = _is_refund_like_text(
        raw_merchant=description,
        description=description,
    )
    transfer_category = ("Transfers", "mixed")
    resolved_flow: str | None = None
    resolved_category = category
    resolved_essentiality = essentiality

    income_tokens = ("dividend", "interest paid", "interest received", "interest credit")
    transfer_tokens = ("funds transfer", "transfer received", "zelle", "online transfer")
    compact_transfer_tokens = ("epay", "cepay", "instxfer", "moneyline")

    if source_type == "credit_card":
        if signed_amount < 0:
            resolved_flow = "expense"
        else:
            resolved_flow = "refund" if is_refund_like else "payment"
    elif any(token in normalized for token in income_tokens):
        resolved_flow = "income"
    elif looks_like_investment_activity(description=description, merchant=description) or any(
        token in normalized for token in ("reinvestment", "reinvest", "sweep into")
    ):
        resolved_flow = "investment"
    elif is_refund_like:
        resolved_flow = "refund"
    elif "payment thank you" in normalized:
        resolved_flow = "payment"
    elif (
        any(token in normalized for token in transfer_tokens)
        or any(token in compact for token in compact_transfer_tokens)
        or category.lower() == "transfers"
    ):
        resolved_flow = "transfer_in" if is_positive else "transfer_out"

    if resolved_flow in {"payment", "transfer_in", "transfer_out", "investment"}:
        resolved_category, resolved_essentiality = transfer_category
    elif resolved_flow == "income":
        resolved_category, resolved_essentiality = "Income", "essential"
    elif resolved_flow == "refund":
        resolved_category, resolved_essentiality = _classify_merchant(
            raw_merchant=description,
            description=description,
            amount=float(abs(signed_amount)),
        )
    elif resolved_flow is None:
        if signed_amount < 0:
            resolved_flow = "expense"
        else:
            resolved_flow = "income"
            resolved_category, resolved_essentiality = "Income", "essential"

    return resolved_flow, resolved_category, resolved_essentiality


def parse_statement_csv(
    *,
    stored_path: Path,
    source_type: str,
    account_label: str | None,
) -> list[ExtractedTransaction]:
    try:
        with stored_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as handle:
            raw_reader = csv_reader(handle)
            headers: list[str] | None = None
            rows = []
            for raw_values in raw_reader:
                if not any((value or "").strip() for value in raw_values):
                    continue
                if headers is None:
                    headers = [str(value or "").strip() for value in raw_values]
                    continue
                normalized_row = {
                    _normalize_csv_header(header): (
                        raw_values[index].strip()
                        if index < len(raw_values) and raw_values[index] is not None
                        else ""
                    )
                    for index, header in enumerate(headers)
                    if header
                }
                if any(value for value in normalized_row.values()):
                    rows.append(normalized_row)
    except OSError:
        return []

    if not rows or not _looks_like_statement_csv(rows[0]):
        return []

    transactions: list[ExtractedTransaction] = []
    for row in rows:
        transaction_date = _extract_csv_transaction_date(row)
        signed_amount = _extract_csv_signed_amount(row)
        if transaction_date is None or signed_amount is None or signed_amount == 0:
            continue

        description = _compose_csv_description(row)
        category, essentiality = _classify_merchant(
            raw_merchant=description,
            description=description,
            amount=float(abs(signed_amount)),
        )
        flow_type, category, essentiality = _classify_statement_csv_flow(
            description=description,
            source_type=source_type,
            signed_amount=signed_amount,
            category=category,
            essentiality=essentiality,
        )
        transactions.append(
            ExtractedTransaction(
                transaction_date=transaction_date,
                posted_date=_extract_csv_posted_date(row),
                description=description,
                raw_merchant=description,
                amount=abs(signed_amount),
                flow_type=flow_type,
                category=category,
                essentiality=essentiality,
                confidence=0.84,
                account_label=account_label,
                metadata={
                    "source": "statement_csv",
                    "balance_after": row.get("cash_balance") or row.get("balance"),
                },
            )
        )
    return transactions


def parse_ofx_transactions(
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
        amount = parse_decimal_value(amount_match.group(1))
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
            if amount < 0:
                flow_type = "expense"
            else:
                flow_type = (
                    "refund"
                    if _is_refund_like_text(raw_merchant=description, description=description)
                    else "payment"
                )
        else:
            flow_type = "expense" if amount < 0 else "income"
            if flow_type == "income" and "transfer" in description.lower():
                flow_type = "transfer_in"
        category, essentiality = _classification_for_flow(
            raw_merchant=description,
            description=description,
            amount=float(normalized_amount),
            flow_type=flow_type,
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


def parse_chase_statement(
    extracted_text: str,
    account_label: str | None,
) -> list[ExtractedTransaction]:
    statement_date = _extract_statement_date(extracted_text)
    if statement_date is None:
        return []

    rows: list[ExtractedTransaction] = []
    in_activity = False
    activity_header = "Date of Transaction Merchant Name or Transaction Description"
    previous_normalized_line = ""
    for raw_line in extracted_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized_line = re.sub(r"\s+", " ", line)
        header_window = f"{previous_normalized_line} {normalized_line}".strip()
        if activity_header in normalized_line or activity_header in header_window:
            in_activity = True
            previous_normalized_line = normalized_line
            continue
        if not in_activity:
            previous_normalized_line = normalized_line
            continue
        if normalized_line.startswith("Fees Charged") or normalized_line.startswith("Interest Charged"):
            break

        match = re.match(
            r"^(?P<date>\d{2}/\d{2})\s+(?:&\s+)?(?P<desc>.+?)\s+(?P<amount>-?\d[\d,]*\.\d{2})$",
            line,
        )
        if not match:
            previous_normalized_line = normalized_line
            continue

        transaction_date = _statement_transaction_date(
            raw_date=match.group("date"),
            statement_date=statement_date,
        )
        if transaction_date is None:
            previous_normalized_line = normalized_line
            continue

        description = match.group("desc").strip()
        amount = parse_decimal_value(match.group("amount"))
        if amount is None:
            previous_normalized_line = normalized_line
            continue
        flow_type = _classify_statement_flow(description)
        if flow_type != "expense":
            amount = abs(amount)
        category, essentiality = _classification_for_flow(
            raw_merchant=description,
            description=description,
            amount=float(abs(amount)),
            flow_type=flow_type,
        )
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
        previous_normalized_line = normalized_line
    return rows


def parse_wells_fargo_statement(
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
                parse_decimal_value(amounts[-2] if len(amounts) >= 2 else amounts[0])
                if parsed_date is not None and amounts
                else None
            )
            if amount is not None and parsed_date is not None:
                description = re.sub(r"\d[\d,]*\.\d{2}", "", rest).strip()
                flow_type = _classify_wells_flow(description)
                category, essentiality = _classification_for_flow(
                    raw_merchant=description,
                    description=description,
                    amount=float(amount),
                    flow_type=flow_type,
                )
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
            amount = parse_decimal_value(amounts[0])
            if amount is None:
                continue
            description = " ".join(description_parts).strip()
            flow_type = _classify_wells_flow(description)
            category, essentiality = _classification_for_flow(
                raw_merchant=description,
                description=description,
                amount=float(amount),
                flow_type=flow_type,
            )
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


def extract_transactions(
    *,
    filename: str,
    source_type: str,
    document_type: str,
    extracted_text: str,
    structured_data: dict[str, Any],
    account_label: str | None,
    review_summary: str,
    stored_path: Path | None,
) -> list[ExtractedTransaction]:
    if not extracted_text and stored_path is None and source_type != "receipt":
        return []

    transactions: list[ExtractedTransaction] = []
    if filename.lower().endswith((".ofx", ".qfx")) or "<stmttrn>" in extracted_text.lower():
        transactions.extend(parse_ofx_transactions(extracted_text, account_label, source_type))
    elif (
        stored_path is not None
        and stored_path.suffix.lower() == ".csv"
        and source_type in {"bank", "credit_card", "brokerage"}
    ):
        transactions.extend(
            parse_statement_csv(
                stored_path=stored_path,
                source_type=source_type,
                account_label=account_label,
            )
        )
    elif source_type == "credit_card" and document_type == "statement":
        transactions.extend(parse_chase_statement(extracted_text, account_label))
    elif source_type == "bank" and document_type == "statement":
        transactions.extend(parse_wells_fargo_statement(extracted_text, account_label))

    if (
        source_type == "receipt"
        and isinstance(structured_data.get("merchant"), str)
        and (
            isinstance(structured_data.get("total_amount"), str)
            or isinstance(structured_data.get("transactions"), list)
        )
    ):
        structured_transactions = _extract_structured_receipt_transactions(
            transactions=structured_data.get("transactions"),
            structured_data=structured_data,
            account_label=account_label,
            review_summary=review_summary,
            filename=filename,
        )
        if structured_transactions:
            transactions.extend(structured_transactions)
            return transactions

        candidate = structured_data.get("statement_period")
        parsed_date = _parse_date_value(str(candidate)) if isinstance(candidate, str) else None
        if parsed_date is None:
            dm = re.search(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", extracted_text)
            parsed_date = _parse_date_value(dm.group(1)) if dm else None
        parsed_amount = parse_decimal_value(str(structured_data.get("total_amount")))
        if parsed_date is not None and parsed_amount is not None:
            category, essentiality = _classification_for_flow(
                raw_merchant=str(structured_data["merchant"]),
                description=review_summary or filename,
                amount=float(parsed_amount),
                flow_type="expense",
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
