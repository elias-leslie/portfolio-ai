"""Deterministic baseline document review and question generation."""

from __future__ import annotations

import csv
import re
from datetime import datetime
from io import StringIO

# Text preview length for structured_data summaries
TEXT_PREVIEW_LENGTH = 500
# Default confidence for baseline (non-LLM) document reviews
BASELINE_REVIEW_CONFIDENCE = 0.45

_QuestionDict = dict[str, object]
_StructuredData = dict[str, object]


def _extract_amounts(extracted_text: str | None) -> tuple[str | None, str | None]:
    """Return (statement_period, total_amount) from extracted text."""
    if not extracted_text:
        return None, None
    period_match = re.search(
        r"([A-Z][a-z]+ \d{1,2}, \d{4}\s*(?:-|to)\s*[A-Z][a-z]+ \d{1,2}, \d{4})",
        extracted_text,
    )
    amount_match = re.search(
        r"(?:new balance|amount due|order total|total)\s*[:$]?\s*\$?([0-9][0-9,]*\.\d{2})",
        extracted_text,
        flags=re.IGNORECASE,
    )
    return (
        period_match.group(1) if period_match else None,
        amount_match.group(1) if amount_match else None,
    )


def _question_role() -> _QuestionDict:
    return {
        "field_name": None,
        "question": "What role should this document play in the household plan?",
        "priority": "medium",
        "question_format": "single_select",
        "options": [
            "Budgeting",
            "Cash-flow tracking",
            "Savings analysis",
            "Retirement planning",
            "Reference only",
        ],
        "recommendation": (
            "Confirm whether Jenny should use this for budgeting, cash-flow tracking,"
            " savings analysis, or only as a reference."
        ),
        "rationale": "Jenny could not confidently infer the full financial meaning from the file alone.",
    }


def _question_receipt_merchant(merchant: str) -> list[_QuestionDict]:
    return [
        {
            "field_name": None,
            "question": f"Should Jenny treat {merchant} orders like this as part of regular household spending?",
            "priority": "medium",
            "question_format": "boolean",
            "options": ["Yes", "No"],
            "recommendation": (
                f"Answer 'yes' if {merchant} is a recurring household shopping channel"
                " for groceries, consumables, or home goods."
            ),
            "rationale": "This helps Jenny separate recurring household shopping from one-off discretionary purchases.",
        }
    ]


def _question_bank_account(account_hint: str) -> list[_QuestionDict]:
    return [
        {
            "field_name": "monthly_essential_target",
            "question": f"Is {account_hint} your primary account for monthly bills, deposits, and budget tracking?",
            "priority": "high",
            "question_format": "boolean",
            "options": ["Yes", "No"],
            "recommendation": (
                "Answer 'yes' if most paycheck deposits, bill payments, and core household"
                " cash flow pass through this account."
            ),
            "rationale": "Primary checking accounts anchor the household cash-flow model.",
        }
    ]


def _question_credit_card_account(account_hint: str) -> list[_QuestionDict]:
    return [
        {
            "field_name": "monthly_essential_target",
            "question": f"Should Jenny treat {account_hint} as part of core household spending?",
            "priority": "high",
            "question_format": "boolean",
            "options": ["Yes", "No"],
            "recommendation": (
                "Answer 'yes' if this card is used for regular groceries, household shopping,"
                " subscriptions, or recurring family spending."
            ),
            "rationale": "This determines whether Jenny should treat the card as budget-driving spend data.",
        }
    ]


def _question_unknown_document() -> _QuestionDict:
    return {
        "field_name": None,
        "question": "What kind of document is this and which account or merchant is it tied to?",
        "priority": "high",
        "question_format": "long_text",
        "recommendation": (
            "Name the merchant or institution and say whether this is a receipt,"
            " order confirmation, or statement."
        ),
        "rationale": "Jenny could not confidently identify the institution, account, or document class from the file alone.",
    }


