"""Deterministic baseline document review and question generation."""

from __future__ import annotations

import re
from typing import Any

# Text preview length for structured_data summaries
TEXT_PREVIEW_LENGTH = 500
# Default confidence for baseline (non-LLM) document reviews
BASELINE_REVIEW_CONFIDENCE = 0.45


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


def _build_questions(
    *,
    source_type: str,
    document_type: str,
    summary: str,
    merchant: Any,
    account_hint: Any,
) -> list[dict[str, Any]]:
    questions = [
        {
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
            "recommendation": "Confirm whether Jenny should use this for budgeting, cash-flow tracking, savings analysis, or only as a reference.",
            "rationale": "Jenny could not confidently infer the full financial meaning from the file alone.",
        }
    ]
    if source_type == "receipt" and isinstance(merchant, str) and merchant:
        return [
            {
                "field_name": None,
                "question": f"Should Jenny treat {merchant} orders like this as part of regular household spending?",
                "priority": "medium",
                "question_format": "boolean",
                "options": ["Yes", "No"],
                "recommendation": f"Answer 'yes' if {merchant} is a recurring household shopping channel for groceries, consumables, or home goods.",
                "rationale": "This helps Jenny separate recurring household shopping from one-off discretionary purchases.",
            }
        ]
    if source_type == "bank" and isinstance(account_hint, str) and account_hint:
        return [
            {
                "field_name": "monthly_essential_target",
                "question": f"Is {account_hint} your primary account for monthly bills, deposits, and budget tracking?",
                "priority": "high",
                "question_format": "boolean",
                "options": ["Yes", "No"],
                "recommendation": "Answer 'yes' if most paycheck deposits, bill payments, and core household cash flow pass through this account.",
                "rationale": "Primary checking accounts anchor the household cash-flow model.",
            }
        ]
    if source_type == "credit_card" and isinstance(account_hint, str) and account_hint:
        return [
            {
                "field_name": "monthly_essential_target",
                "question": f"Should Jenny treat {account_hint} as part of core household spending?",
                "priority": "high",
                "question_format": "boolean",
                "options": ["Yes", "No"],
                "recommendation": "Answer 'yes' if this card is used for regular groceries, household shopping, subscriptions, or recurring family spending.",
                "rationale": "This determines whether Jenny should treat the card as budget-driving spend data.",
            }
        ]
    if source_type == "other" or document_type == "other":
        questions.append(
            {
                "field_name": None,
                "question": "What kind of document is this and which account or merchant is it tied to?",
                "priority": "high",
                "question_format": "long_text",
                "recommendation": "Name the merchant or institution and say whether this is a receipt, order confirmation, or statement.",
                "rationale": "Jenny could not confidently identify the institution, account, or document class from the file alone.",
            }
        )
    if source_type in {"bank", "credit_card"}:
        questions.append(
            {
                "field_name": "monthly_essential_target",
                "question": "Is this account part of your core monthly household spending?",
                "priority": "high",
                "question_format": "boolean",
                "options": ["Yes", "No"],
                "recommendation": "Confirm if this account covers regular household bills, groceries, or everyday spending.",
                "rationale": "This determines whether Jenny should treat the spend as budget-driving data.",
            }
        )
    if source_type in {"retirement", "brokerage"}:
        questions.append(
            {
                "field_name": "target_retirement_spend",
                "question": "Should this account count toward retirement readiness tracking?",
                "priority": "medium",
                "question_format": "boolean",
                "options": ["Yes", "No"],
                "recommendation": "Confirm if this is a retirement or long-term investment account that should shape future-income planning.",
                "rationale": "Jenny needs to know whether the account is part of the retirement plan or general savings.",
            }
        )
    if "keep refining" not in summary.lower():
        questions[0]["rationale"] = f"{questions[0]['rationale']} Current best read: {summary}"
    return questions


def _baseline_review(
    *,
    filename: str,
    source_type: str,
    document_type: str,
    extracted_text: str | None,
) -> dict[str, Any]:
    structured_data: dict[str, Any] = {
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


def _classify_by_content(
    *,
    filename: str,
    extracted_text: str | None,
    inferred_source: str,
    inferred_document: str,
    confidence: float,
    summary: str,
    structured_data: dict[str, Any],
) -> tuple[str, str, float, str, dict[str, Any]]:
    """Match document content against known patterns and return updated classification."""
    filename_lower = filename.lower()
    text_lower = (extracted_text or "").lower()

    if filename_lower == "order history.csv" or (
        "order date" in text_lower
        and "order id" in text_lower
        and "payment instrument type" in text_lower
    ):
        inferred_source = "receipt"
        inferred_document = "receipt"
        confidence = 0.9
        structured_data["merchant"] = "Amazon"
        if "total amount" in text_lower or "unit price" in text_lower or "shipping charge" in text_lower:
            summary = "Amazon order history export with order pricing, shipping, and item-level purchase detail."
        else:
            summary = "Amazon order history export covering household purchases over time."
    elif "walmart.com" in text_lower or "order details - walmart.com" in text_lower or "walmart" in filename_lower:
        inferred_source = "receipt"
        inferred_document = "receipt"
        confidence = 0.84
        structured_data["merchant"] = "Walmart"
        summary = "Walmart order details with household shopping line items."
    elif "wells fargo everyday checking" in text_lower:
        inferred_source = "bank"
        inferred_document = "statement"
        confidence = 0.88
        structured_data["account_hint"] = "Wells Fargo Everyday Checking"
        summary = "Wells Fargo Everyday Checking statement showing household cash activity."
    elif "chase.com/amazon" in text_lower or "autopay is on" in text_lower:
        inferred_source = "credit_card"
        inferred_document = "statement"
        confidence = 0.86
        structured_data["account_hint"] = "Chase Amazon card"
        summary = "Chase Amazon credit-card statement with monthly household spending."
    elif "529" in text_lower or "college fnd" in text_lower or "college fund" in text_lower:
        inferred_source = "brokerage"
        inferred_document = "brokerage_statement"
        confidence = 0.9
        structured_data["account_hint"] = "529 college savings account"
        summary = "529 college savings account snapshot with beneficiary balances."
    elif "brokerage" in text_lower or "positions" in text_lower or "dividends" in text_lower:
        inferred_source = "brokerage"
        inferred_document = "brokerage_statement"
        confidence = 0.8
        summary = "Brokerage statement with investable assets and account activity."
    elif "ira" in text_lower or "401(k)" in text_lower or "retirement" in text_lower:
        inferred_source = "retirement"
        inferred_document = "retirement_statement"
        confidence = 0.8
        summary = "Retirement account statement for long-term planning."
    elif "invoice" in text_lower or "amount due" in text_lower or "bill" in text_lower:
        inferred_source = "billing"
        inferred_document = "invoice"
        confidence = 0.78
        summary = "Billing document with payment obligation."

    return inferred_source, inferred_document, confidence, summary, structured_data
