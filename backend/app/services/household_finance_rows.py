"""Row parsers for household finance models."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.models.household_finance import HouseholdDocument, HouseholdProfile, HouseholdQuestion


def _load_json_object(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        return json.loads(value)
    return {}


def question_source_document(row: tuple[Any, ...]) -> dict[str, object] | None:
    if len(row) < 17 or row[11] is None:
        return None

    document_metadata = _load_json_object(row[16])
    structured_data = document_metadata.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}

    merchant = structured_data.get("merchant")
    account_hint = structured_data.get("account_hint")

    return {
        "id": str(row[7]) if row[7] is not None else None,
        "filename": str(row[11]),
        "source_type": str(row[12]) if row[12] is not None else None,
        "document_type": str(row[13]) if row[13] is not None else None,
        "account_label": str(row[14]) if row[14] is not None else None,
        "review_summary": str(row[15]) if row[15] is not None else None,
        "merchant": str(merchant) if isinstance(merchant, str) and merchant else None,
        "account_hint": str(account_hint) if isinstance(account_hint, str) and account_hint else None,
    }


def question_recommendation(
    *,
    field_name: str | None,
    metadata: dict[str, object],
    source_document: dict[str, object] | None,
) -> str | None:
    recommendation = (
        "Give Jenny the shortest clarification needed so she can classify the document and continue automatically."
    )
    explicit = metadata.get("recommendation")
    if isinstance(explicit, str) and explicit.strip():
        recommendation = explicit.strip()
    elif field_name == "monthly_essential_target":
        recommendation = (
            "Answer 'yes' if this account is used for regular household bills, groceries, gas, or everyday spending."
        )
    elif field_name == "target_retirement_spend":
        recommendation = (
            "Answer 'yes' if this account should shape retirement readiness and future spending plans."
        )
    elif source_document is not None:
        merchant = source_document.get("merchant")
        account_label = source_document.get("account_label")
        account_hint = source_document.get("account_hint")
        filename = source_document.get("filename")

        if isinstance(merchant, str) and merchant:
            recommendation = (
                f"Confirm that this is a {merchant} purchase or order and say whether it belongs in your regular household budget."
            )
        elif isinstance(account_label, str) and account_label:
            recommendation = (
                f"Confirm what '{account_label}' is used for and whether Jenny should treat it as part of your main household plan."
            )
        elif isinstance(account_hint, str) and account_hint:
            recommendation = (
                f"Confirm whether '{account_hint}' is the right account or institution for this document."
            )
        elif isinstance(filename, str) and filename:
            recommendation = (
                f"Identify the merchant, institution, or account behind '{filename}' so Jenny can classify it correctly."
            )

    return recommendation


def row_to_profile(
    row: tuple[Any, ...],
    *,
    to_float: Callable[[Any], float | None],
    to_int: Callable[[Any], int | None],
    iso: Callable[[Any], str],
) -> HouseholdProfile:
    return HouseholdProfile(
        id=str(row[0]),
        household_name=str(row[1]),
        monthly_net_income_target=to_float(row[2]),
        monthly_essential_target=to_float(row[3]),
        monthly_discretionary_target=to_float(row[4]),
        monthly_savings_target=to_float(row[5]),
        target_retirement_age=to_int(row[6]),
        target_retirement_spend=to_float(row[7]),
        notes=str(row[8]) if row[8] is not None else None,
        created_at=iso(row[9]),
        updated_at=iso(row[10]),
    )


def row_to_question(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    iso_or_none: Callable[[Any], str | None],
) -> HouseholdQuestion:
    metadata = _load_json_object(row[8])
    source_document = question_source_document(row)
    if source_document is not None:
        metadata = {
            **metadata,
            "source_document": source_document,
        }

    field_name = str(row[1]) if row[1] is not None else None
    return HouseholdQuestion(
        id=str(row[0]),
        field_name=field_name,
        status=str(row[2]),
        priority=str(row[3]),
        question=str(row[4]),
        rationale=str(row[5]) if row[5] is not None else None,
        recommendation=question_recommendation(
            field_name=field_name,
            metadata=metadata,
            source_document=source_document,
        ),
        answer_text=str(row[6]) if row[6] is not None else None,
        source_document_id=str(row[7]) if row[7] is not None else None,
        metadata=metadata,
        created_at=iso(row[9]),
        answered_at=iso_or_none(row[10]),
    )


def row_to_document(
    row: tuple[Any, ...],
    *,
    to_float: Callable[[Any], float | None],
    iso: Callable[[Any], str],
    iso_or_none: Callable[[Any], str | None],
) -> HouseholdDocument:
    metadata = _load_json_object(row[16])
    return HouseholdDocument(
        id=str(row[0]),
        filename=str(row[1]),
        source_type=str(row[2]),
        document_type=str(row[3]),
        status=str(row[4]),
        account_label=str(row[5]) if row[5] is not None else None,
        file_size_bytes=int(row[6]),
        content_type=str(row[7]) if row[7] is not None else None,
        classification_confidence=to_float(row[8]),
        review_status=str(row[9]) if row[9] is not None else None,
        review_summary=str(row[10]) if row[10] is not None else None,
        review_confidence=to_float(row[11]),
        statement_start=iso_or_none(row[12]),
        statement_end=iso_or_none(row[13]),
        uploaded_at=iso(row[14]),
        parsed_at=iso_or_none(row[15]),
        metadata=metadata,
    )