def _question_core_spending() -> _QuestionDict:
    return {
        "field_name": "monthly_essential_target",
        "question": "Is this account part of your core monthly household spending?",
        "priority": "high",
        "question_format": "boolean",
        "options": ["Yes", "No"],
        "recommendation": "Confirm if this account covers regular household bills, groceries, or everyday spending.",
        "rationale": "This determines whether Jenny should treat the spend as budget-driving data.",
    }


def _question_retirement() -> _QuestionDict:
    return {
        "field_name": "target_retirement_spend",
        "question": "Should this account count toward retirement readiness tracking?",
        "priority": "medium",
        "question_format": "boolean",
        "options": ["Yes", "No"],
        "recommendation": (
            "Confirm if this is a retirement or long-term investment account that should"
            " shape future-income planning."
        ),
        "rationale": "Jenny needs to know whether the account is part of the retirement plan or general savings.",
    }


def _build_questions(
    *,
    source_type: str,
    document_type: str,
    summary: str,
    merchant: object,
    account_hint: object,
) -> list[_QuestionDict]:
    if source_type == "receipt" and isinstance(merchant, str) and merchant:
        return _question_receipt_merchant(merchant)
    if source_type == "bank" and isinstance(account_hint, str) and account_hint:
        return _question_bank_account(account_hint)
    if source_type == "credit_card" and isinstance(account_hint, str) and account_hint:
        return _question_credit_card_account(account_hint)

    questions: list[_QuestionDict] = [_question_role()]

    if source_type == "other" or document_type == "other":
        questions.append(_question_unknown_document())
    if source_type in {"bank", "credit_card"}:
        questions.append(_question_core_spending())
    if source_type in {"retirement", "brokerage"}:
        questions.append(_question_retirement())
    if "keep refining" not in summary.lower():
        questions[0]["rationale"] = f"{questions[0]['rationale']} Current best read: {summary}"

    return questions


def _classify_amazon(text_lower: str, structured_data: _StructuredData) -> tuple[str, str, float, str]:
    structured_data["merchant"] = "Amazon"
    if "total amount" in text_lower or "unit price" in text_lower or "shipping charge" in text_lower:
        summary = "Amazon order history export with order pricing, shipping, and item-level purchase detail."
    else:
        summary = "Amazon order history export covering household purchases over time."
    return "receipt", "receipt", 0.9, summary


def _classify_walmart(structured_data: _StructuredData) -> tuple[str, str, float, str]:
    structured_data["merchant"] = "Walmart"
    return "receipt", "receipt", 0.84, "Walmart order details with household shopping line items."


def _classify_wells_fargo(structured_data: _StructuredData) -> tuple[str, str, float, str]:
    structured_data["account_hint"] = "Wells Fargo Everyday Checking"
    return "bank", "statement", 0.88, "Wells Fargo Everyday Checking statement showing household cash activity."


def _classify_chase_amazon(structured_data: _StructuredData) -> tuple[str, str, float, str]:
    structured_data["account_hint"] = "Chase Amazon card"
    return "credit_card", "statement", 0.86, "Chase Amazon credit-card statement with monthly household spending."


def _classify_529(structured_data: _StructuredData) -> tuple[str, str, float, str]:
    structured_data["account_hint"] = "529 college savings account"
    return "brokerage", "brokerage_statement", 0.9, "529 college savings account snapshot with beneficiary balances."


