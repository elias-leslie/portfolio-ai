"""Row parsers and shared constants for household finance models."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.models.household_finance import (
    HouseholdDocument,
    HouseholdEvidenceAccount,
    HouseholdProfile,
    HouseholdQuestion,
    HouseholdTrackedAccount,
)

FIELD_LABELS = {
    "adult_count": "Adults in household",
    "dependent_count": "Dependents",
    "monthly_net_income_target": "Monthly take-home income",
    "monthly_essential_target": "Essential budget",
    "monthly_discretionary_target": "Discretionary budget",
    "monthly_savings_target": "Monthly savings target",
    "target_retirement_age": "Target retirement age",
    "target_spouse_retirement_age": "Spouse retirement age",
    "target_retirement_spend": "Target monthly retirement spend",
    "retirement_inflation_rate": "Retirement inflation rate",
    "retirement_horizon_years": "Retirement horizon years",
    "primary_social_security_monthly": "Your Social Security monthly estimate",
    "spouse_social_security_monthly": "Spouse Social Security monthly estimate",
    "primary_social_security_annual_earnings": "Your annual earnings for Social Security estimate",
    "spouse_social_security_annual_earnings": "Spouse annual earnings for Social Security estimate",
    "primary_social_security_start_age": "Your Social Security start age",
    "spouse_social_security_start_age": "Spouse Social Security start age",
    "social_security_payable_ratio": "Social Security payable percentage",
    "filing_status": "Tax filing status",
    "state_of_residence": "State of residence",
    "effective_tax_rate": "Effective tax rate",
    "marginal_federal_tax_rate": "Federal marginal tax rate",
    "marginal_state_tax_rate": "State marginal tax rate",
    "emergency_fund_target_months": "Emergency fund target months",
    "emergency_fund_target_amount": "Emergency fund target amount",
}


def _load_json_object(value: Any) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        return json.loads(value)
    return {}


def _load_json_string_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    parsed = value
    if isinstance(value, str) and value:
        parsed = json.loads(value)
    if not isinstance(parsed, list):
        return None
    options = [str(item).strip() for item in parsed if str(item).strip()]
    return options or None


def question_source_document(row: tuple[Any, ...]) -> dict[str, object] | None:
    if len(row) < 20 or row[14] is None:
        return None

    document_metadata = _load_json_object(row[19])
    structured_data = document_metadata.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}

    merchant = structured_data.get("merchant")
    account_hint = structured_data.get("account_hint")

    return {
        "id": str(row[7]) if row[7] is not None else None,
        "filename": str(row[14]),
        "source_type": str(row[15]) if row[15] is not None else None,
        "document_type": str(row[16]) if row[16] is not None else None,
        "account_label": str(row[17]) if row[17] is not None else None,
        "review_summary": str(row[18]) if row[18] is not None else None,
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
        adult_count=to_int(row[2]),
        dependent_count=to_int(row[3]),
        monthly_net_income_target=to_float(row[4]),
        monthly_essential_target=to_float(row[5]),
        monthly_discretionary_target=to_float(row[6]),
        monthly_savings_target=to_float(row[7]),
        target_retirement_age=to_int(row[8]),
        target_spouse_retirement_age=to_int(row[9]),
        target_retirement_spend=to_float(row[10]),
        retirement_inflation_rate=to_float(row[11]),
        retirement_horizon_years=to_int(row[12]),
        primary_social_security_monthly=to_float(row[13]),
        spouse_social_security_monthly=to_float(row[14]),
        primary_social_security_annual_earnings=to_float(row[15]),
        spouse_social_security_annual_earnings=to_float(row[16]),
        primary_social_security_start_age=to_int(row[17]),
        spouse_social_security_start_age=to_int(row[18]),
        social_security_payable_ratio=to_float(row[19]),
        filing_status=str(row[20]) if row[20] is not None else None,
        state_of_residence=str(row[21]) if row[21] is not None else None,
        effective_tax_rate=to_float(row[22]),
        marginal_federal_tax_rate=to_float(row[23]),
        marginal_state_tax_rate=to_float(row[24]),
        emergency_fund_target_months=to_float(row[25]),
        emergency_fund_target_amount=to_float(row[26]),
        withdrawal_strategy=str(row[27]) if row[27] is not None else None,
        withdrawal_initial_rate=to_float(row[28]),
        withdrawal_decline_mode=str(row[29]) if row[29] is not None else None,
        discretionary_decline_rate=to_float(row[30]),
        phase_slow_go_age=to_int(row[31]),
        phase_no_go_age=to_int(row[32]),
        phase_go_go_pct=to_float(row[33]),
        phase_slow_go_pct=to_float(row[34]),
        phase_no_go_pct=to_float(row[35]),
        bridge_mode=str(row[36]) if row[36] is not None else None,
        bridge_manual_amount=to_float(row[37]),
        bridge_real_return=to_float(row[38]),
        retirement_essential_floor_override=to_float(row[39]),
        retirement_discretionary_override=to_float(row[40]),
        notes=str(row[41]) if row[41] is not None else None,
        created_at=iso(row[42]),
        updated_at=iso(row[43]),
        bridge_growth=str(row[44]) if len(row) > 44 and row[44] is not None else None,
        aca_tier=str(row[45]) if len(row) > 45 and row[45] is not None else None,
        aca_premium_age21_override=to_float(row[46]) if len(row) > 46 else None,
        aca_oop_monthly=to_float(row[47]) if len(row) > 47 else None,
        medicare_monthly_per_person=to_float(row[48]) if len(row) > 48 else None,
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
        question_format=str(row[9]) if row[9] is not None else "short_text",
        options=_load_json_string_list(row[10]),
        direction=str(row[11]) if row[11] is not None else "jenny_to_user",
        created_at=iso(row[12]),
        answered_at=iso_or_none(row[13]),
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


def row_to_evidence_account(
    row: tuple[Any, ...],
    *,
    to_float: Callable[[Any], float | None],
    iso_or_none: Callable[[Any], str | None],
) -> HouseholdEvidenceAccount:
    metadata = _load_json_object(row[15])
    return HouseholdEvidenceAccount(
        id=str(row[0]),
        document_id=str(row[1]),
        household_account_id=str(row[2]) if row[2] is not None else None,
        source_type=str(row[3]),
        asset_group=str(row[4]),
        account_type=str(row[5]),
        institution_name=str(row[6]) if row[6] is not None else None,
        account_name=str(row[7]) if row[7] is not None else None,
        account_mask=str(row[8]) if row[8] is not None else None,
        owner_name=str(row[9]) if row[9] is not None else None,
        currency=str(row[10]) if row[10] is not None else None,
        balance=to_float(row[11]),
        holdings_value=to_float(row[12]),
        cash_balance=to_float(row[13]),
        as_of_date=iso_or_none(row[14]),
        confidence=to_float(row[16]),
        metadata=metadata,
    )


def row_to_tracked_account(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
) -> HouseholdTrackedAccount:
    return HouseholdTrackedAccount(
        id=str(row[0]),
        household_account_id=str(row[1]) if row[1] is not None else None,
        label=str(row[2]),
        asset_group=str(row[3]),
        account_type=str(row[4]),
        source_type=str(row[5]),
        match_key=str(row[6]) if row[6] is not None else None,
        institution_name=str(row[7]) if row[7] is not None else None,
        owner_name=str(row[8]) if row[8] is not None else None,
        account_mask=str(row[9]) if row[9] is not None else None,
        notes=str(row[10]) if row[10] is not None else None,
        created_at=iso(row[11]),
        updated_at=iso(row[12]),
    )
