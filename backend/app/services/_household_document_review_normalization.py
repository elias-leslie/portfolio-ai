"""Household document review merge and normalization helpers."""

from __future__ import annotations

from typing import Any

from app.services._household_document_pipeline_utils import looks_like_transaction_activity

_GENERIC_SUMMARIES = frozenset(
    {
        "uploaded other from other.",
        "uploaded statement from credit card.",
        "uploaded statement from bank.",
        "uploaded brokerage statement from brokerage.",
        "uploaded retirement statement from retirement.",
    }
)


def normalize_review_checks(*, reviewed: dict[str, Any], extracted_text: str | None) -> dict[str, Any]:
    raw_review_checks = reviewed.get("review_checks")
    review_checks = dict(raw_review_checks) if isinstance(raw_review_checks, dict) else {}
    structured_data = reviewed.get("structured_data")
    financial_accounts = []
    if isinstance(structured_data, dict) and isinstance(structured_data.get("financial_accounts"), list):
        financial_accounts = [
            account
            for account in structured_data["financial_accounts"]
            if isinstance(account, dict)
        ]
    if review_checks.get("expected_account_count") in {None, ""}:
        review_checks["expected_account_count"] = len(financial_accounts)
    if review_checks.get("expects_transaction_activity") is None:
        has_position_snapshot = any(
            isinstance(account.get("holdings"), list) or account.get("position_snapshot") is True
            for account in financial_accounts
        )
        review_source_type = str(reviewed.get("source_type") or "")
        review_document_type = str(reviewed.get("document_type") or "")
        review_checks["expects_transaction_activity"] = (
            False
            if has_position_snapshot
            and review_source_type in {"brokerage", "retirement"}
            and review_document_type in {"brokerage_statement", "retirement_statement"}
            else looks_like_transaction_activity(
                source_type=review_source_type,
                document_type=review_document_type,
                extracted_text=extracted_text,
            )
        )
    if review_checks.get("ambiguity_remaining") is None:
        review_checks["ambiguity_remaining"] = bool(reviewed.get("questions"))
    if review_checks.get("ambiguity_remaining") and not review_checks.get("ambiguity_reason") and reviewed.get("questions"):
        review_checks["ambiguity_reason"] = "Additional user input still required."
    return review_checks


def merge_llm_result(reviewed: dict[str, Any], baseline: dict[str, Any], extracted_text: str | None) -> dict[str, Any]:
    structured_data = reviewed.setdefault("structured_data", {})
    if isinstance(structured_data, dict):
        structured_data.update({k: v for k, v in baseline["structured_data"].items() if k not in structured_data})
    reviewed.setdefault("inferred_values", [])
    reviewed.setdefault("planning_items", [])
    if not isinstance(reviewed.get("questions"), list):
        reviewed["questions"] = []
    if not reviewed.get("summary"):
        reviewed["summary"] = baseline["summary"]
    if reviewed.get("confidence") is None:
        reviewed["confidence"] = baseline["confidence"]
    reviewed["source_type"] = str(reviewed.get("source_type") or baseline["source_type"])
    reviewed["document_type"] = str(reviewed.get("document_type") or baseline["document_type"])
    reviewed["review_checks"] = normalize_review_checks(reviewed=reviewed, extracted_text=extracted_text)
    reviewed["extracted_text"] = extracted_text
    return reviewed


def _generic_summary_subject(reviewed: dict[str, Any]) -> str:
    structured_data = reviewed.get("structured_data")
    structured = structured_data if isinstance(structured_data, dict) else {}
    return str(
        structured.get("account_hint")
        or structured.get("provider_name")
        or structured.get("merchant")
        or "Household account"
    ).strip()


def normalize_summary(
    *,
    reviewed: dict[str, Any],
    fallback_summary: str,
    source_type: str,
    document_type: str,
    extracted_text: str | None,
) -> str:
    current_summary = str(reviewed.get("summary") or "").strip()
    summary = current_summary or fallback_summary or "Reviewed household finance document."
    generic = not current_summary or current_summary.lower() in _GENERIC_SUMMARIES
    if not generic:
        return summary

    subject = _generic_summary_subject(reviewed)
    if looks_like_transaction_activity(source_type=source_type, document_type=document_type, extracted_text=extracted_text):
        activity_summaries = {
            "credit_card": f"{subject} activity export with machine-readable card transactions.",
            "bank": f"{subject} activity export with machine-readable cash transactions.",
            "brokerage": f"{subject} export with machine-readable account activity.",
        }
        return activity_summaries.get(source_type, summary)

    statement_summaries = {
        ("credit_card", "statement"): f"{subject} statement with household card activity.",
        ("bank", "statement"): f"{subject} statement with household cash activity.",
        ("brokerage", "brokerage_statement"): f"{subject} snapshot with investable assets and account activity.",
        ("retirement", "retirement_statement"): f"{subject} retirement snapshot for long-term planning.",
    }
    return statement_summaries.get((source_type, document_type), summary)