def _parse_natural_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.strip().split())
    for pattern in ("%B %d, %Y", "%b %d, %Y", "%b-%d-%Y", "%B-%d-%Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(cleaned, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_csv_header(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.replace("\ufeff", "").strip().lower())
    return normalized.strip("_")


def _csv_rows_from_text(extracted_text: str | None) -> tuple[list[str], list[dict[str, str]]]:
    if not extracted_text:
        return [], []
    reader = csv.reader(StringIO(extracted_text.lstrip("\ufeff")))
    headers: list[str] | None = None
    normalized_headers: list[str] = []
    rows: list[dict[str, str]] = []
    for raw_row in reader:
        cleaned = [str(cell or "").strip() for cell in raw_row]
        if not any(cleaned):
            continue
        if headers is None:
            headers = cleaned
            normalized_headers = [_normalize_csv_header(cell) for cell in cleaned]
            continue
        padded = cleaned + [""] * max(0, len(normalized_headers) - len(cleaned))
        row_dict = {
            normalized_headers[index]: padded[index]
            for index in range(len(normalized_headers))
            if normalized_headers[index]
        }
        if row_dict:
            rows.append(row_dict)
    return normalized_headers, rows


def _numeric_string(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"[-+]?\$?([0-9][0-9,]*\.\d+)", value)
    return match.group(1).replace(",", "") if match else None


def _float_value(value: str | None) -> float | None:
    numeric = _numeric_string(value)
    if numeric is None:
        return None
    try:
        return float(numeric)
    except ValueError:
        return None


def _extract_cash_management_account(text: str) -> dict[str, object] | None:
    balance_match = re.search(
        r"account total balance(?: on date:\s*([A-Za-z]{3,9}[- ][0-9]{1,2}(?:,|-)[0-9]{4}))?(?: is)?\s*,?\s*\$([0-9][0-9,]*\.\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    if balance_match is None:
        return None
    available_cash_match = re.search(
        r"cash available to withdraw\s*\$([0-9][0-9,]*\.\d{2})",
        text,
        flags=re.IGNORECASE,
    )
    account_name_match = re.search(
        r"(?im)^(cash management(?:\s*\([^)\n]+\))?)\s*$",
        text,
    )
    account_mask_match = re.search(
        r"cash account:\s*([A-Za-z0-9*]+)",
        text,
        flags=re.IGNORECASE,
    )
    account_hint = account_name_match.group(1).strip() if account_name_match else "Cash Management"
    as_of_match = re.search(
        r"as of\s*([A-Za-z]{3,9}[- ][0-9]{1,2}(?:,|-)[0-9]{4})",
        text,
        flags=re.IGNORECASE,
    )
    as_of_date = _parse_natural_date(as_of_match.group(1) if as_of_match else None)
    if as_of_date is None:
        as_of_date = _parse_natural_date(balance_match.group(1))
    has_activity_table = bool(
        re.search(r"activity\s*&\s*orders", text, flags=re.IGNORECASE)
        or re.search(r"recent activity", text, flags=re.IGNORECASE)
    )
    has_activity_rows = bool(
        re.search(
            r"(?m)^[A-Z][a-z]{2}[-/][0-9]{2}[-/][0-9]{4}\s*$",
            text,
        )
        or re.search(
            r"[A-Z][a-z]{2}[-/][0-9]{2}[-/][0-9]{4}",
            text,
        )
        or re.search(
            r"(?m)^[A-Z][a-z]{2}-[0-9]{2}-[0-9]{4}\n.+\n[-+]?\$?[0-9][0-9,]*\.\d{2}",
            text,
        )
    )
    return {
        "asset_group": "taxable",
        "account_type": "brokerage",
        "account_name": account_hint,
        "account_hint": account_hint,
        "account_mask": account_mask_match.group(1).strip() if account_mask_match is not None else None,
        "balance": balance_match.group(2),
        "cash_balance": (
            available_cash_match.group(1) if available_cash_match is not None else balance_match.group(2)
        ),
        "currency": "USD",
        "as_of_date": as_of_date,
        "activity_observed_through": as_of_date if has_activity_table and has_activity_rows else None,
    }


def _classify_cash_management(
    extracted_text: str | None,
    structured_data: _StructuredData,
) -> tuple[str, str, float, str]:
    account = _extract_cash_management_account(extracted_text or "")
    if account is not None:
        structured_data["account_hint"] = account["account_hint"]
        structured_data["financial_accounts"] = [account]
        if account.get("balance") is not None:
            structured_data["total_amount"] = account["balance"]
        if account.get("as_of_date") is not None:
            structured_data["statement_period"] = f"As of {account['as_of_date']}"
    return (
        "brokerage",
        "brokerage_statement",
        0.9,
        "Cash management account snapshot with recent activity, balance details, and available cash.",
    )


def _extract_statement_csv_account(
    *,
    filename: str,
    extracted_text: str | None,
) -> dict[str, object] | None:
    if not extracted_text:
        return None
    normalized_headers, data_rows = _csv_rows_from_text(extracted_text)
    if not normalized_headers or not data_rows:
        return None
    header_set = set(normalized_headers)
    if not {"run_date", "action", "amount", "cash_balance"}.issubset(header_set):
        return None

    first_row = data_rows[0]
    account_mask_match = re.search(
        r"(?:history|activity|transactions?)_for_account_([A-Za-z0-9*]+)",
        filename,
        flags=re.IGNORECASE,
    )
    account_mask = account_mask_match.group(1).strip() if account_mask_match is not None else None
    as_of_date = _parse_natural_date(first_row.get("run_date"))
    balance = first_row.get("cash_balance") or None
    if not balance:
        return None

    account_hint = f"Account {account_mask}" if account_mask else "Imported cash account"
    return {
        "asset_group": "taxable",
        "account_type": "brokerage",
        "account_name": account_hint,
        "account_hint": account_hint,
        "account_mask": account_mask,
        "balance": balance,
        "cash_balance": balance,
        "currency": "USD",
        "as_of_date": as_of_date,
        "activity_observed_through": as_of_date,
    }


def _fidelity_account_type(account_name: str) -> tuple[str, str, str]:
    normalized = account_name.lower()
    if "roth" in normalized:
        return "retirement", "roth_ira", "retirement"
    if "traditional ira" in normalized or "rollover ira" in normalized or normalized.endswith(" ira"):
        return "retirement", "ira", "retirement"
    if "529" in normalized:
        return "education", "529", "education"
    return "taxable", "brokerage", "brokerage"


def _extract_fidelity_positions_accounts(
    *,
    extracted_text: str | None,
) -> tuple[str, str, float, str, _StructuredData] | None:
    headers, rows = _csv_rows_from_text(extracted_text)
    required = {"account_number", "account_name", "symbol", "description", "current_value", "type"}
    if not required.issubset(set(headers)):
        return None

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        account_number = row.get("account_number", "").strip()
        account_name = row.get("account_name", "").strip()
        current_value = _float_value(row.get("current_value"))
        if not account_number or not account_name or current_value is None:
            continue
        asset_group, account_type, source_type = _fidelity_account_type(account_name)
        group = grouped.setdefault(
            (account_number, account_name),
            {
                "balance_total": 0.0,
                "cash_total": 0.0,
                "holdings": [],
                "asset_group": asset_group,
                "account_type": account_type,
                "source_type": source_type,
                "account_number": account_number,
                "account_name": account_name,
            },
        )
        symbol = row.get("symbol", "").replace("*", "").strip()
        description = row.get("description", "").strip()
        quantity = _numeric_string(row.get("quantity"))
        weight_pct = _numeric_string(row.get("percent_of_account"))
        position_type = row.get("type", "").strip().lower()
        group["balance_total"] = float(group["balance_total"]) + current_value
        is_cash_like = (
            symbol.upper() in {"SPAXX", "FCASH", "FDRXX"}
            or "money market" in description.lower()
            or position_type == "cash"
        )
        if is_cash_like:
            group["cash_total"] = float(group["cash_total"]) + current_value
        holdings = group["holdings"]
        if isinstance(holdings, list):
            holdings.append(
                {
                    "symbol": symbol or None,
                    "description": description or None,
                    "quantity": quantity,
                    "market_value": f"{current_value:.2f}",
                    "weight_pct": weight_pct,
                }
            )

    if not grouped:
        return None

    date_match = re.search(
        r"date downloaded\s+([A-Za-z]{3,9}-[0-9]{1,2}-[0-9]{4})",
        extracted_text or "",
        flags=re.IGNORECASE,
    )
    as_of_date = _parse_natural_date(date_match.group(1) if date_match else None)
    financial_accounts: list[dict[str, object]] = []
    source_types: set[str] = set()
    total_balance = 0.0
    for (_, account_name), group in grouped.items():
        balance_total = round(float(group["balance_total"]), 2)
        cash_total = round(float(group["cash_total"]), 2)
        holdings_value = round(balance_total - cash_total, 2)
        source_type = str(group["source_type"])
        source_types.add(source_type)
        total_balance += balance_total
        financial_accounts.append(
            {
                "asset_group": group["asset_group"],
                "account_type": group["account_type"],
                "institution_name": "Fidelity",
                "account_name": account_name,
                "account_hint": account_name,
                "account_mask": str(group["account_number"]),
                "currency": "USD",
                "balance": f"{balance_total:.2f}",
                "holdings_value": f"{holdings_value:.2f}",
                "cash_balance": f"{cash_total:.2f}",
                "as_of_date": as_of_date,
                "holdings": group["holdings"],
            }
        )

    source_type = "retirement" if source_types == {"retirement"} else "brokerage"
    document_type = "retirement_statement" if source_type == "retirement" else "brokerage_statement"
    account_count = len(financial_accounts)
    structured_data: _StructuredData = {
        "provider_name": "Fidelity",
        "currency": "USD",
        "financial_accounts": financial_accounts,
        "total_amount": f"{total_balance:.2f}",
        "account_count": account_count,
    }
    if as_of_date is not None:
        structured_data["statement_period"] = as_of_date
    if account_count == 1:
        structured_data["account_hint"] = str(financial_accounts[0]["account_name"])
    else:
        structured_data["account_hint"] = f"Fidelity positions export ({account_count} accounts)"
    summary = (
        f"Fidelity positions export covering {account_count} "
        f"{'retirement' if source_type == 'retirement' else 'brokerage'} "
        f"{'account' if account_count == 1 else 'accounts'} totaling ${total_balance:,.2f}."
    )
    return source_type, document_type, 0.95, summary, structured_data


def _classify_statement_csv(
    *,
    filename: str,
    extracted_text: str | None,
    structured_data: _StructuredData,
) -> tuple[str, str, float, str] | None:
    account = _extract_statement_csv_account(filename=filename, extracted_text=extracted_text)
    if account is None:
        return None
    structured_data["account_hint"] = account["account_hint"]
    structured_data["financial_accounts"] = [account]
    structured_data["total_amount"] = account["balance"]
    if account.get("as_of_date") is not None:
        structured_data["statement_period"] = f"As of {account['as_of_date']}"
    return (
        "brokerage",
        "brokerage_statement",
        0.9,
        "Structured account export with dated cash activity and running balance.",
    )


def _classify_by_content(
    *,
    filename: str,
    extracted_text: str | None,
    inferred_source: str,
    inferred_document: str,
    confidence: float,
    summary: str,
    structured_data: _StructuredData,
) -> tuple[str, str, float, str, _StructuredData]:
    """Match document content against known patterns and return updated classification."""
    filename_lower = filename.lower()
    text_lower = (extracted_text or "").lower()

    is_amazon_order = filename_lower == "order history.csv" or (
        "order date" in text_lower
        and "order id" in text_lower
        and "payment instrument type" in text_lower
    )

    if is_amazon_order:
        inferred_source, inferred_document, confidence, summary = _classify_amazon(text_lower, structured_data)
    elif filename_lower.endswith(".csv"):
        fidelity_positions = _extract_fidelity_positions_accounts(
            extracted_text=extracted_text,
        )
        if fidelity_positions is not None:
            (
                inferred_source,
                inferred_document,
                confidence,
                summary,
                positions_structured_data,
            ) = fidelity_positions
            structured_data.update(positions_structured_data)
        else:
            statement_csv = _classify_statement_csv(
                filename=filename,
                extracted_text=extracted_text,
                structured_data=structured_data,
            )
            if statement_csv is not None:
                inferred_source, inferred_document, confidence, summary = statement_csv
    elif "chase.com/amazon" in text_lower or "autopay is on" in text_lower:
        inferred_source, inferred_document, confidence, summary = _classify_chase_amazon(structured_data)
    elif (
        "order details - walmart.com" in text_lower
        or ("walmart.com" in text_lower and "order details" in text_lower)
        or "walmart" in filename_lower
    ):
        inferred_source, inferred_document, confidence, summary = _classify_walmart(structured_data)
    elif "wells fargo everyday checking" in text_lower:
        inferred_source, inferred_document, confidence, summary = _classify_wells_fargo(structured_data)
    elif "529" in text_lower or "college fnd" in text_lower or "college fund" in text_lower:
        inferred_source, inferred_document, confidence, summary = _classify_529(structured_data)
    elif "cash management" in text_lower and (
        "account total balance" in text_lower
        or "cash available to withdraw" in text_lower
        or "recent activity" in text_lower
    ):
        inferred_source, inferred_document, confidence, summary = _classify_cash_management(
            extracted_text, structured_data
        )
    elif "brokerage" in text_lower or "positions" in text_lower or "dividends" in text_lower:
        inferred_source, inferred_document, confidence = "brokerage", "brokerage_statement", 0.8
        summary = "Brokerage statement with investable assets and account activity."
    elif "<invstmtmsgsrsv1>" in text_lower or "<invtranlist>" in text_lower:
        inferred_source, inferred_document, confidence = "brokerage", "brokerage_statement", 0.84
        summary = "Investment account export with machine-readable holdings and activity."
    elif "<creditcardmsgsrsv1>" in text_lower or "<ccstmttrnrs>" in text_lower:
        inferred_source, inferred_document, confidence = "credit_card", "statement", 0.84
        summary = "Credit-card export with machine-readable transaction activity."
    elif "<bankmsgsrsv1>" in text_lower or "<banktranlist>" in text_lower or "<stmttrn>" in text_lower:
        inferred_source, inferred_document, confidence = "bank", "statement", 0.82
        summary = "Bank account export with machine-readable transaction activity."
    elif "ira" in text_lower or "401(k)" in text_lower or "retirement" in text_lower:
        inferred_source, inferred_document, confidence = "retirement", "retirement_statement", 0.8
        summary = "Retirement account statement for long-term planning."
    elif "invoice" in text_lower or "amount due" in text_lower or "bill" in text_lower:
        inferred_source, inferred_document, confidence = "billing", "invoice", 0.78
        summary = "Billing document with payment obligation."

    return inferred_source, inferred_document, confidence, summary, structured_data


def _baseline_review(
    *,
    filename: str,
    source_type: str,
    document_type: str,
    extracted_text: str | None,
) -> dict[str, object]:
    structured_data: _StructuredData = {
        "text_preview": extracted_text[:TEXT_PREVIEW_LENGTH] if extracted_text else None,
    }
    inferred_source = source_type
    inferred_document = document_type
    confidence = BASELINE_REVIEW_CONFIDENCE
    summary = f"Uploaded {document_type.replace('_', ' ')} from {source_type.replace('_', ' ')}."

    inferred_source, inferred_document, confidence, summary, structured_data = _classify_by_content(
        filename=filename,
        extracted_text=extracted_text,
        inferred_source=inferred_source,
        inferred_document=inferred_document,
        confidence=confidence,
        summary=summary,
        structured_data=structured_data,
    )

    statement_period, total_amount = _extract_amounts(extracted_text)
    if statement_period:
        structured_data["statement_period"] = statement_period
    if total_amount:
        structured_data["total_amount"] = total_amount

    return {
        "summary": summary,
        "document_type": inferred_document,
        "source_type": inferred_source,
        "confidence": confidence,
        "structured_data": structured_data,
        "inferred_values": [],
        "questions": _build_questions(
            source_type=inferred_source,
            document_type=inferred_document,
            summary=summary,
            merchant=structured_data.get("merchant"),
            account_hint=structured_data.get("account_hint"),
        ),
    }
