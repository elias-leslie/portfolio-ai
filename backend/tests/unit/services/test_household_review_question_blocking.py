"""Informational review questions must not hold a document out of the ledger."""

from __future__ import annotations

from typing import Any

from app.services._household_document_review_normalization import normalize_review_checks
from app.services.household_document_review_contracts import HouseholdDocumentReviewPayload
from app.services.household_question_classifier import blocking_review_questions

_CHANNEL = {"question": "Is Walmart a recurring household shopping channel?", "question_format": "boolean"}
_ACCOUNT = {
    "question": "Is Checking 1234 your primary account for monthly bills, deposits, and budget tracking?",
    "field_name": "monthly_essential_target",
}


def _receipt(questions: list[dict[str, Any]], checks: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"source_type": "receipt", "document_type": "receipt", "questions": questions, "review_checks": checks or {}}


def test_shopping_channel_question_is_informational() -> None:
    assert blocking_review_questions([_CHANNEL]) == []
    assert blocking_review_questions([_CHANNEL, _ACCOUNT]) == [_ACCOUNT]


def test_receipt_with_only_a_channel_question_is_not_ambiguous() -> None:
    checks = normalize_review_checks(reviewed=_receipt([_CHANNEL]), extracted_text=None)
    assert checks["ambiguity_remaining"] is False


def test_ambiguity_that_only_restates_the_channel_question_is_cleared() -> None:
    """Exactly the stored state that re-asked an answered question on every review."""
    reviewed = _receipt(
        [_CHANNEL],
        {"ambiguity_remaining": True, "ambiguity_reason": _CHANNEL["question"]},
    )
    checks = normalize_review_checks(reviewed=reviewed, extracted_text=None)
    assert checks["ambiguity_remaining"] is False
    assert "ambiguity_reason" not in checks


def test_a_real_ambiguity_reason_still_blocks() -> None:
    reviewed = _receipt(
        [_CHANNEL],
        {"ambiguity_remaining": True, "ambiguity_reason": "Two cards could have paid this order."},
    )
    checks = normalize_review_checks(reviewed=reviewed, extracted_text=None)
    assert checks["ambiguity_remaining"] is True


def test_blocking_questions_still_fail_closed() -> None:
    checks = normalize_review_checks(reviewed=_receipt([_CHANNEL, _ACCOUNT]), extracted_text=None)
    assert checks["ambiguity_remaining"] is True
    assert _ACCOUNT["question"] in checks["ambiguity_reason"]


def test_contract_does_not_derive_ambiguity_from_informational_questions() -> None:
    result = HouseholdDocumentReviewPayload.model_validate(_receipt([_CHANNEL]))
    assert result.review_checks.ambiguity_remaining is not True
    blocked = HouseholdDocumentReviewPayload.model_validate(_receipt([_ACCOUNT]))
    assert blocked.review_checks.ambiguity_remaining is True
