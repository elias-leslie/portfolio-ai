"""DB helpers and section config for household planning tables."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.logging_config import get_logger
from app.models.household_planning import (
    HouseholdDebtObligationInput,
    HouseholdHousingCostInput,
    HouseholdIncomeSourceInput,
    HouseholdInsurancePolicyInput,
    HouseholdPlannedExpenseInput,
    HouseholdPlanningMemberInput,
    HouseholdRetirementCollegeScheduleInput,
    HouseholdRetirementHealthcareScheduleInput,
    HouseholdRetirementIncomeSourceInput,
)
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_planning_rows import (
    row_to_debt_obligation,
    row_to_housing_cost,
    row_to_income_source,
    row_to_insurance_policy,
    row_to_member,
    row_to_planned_expense,
    row_to_retirement_college_schedule,
    row_to_retirement_healthcare_schedule,
    row_to_retirement_income_source,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class _SectionConfig:
    key: str
    table: str
    columns: tuple[str, ...]
    natural_key_fields: tuple[str, ...]
    row_parser: Any
    input_model: Any


_SECTIONS: dict[str, _SectionConfig] = {
    "members": _SectionConfig(
        key="members",
        table="household_members",
        columns=(
            "display_name",
            "role",
            "relationship",
            "birth_year",
            "is_dependent",
            "lives_in_household",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("display_name", "role"),
        row_parser=row_to_member,
        input_model=HouseholdPlanningMemberInput,
    ),
    "income_sources": _SectionConfig(
        key="income_sources",
        table="household_income_sources",
        columns=(
            "label",
            "owner_name",
            "source_type",
            "pay_frequency",
            "employer_or_source",
            "gross_amount",
            "net_amount",
            "monthly_amount",
            "annual_amount",
            "variable_income_notes",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "source_type"),
        row_parser=row_to_income_source,
        input_model=HouseholdIncomeSourceInput,
    ),
    "debt_obligations": _SectionConfig(
        key="debt_obligations",
        table="household_debt_obligations",
        columns=(
            "label",
            "debt_type",
            "lender",
            "balance",
            "monthly_payment",
            "interest_rate",
            "payoff_target_date",
            "secured_by",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "debt_type"),
        row_parser=row_to_debt_obligation,
        input_model=HouseholdDebtObligationInput,
    ),
    "housing_costs": _SectionConfig(
        key="housing_costs",
        table="household_housing_costs",
        columns=(
            "label",
            "housing_type",
            "occupancy_role",
            "monthly_payment",
            "property_tax_monthly",
            "hoa_monthly",
            "insurance_monthly",
            "utilities_monthly",
            "maintenance_monthly",
            "mortgage_balance",
            "interest_rate",
            "property_value",
            "ownership_percent",
            "value_as_of",
            "retirement_treatment",
            "annual_retirement_income",
            "liquidity_year",
            "liquidity_amount",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "occupancy_role"),
        row_parser=row_to_housing_cost,
        input_model=HouseholdHousingCostInput,
    ),
    "insurance_policies": _SectionConfig(
        key="insurance_policies",
        table="household_insurance_policies",
        columns=(
            "label",
            "coverage_type",
            "carrier",
            "premium_monthly",
            "coverage_amount",
            "deductible",
            "employer_sponsored",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "coverage_type"),
        row_parser=row_to_insurance_policy,
        input_model=HouseholdInsurancePolicyInput,
    ),
    "retirement_income_sources": _SectionConfig(
        key="retirement_income_sources",
        table="household_retirement_income_sources",
        columns=(
            "label",
            "source_type",
            "owner_name",
            "start_age",
            "monthly_amount",
            "annual_amount",
            "inflation_adjusted",
            "survivor_benefit",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "source_type"),
        row_parser=row_to_retirement_income_source,
        input_model=HouseholdRetirementIncomeSourceInput,
    ),
    "retirement_healthcare_schedule": _SectionConfig(
        key="retirement_healthcare_schedule",
        table="household_retirement_healthcare_schedule",
        columns=(
            "age",
            "real_amount",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("age",),
        row_parser=row_to_retirement_healthcare_schedule,
        input_model=HouseholdRetirementHealthcareScheduleInput,
    ),
    "retirement_college_schedule": _SectionConfig(
        key="retirement_college_schedule",
        table="household_retirement_college_schedule",
        columns=(
            "calendar_year",
            "real_amount",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("calendar_year",),
        row_parser=row_to_retirement_college_schedule,
        input_model=HouseholdRetirementCollegeScheduleInput,
    ),
    "planned_expenses": _SectionConfig(
        key="planned_expenses",
        table="household_planned_expenses",
        columns=(
            "label",
            "expense_kind",
            "category",
            "target_amount",
            "target_date",
            "monthly_saving_target",
            "priority",
            "notes",
            "confirmation_status",
            "provenance",
            "evidence_note",
            "source_document_id",
        ),
        natural_key_fields=("label", "expense_kind"),
        row_parser=row_to_planned_expense,
        input_model=HouseholdPlannedExpenseInput,
    ),
}


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _natural_key(config: _SectionConfig, payload: dict[str, object]) -> str:
    return "|".join(_normalize_key(str(payload.get(field) or "")) for field in config.natural_key_fields)


def list_section_rows(service: Any, config: _SectionConfig) -> list[Any]:
    with service.storage.connection() as conn:
        rows = conn.execute(
            f"SELECT id, {', '.join(config.columns)}, created_at, updated_at "
            f"FROM {config.table} ORDER BY updated_at DESC, created_at DESC"
        ).fetchall()
    parser_kwargs = {"iso": iso, "to_float": to_float, "iso_or_none": iso_or_none}
    return [
        config.row_parser(row, **{k: v for k, v in parser_kwargs.items() if k in config.row_parser.__code__.co_varnames})
        for row in rows
    ]


def insert_row(*, conn: Any, config: _SectionConfig, row_id: str, payload: dict[str, object], now: str) -> None:
    columns = ", ".join(("id", *config.columns, "created_at", "updated_at"))
    placeholders = ", ".join(["%s"] * (len(config.columns) + 3))
    values = [row_id, *[payload.get(column) for column in config.columns], now, now]
    conn.execute(f"INSERT INTO {config.table} ({columns}) VALUES ({placeholders})", values)


def update_row(*, conn: Any, config: _SectionConfig, row_id: str, payload: dict[str, object], updated_at: str) -> None:
    set_clause = ", ".join(f"{column} = %s" for column in (*config.columns, "updated_at"))
    values = [payload.get(column) for column in config.columns]
    values.extend([updated_at, row_id])
    conn.execute(f"UPDATE {config.table} SET {set_clause} WHERE id = %s", values)


def replace_section_rows(*, conn: Any, config: _SectionConfig, rows: list[dict[str, object]]) -> None:
    existing_ids = {str(row[0]) for row in conn.execute(f"SELECT id FROM {config.table}").fetchall()}
    keep_ids: set[str] = set()
    now = datetime.now(UTC).isoformat()
    for raw_row in rows:
        try:
            item = config.input_model.model_validate(raw_row)
        except ValidationError as exc:
            logger.debug("planning_upsert_validation_failed", table=config.table, error=str(exc))
            continue
        payload = item.model_dump()
        row_id = payload.pop("id") or str(uuid.uuid4())
        keep_ids.add(row_id)
        if row_id in existing_ids:
            update_row(conn=conn, config=config, row_id=row_id, payload=payload, updated_at=now)
        else:
            insert_row(conn=conn, config=config, row_id=row_id, payload=payload, now=now)
    for stale_id in existing_ids - keep_ids:
        conn.execute(f"DELETE FROM {config.table} WHERE id = %s", [stale_id])


def merge_section_rows(
    *,
    conn: Any,
    config: _SectionConfig,
    current_items: list[Any],
    rows: list[dict[str, object]],
) -> None:
    keyed_items = {_natural_key(config, item.model_dump()): item for item in current_items}
    now = datetime.now(UTC).isoformat()
    for raw_row in rows:
        try:
            item = config.input_model.model_validate(raw_row)
        except ValidationError as exc:
            logger.debug("planning_merge_validation_failed", table=config.table, error=str(exc))
            continue
        payload = item.model_dump(exclude_unset=True)
        row_id = payload.pop("id", None)
        if row_id is None:
            existing = keyed_items.get(_natural_key(config, payload))
            row_id = existing.id if existing is not None else None
        if row_id is None:
            insert_row(conn=conn, config=config, row_id=str(uuid.uuid4()), payload=payload, now=now)
        else:
            existing_payload = next(
                (
                    {k: v for k, v in current_item.model_dump().items() if k not in {"id", "created_at", "updated_at"}}
                    for current_item in current_items
                    if current_item.id == row_id
                ),
                {},
            )
            merged_payload = {**existing_payload, **payload}
            update_row(conn=conn, config=config, row_id=row_id, payload=merged_payload, updated_at=now)
