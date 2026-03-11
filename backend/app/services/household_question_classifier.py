"""Question family classification and answer-matching helpers."""

from __future__ import annotations

import re

from app.models.household_finance import HouseholdQuestion

_FAMILY_TOKENS: dict[str, list[str]] = {
    "core_spending": [
        "yes",
        "main household",
        "primary account",
        "regular bills",
        "core household",
        "everyday spending",
        "cash flow",
    ],
    "shopping_channel": [
        "yes",
        "recurring",
        "regular household",
        "grocer",
        "consumable",
        "home goods",
        "weekly",
        "monthly",
    ],
}

_NEGATIVE_TOKENS: dict[str, list[str]] = {
    "core_spending": [
        "no",
        "side account",
        "occasional transfers",
        "occasional transfer",
        "secondary account",
        "not primary",
        "not our main",
    ],
    "shopping_channel": [
        "no",
        "one-off",
        "one off",
        "rarely",
        "occasional",
        "not regular",
    ],
}


def question_family(question_text: str, field_name: str | None) -> str:
    """Classify a question into a known semantic family."""
    normalized = question_text.lower()
    if field_name == "monthly_essential_target" and any(
        phrase in normalized
        for phrase in [
            "primary account",
            "monthly bills",
            "budget tracking",
            "core monthly household spending",
            "core household spending",
            "budget-driving",
        ]
    ):
        return "core_spending"
    if "regular household spending" in normalized or "recurring household shopping channel" in normalized:
        return "shopping_channel"
    if "how often does the household shop" in normalized or "weekly, bi-weekly" in normalized:
        return "merchant_cadence"
    if field_name in {"target_retirement_age", "target_retirement_spend"}:
        return "retirement_target"
    if "what role should this document play" in normalized:
        return "document_role"
    return "unknown"


def question_sort_key(question: HouseholdQuestion) -> tuple[int, str]:
    """Return a sort key for ordering questions by priority then creation time."""
    priority_rank = {"high": 0, "medium": 1, "low": 2}.get(question.priority, 3)
    return (priority_rank, question.created_at)


def clean_source_value(value: object) -> str | None:
    """Normalise a source metadata value to a lowercase stripped string or None."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned or None


_STRING_FIELD_NORMALIZERS: dict[str, dict[str, str]] = {
    "filing_status": {
        "single": "single",
        "married filing jointly": "married_filing_jointly",
        "joint": "married_filing_jointly",
        "married jointly": "married_filing_jointly",
        "married filing separately": "married_filing_separately",
        "head of household": "head_of_household",
        "surviving spouse": "qualifying_surviving_spouse",
    }
}

_INTEGER_FIELDS = {
    "adult_count",
    "dependent_count",
    "target_retirement_age",
    "emergency_fund_target_months",
}

_TEXT_FIELDS = {"filing_status", "state_of_residence"}


def parse_answer_value(field_name: str, answer_text: str) -> str | float | int | None:
    """Extract a numeric value from free-text answer, rounding appropriately."""
    if field_name in _TEXT_FIELDS:
        cleaned = answer_text.strip()
        if not cleaned:
            return None
        alias_map = _STRING_FIELD_NORMALIZERS.get(field_name, {})
        return alias_map.get(cleaned.lower(), cleaned)

    normalized = answer_text.replace(",", "").replace("$", "").strip().lower()
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match is None:
        return None
    number = float(match.group(0))
    if field_name in _INTEGER_FIELDS:
        return round(number)
    return round(number, 2)


def _has_negative_signal(normalized_answer: str, negatives: list[str]) -> bool:
    return any(
        token == normalized_answer
        or normalized_answer.startswith(f"{token} ")
        or normalized_answer.startswith(f"{token},")
        or f" {token} " in normalized_answer
        or normalized_answer.endswith(f" {token}")
        for token in negatives
    )


def answer_covers_family(normalized_answer: str, family: str) -> bool:
    """Return True when the answer signals coverage (positive or negative) for a family."""
    tokens = _FAMILY_TOKENS.get(family, [])
    negatives = _NEGATIVE_TOKENS.get(family, [])
    return _has_negative_signal(normalized_answer, negatives) or any(
        token in normalized_answer for token in tokens
    )


def questions_share_source_context(
    first: HouseholdQuestion,
    second: HouseholdQuestion,
) -> bool:
    """Return True if two questions share a common source document or source metadata."""
    if first.source_document_id is not None and first.source_document_id == second.source_document_id:
        return True

    first_source = first.metadata.get("source_document")
    second_source = second.metadata.get("source_document")
    if not isinstance(first_source, dict) or not isinstance(second_source, dict):
        return False

    for key in ["account_label", "account_hint", "merchant"]:
        first_value = clean_source_value(first_source.get(key))
        second_value = clean_source_value(second_source.get(key))
        if first_value and second_value and first_value == second_value:
            return True
    return False
