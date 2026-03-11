"""Row parsers for household planning tables."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.models.household_planning import (
    HouseholdDebtObligation,
    HouseholdDocumentRequirement,
    HouseholdHousingCost,
    HouseholdIncomeSource,
    HouseholdInsurancePolicy,
    HouseholdPlannedExpense,
    HouseholdPlanningMember,
    HouseholdRetirementIncomeSource,
)


def row_to_member(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
) -> HouseholdPlanningMember:
    return HouseholdPlanningMember(
        id=str(row[0]),
        display_name=str(row[1]),
        role=str(row[2]),
        relationship=str(row[3]) if row[3] is not None else None,
        birth_year=int(row[4]) if row[4] is not None else None,
        is_dependent=bool(row[5]),
        lives_in_household=bool(row[6]),
        notes=str(row[7]) if row[7] is not None else None,
        confirmation_status=str(row[8]),
        provenance=str(row[9]),
        evidence_note=str(row[10]) if row[10] is not None else None,
        source_document_id=str(row[11]) if row[11] is not None else None,
        created_at=iso(row[12]),
        updated_at=iso(row[13]),
    )


def row_to_income_source(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
) -> HouseholdIncomeSource:
    return HouseholdIncomeSource(
        id=str(row[0]),
        label=str(row[1]),
        owner_name=str(row[2]) if row[2] is not None else None,
        source_type=str(row[3]),
        pay_frequency=str(row[4]) if row[4] is not None else None,
        employer_or_source=str(row[5]) if row[5] is not None else None,
        gross_amount=to_float(row[6]),
        net_amount=to_float(row[7]),
        monthly_amount=to_float(row[8]),
        annual_amount=to_float(row[9]),
        variable_income_notes=str(row[10]) if row[10] is not None else None,
        notes=str(row[11]) if row[11] is not None else None,
        confirmation_status=str(row[12]),
        provenance=str(row[13]),
        evidence_note=str(row[14]) if row[14] is not None else None,
        source_document_id=str(row[15]) if row[15] is not None else None,
        created_at=iso(row[16]),
        updated_at=iso(row[17]),
    )


def row_to_debt_obligation(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
    iso_or_none: Callable[[Any], str | None],
) -> HouseholdDebtObligation:
    return HouseholdDebtObligation(
        id=str(row[0]),
        label=str(row[1]),
        debt_type=str(row[2]),
        lender=str(row[3]) if row[3] is not None else None,
        balance=to_float(row[4]),
        monthly_payment=to_float(row[5]),
        interest_rate=to_float(row[6]),
        payoff_target_date=iso_or_none(row[7]),
        secured_by=str(row[8]) if row[8] is not None else None,
        notes=str(row[9]) if row[9] is not None else None,
        confirmation_status=str(row[10]),
        provenance=str(row[11]),
        evidence_note=str(row[12]) if row[12] is not None else None,
        source_document_id=str(row[13]) if row[13] is not None else None,
        created_at=iso(row[14]),
        updated_at=iso(row[15]),
    )


def row_to_housing_cost(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
) -> HouseholdHousingCost:
    return HouseholdHousingCost(
        id=str(row[0]),
        label=str(row[1]),
        housing_type=str(row[2]),
        occupancy_role=str(row[3]),
        monthly_payment=to_float(row[4]),
        property_tax_monthly=to_float(row[5]),
        hoa_monthly=to_float(row[6]),
        insurance_monthly=to_float(row[7]),
        utilities_monthly=to_float(row[8]),
        maintenance_monthly=to_float(row[9]),
        mortgage_balance=to_float(row[10]),
        interest_rate=to_float(row[11]),
        notes=str(row[12]) if row[12] is not None else None,
        confirmation_status=str(row[13]),
        provenance=str(row[14]),
        evidence_note=str(row[15]) if row[15] is not None else None,
        source_document_id=str(row[16]) if row[16] is not None else None,
        created_at=iso(row[17]),
        updated_at=iso(row[18]),
    )


def row_to_insurance_policy(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
) -> HouseholdInsurancePolicy:
    return HouseholdInsurancePolicy(
        id=str(row[0]),
        label=str(row[1]),
        coverage_type=str(row[2]),
        carrier=str(row[3]) if row[3] is not None else None,
        premium_monthly=to_float(row[4]),
        coverage_amount=to_float(row[5]),
        deductible=to_float(row[6]),
        employer_sponsored=bool(row[7]),
        notes=str(row[8]) if row[8] is not None else None,
        confirmation_status=str(row[9]),
        provenance=str(row[10]),
        evidence_note=str(row[11]) if row[11] is not None else None,
        source_document_id=str(row[12]) if row[12] is not None else None,
        created_at=iso(row[13]),
        updated_at=iso(row[14]),
    )


def row_to_retirement_income_source(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
) -> HouseholdRetirementIncomeSource:
    return HouseholdRetirementIncomeSource(
        id=str(row[0]),
        label=str(row[1]),
        source_type=str(row[2]),
        owner_name=str(row[3]) if row[3] is not None else None,
        start_age=int(row[4]) if row[4] is not None else None,
        monthly_amount=to_float(row[5]),
        annual_amount=to_float(row[6]),
        inflation_adjusted=bool(row[7]),
        survivor_benefit=bool(row[8]),
        notes=str(row[9]) if row[9] is not None else None,
        confirmation_status=str(row[10]),
        provenance=str(row[11]),
        evidence_note=str(row[12]) if row[12] is not None else None,
        source_document_id=str(row[13]) if row[13] is not None else None,
        created_at=iso(row[14]),
        updated_at=iso(row[15]),
    )


def row_to_planned_expense(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
    to_float: Callable[[Any], float | None],
    iso_or_none: Callable[[Any], str | None],
) -> HouseholdPlannedExpense:
    return HouseholdPlannedExpense(
        id=str(row[0]),
        label=str(row[1]),
        expense_kind=str(row[2]),
        category=str(row[3]),
        target_amount=to_float(row[4]),
        target_date=iso_or_none(row[5]),
        monthly_saving_target=to_float(row[6]),
        priority=str(row[7]),
        notes=str(row[8]) if row[8] is not None else None,
        confirmation_status=str(row[9]),
        provenance=str(row[10]),
        evidence_note=str(row[11]) if row[11] is not None else None,
        source_document_id=str(row[12]) if row[12] is not None else None,
        created_at=iso(row[13]),
        updated_at=iso(row[14]),
    )


def row_to_document_requirement(
    row: tuple[Any, ...],
    *,
    iso: Callable[[Any], str],
) -> HouseholdDocumentRequirement:
    return HouseholdDocumentRequirement(
        id=str(row[0]),
        requirement_key=str(row[1]),
        document_kind=str(row[2]),
        label=str(row[3]),
        status=str(row[4]),
        priority=str(row[5]),
        related_section=str(row[6]) if row[6] is not None else None,
        related_record_id=str(row[7]) if row[7] is not None else None,
        rationale=str(row[8]) if row[8] is not None else None,
        notes=str(row[9]) if row[9] is not None else None,
        source=str(row[10]),
        satisfied_by_document_id=str(row[11]) if row[11] is not None else None,
        created_at=iso(row[12]),
        updated_at=iso(row[13]),
    )
