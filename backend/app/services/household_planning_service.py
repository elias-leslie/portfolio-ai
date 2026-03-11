"""Household planning snapshot persistence and document-requirement sync."""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.models.household_planning import (
    HouseholdDebtObligationInput,
    HouseholdDocumentRequirementUpdate,
    HouseholdHousingCostInput,
    HouseholdIncomeSourceInput,
    HouseholdInsurancePolicyInput,
    HouseholdPlannedExpenseInput,
    HouseholdPlanningMemberInput,
    HouseholdPlanningSectionStatus,
    HouseholdPlanningSnapshot,
    HouseholdPlanningSummary,
    HouseholdPlanningUpdate,
    HouseholdRetirementIncomeSourceInput,
)
from app.services.household_planning_rows import (
    row_to_debt_obligation,
    row_to_document_requirement,
    row_to_housing_cost,
    row_to_income_source,
    row_to_insurance_policy,
    row_to_member,
    row_to_planned_expense,
    row_to_retirement_income_source,
)

_DOCUMENT_MATCHERS: dict[str, set[str]] = {
    "pay_stub": {"pay_stub"},
    "w2_1099": {"w2_1099"},
    "tax_return": {"tax_return", "w2_1099"},
    "mortgage_statement": {"mortgage_statement"},
    "heloc_statement": {"heloc_statement"},
    "student_loan_statement": {"student_loan_statement"},
    "auto_loan_statement": {"auto_loan_statement"},
    "insurance_policy": {"insurance_policy", "insurance_declarations"},
    "social_security_statement": {"social_security_statement"},
    "pension_statement": {"pension_statement"},
    "benefits_summary": {"benefits_summary"},
    "major_expense_support": {"major_expense_support", "invoice", "receipt"},
}


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


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


class HouseholdPlanningService:
    """Load and persist typed household planning sections."""

    def get_snapshot(self, service: Any) -> HouseholdPlanningSnapshot:
        profile = service.get_profile()
        sections = self._load_sections(service)
        self.sync_document_requirements(service, profile=profile, sections=sections)
        requirements = self._list_document_requirements(service)
        summary = self._build_summary(profile=profile, sections=sections, requirements=requirements)
        return HouseholdPlanningSnapshot(summary=summary, document_requirements=requirements, **sections)

    def update_snapshot(self, service: Any, payload: HouseholdPlanningUpdate) -> HouseholdPlanningSnapshot:
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return self.get_snapshot(service)

        with service.storage.connection() as conn:
            for section_key, config in _SECTIONS.items():
                items = update_data.get(section_key)
                if items is None:
                    continue
                self._replace_section_rows(conn=conn, config=config, rows=items)
            requirements = update_data.get("document_requirements")
            if requirements is not None:
                self._update_document_requirement_statuses(conn=conn, updates=requirements)
            conn.commit()
        return self.get_snapshot(service)

    def merge_planning_items(
        self,
        service: Any,
        *,
        items: list[dict[str, object]],
        provenance: str,
        source_document_id: str | None = None,
    ) -> None:
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for raw_item in items:
            section = str(raw_item.get("section") or "").strip()
            config = _SECTIONS.get(section)
            if config is None:
                continue
            payload = {key: value for key, value in raw_item.items() if key != "section" and value is not None}
            if "rationale" in payload and "evidence_note" not in payload:
                payload["evidence_note"] = payload.pop("rationale")
            if section == "debt_obligations" and "source_type" in payload and "debt_type" not in payload:
                payload["debt_type"] = payload.pop("source_type")
            if section == "housing_costs" and "source_type" in payload and "housing_type" not in payload:
                payload["housing_type"] = payload.pop("source_type")
            if section == "insurance_policies" and "source_type" in payload and "coverage_type" not in payload:
                payload["coverage_type"] = payload.pop("source_type")
            payload.setdefault("provenance", provenance)
            payload.setdefault("confirmation_status", "inferred")
            if source_document_id and "source_document_id" not in payload:
                payload["source_document_id"] = source_document_id
            grouped[section].append(payload)

        if not grouped:
            return

        with service.storage.connection() as conn:
            existing = self._load_sections(service)
            for section, raw_items in grouped.items():
                config = _SECTIONS[section]
                current_items = existing[section]
                self._merge_section_rows(
                    conn=conn,
                    config=config,
                    current_items=current_items,
                    rows=raw_items,
                )
            conn.commit()
        self.get_snapshot(service)

    def sync_document_requirements(
        self,
        service: Any,
        *,
        profile: Any,
        sections: dict[str, list[Any]],
    ) -> None:
        desired = self._generate_requirement_seeds(profile=profile, sections=sections)
        documents = service.list_documents(limit=200).items
        matched_docs = {
            seed["requirement_key"]: self._matching_document_id(seed["document_kind"], documents)
            for seed in desired
        }

        with service.storage.connection() as conn:
            existing_rows = conn.execute(
                """
                SELECT id, requirement_key, source, status
                FROM household_document_requirements
                """
            ).fetchall()
            existing_by_key = {
                str(row[1]): {"id": str(row[0]), "source": str(row[2]), "status": str(row[3])}
                for row in existing_rows
            }
            desired_keys = {seed["requirement_key"] for seed in desired}
            now = datetime.now(UTC).isoformat()

            for seed in desired:
                requirement_id = existing_by_key.get(seed["requirement_key"], {}).get("id") or str(uuid.uuid4())
                matched_document_id = matched_docs.get(seed["requirement_key"])
                existing_status = existing_by_key.get(seed["requirement_key"], {}).get("status")
                status = "received" if matched_document_id else "missing"
                if existing_status in {"waived", "not_applicable"} and matched_document_id is None:
                    status = existing_status
                values = [
                    requirement_id,
                    seed["requirement_key"],
                    seed["document_kind"],
                    seed["label"],
                    status,
                    seed["priority"],
                    seed.get("related_section"),
                    seed.get("related_record_id"),
                    seed.get("rationale"),
                    seed.get("notes"),
                    "system",
                    matched_document_id,
                    now,
                    now,
                ]
                conn.execute(
                    """
                    INSERT INTO household_document_requirements (
                        id, requirement_key, document_kind, label, status, priority,
                        related_section, related_record_id, rationale, notes, source,
                        satisfied_by_document_id, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (requirement_key) DO UPDATE SET
                        document_kind = EXCLUDED.document_kind,
                        label = EXCLUDED.label,
                        status = EXCLUDED.status,
                        priority = EXCLUDED.priority,
                        related_section = EXCLUDED.related_section,
                        related_record_id = EXCLUDED.related_record_id,
                        rationale = EXCLUDED.rationale,
                        source = EXCLUDED.source,
                        satisfied_by_document_id = EXCLUDED.satisfied_by_document_id,
                        updated_at = EXCLUDED.updated_at
                    """,
                    values,
                )

            for row in existing_rows:
                requirement_key = str(row[1])
                source = str(row[2])
                if source == "system" and requirement_key not in desired_keys:
                    conn.execute(
                        "DELETE FROM household_document_requirements WHERE id = %s",
                        [str(row[0])],
                    )
            conn.commit()

    def _load_sections(self, service: Any) -> dict[str, list[Any]]:
        return {
            "members": self._list_rows(service, _SECTIONS["members"]),
            "income_sources": self._list_rows(service, _SECTIONS["income_sources"]),
            "debt_obligations": self._list_rows(service, _SECTIONS["debt_obligations"]),
            "housing_costs": self._list_rows(service, _SECTIONS["housing_costs"]),
            "insurance_policies": self._list_rows(service, _SECTIONS["insurance_policies"]),
            "retirement_income_sources": self._list_rows(service, _SECTIONS["retirement_income_sources"]),
            "planned_expenses": self._list_rows(service, _SECTIONS["planned_expenses"]),
        }

    def _list_rows(self, service: Any, config: _SectionConfig) -> list[Any]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                f"SELECT id, {', '.join(config.columns)}, created_at, updated_at "
                f"FROM {config.table} ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        parser_kwargs = {"iso": service._iso, "to_float": service._to_float, "iso_or_none": service._iso_or_none}
        return [config.row_parser(row, **{k: v for k, v in parser_kwargs.items() if k in config.row_parser.__code__.co_varnames}) for row in rows]

    def _replace_section_rows(
        self,
        *,
        conn: Any,
        config: _SectionConfig,
        rows: list[dict[str, object]],
    ) -> None:
        existing_ids = {
            str(row[0])
            for row in conn.execute(f"SELECT id FROM {config.table}").fetchall()
        }
        keep_ids: set[str] = set()
        now = datetime.now(UTC).isoformat()
        for raw_row in rows:
            try:
                item = config.input_model.model_validate(raw_row)
            except ValidationError:
                continue
            payload = item.model_dump()
            row_id = payload.pop("id") or str(uuid.uuid4())
            keep_ids.add(row_id)
            if row_id in existing_ids:
                self._update_row(conn=conn, config=config, row_id=row_id, payload=payload, updated_at=now)
            else:
                self._insert_row(conn=conn, config=config, row_id=row_id, payload=payload, now=now)
        for stale_id in existing_ids - keep_ids:
            conn.execute(f"DELETE FROM {config.table} WHERE id = %s", [stale_id])

    def _merge_section_rows(
        self,
        *,
        conn: Any,
        config: _SectionConfig,
        current_items: list[Any],
        rows: list[dict[str, object]],
    ) -> None:
        keyed_items = {
            self._natural_key(config, item.model_dump()): item
            for item in current_items
        }
        now = datetime.now(UTC).isoformat()
        for raw_row in rows:
            try:
                item = config.input_model.model_validate(raw_row)
            except ValidationError:
                continue
            payload = item.model_dump(exclude_unset=True)
            row_id = payload.pop("id", None)
            if row_id is None:
                existing = keyed_items.get(self._natural_key(config, payload))
                row_id = existing.id if existing is not None else None
            if row_id is None:
                self._insert_row(conn=conn, config=config, row_id=str(uuid.uuid4()), payload=payload, now=now)
            else:
                existing_payload = next(
                    (
                        {
                            key: value
                            for key, value in current_item.model_dump().items()
                            if key not in {"id", "created_at", "updated_at"}
                        }
                        for current_item in current_items
                        if current_item.id == row_id
                    ),
                    {},
                )
                merged_payload = {**existing_payload, **payload}
                self._update_row(conn=conn, config=config, row_id=row_id, payload=merged_payload, updated_at=now)

    def _insert_row(self, *, conn: Any, config: _SectionConfig, row_id: str, payload: dict[str, object], now: str) -> None:
        columns = ", ".join(("id", *config.columns, "created_at", "updated_at"))
        placeholders = ", ".join(["%s"] * (len(config.columns) + 3))
        values = [row_id, *[payload.get(column) for column in config.columns], now, now]
        conn.execute(
            f"INSERT INTO {config.table} ({columns}) VALUES ({placeholders})",
            values,
        )

    def _update_row(self, *, conn: Any, config: _SectionConfig, row_id: str, payload: dict[str, object], updated_at: str) -> None:
        set_clause = ", ".join(f"{column} = %s" for column in (*config.columns, "updated_at"))
        values = [payload.get(column) for column in config.columns]
        values.extend([updated_at, row_id])
        conn.execute(
            f"UPDATE {config.table} SET {set_clause} WHERE id = %s",
            values,
        )

    def _natural_key(self, config: _SectionConfig, payload: dict[str, object]) -> str:
        return "|".join(_normalize_key(str(payload.get(field) or "")) for field in config.natural_key_fields)

    def _update_document_requirement_statuses(self, *, conn: Any, updates: list[dict[str, object]]) -> None:
        now = datetime.now(UTC).isoformat()
        for raw_update in updates:
            update = HouseholdDocumentRequirementUpdate.model_validate(raw_update)
            assignments: list[str] = ["updated_at = %s"]
            values: list[object] = [now]
            if update.status is not None:
                assignments.append("status = %s")
                values.append(update.status)
            if update.notes is not None:
                assignments.append("notes = %s")
                values.append(update.notes)
            values.append(update.id)
            conn.execute(
                f"UPDATE household_document_requirements SET {', '.join(assignments)} WHERE id = %s",
                values,
            )

    def _list_document_requirements(self, service: Any) -> list[Any]:
        with service.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    id, requirement_key, document_kind, label, status, priority,
                    related_section, related_record_id, rationale, notes, source,
                    satisfied_by_document_id, created_at, updated_at
                FROM household_document_requirements
                ORDER BY
                    CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                    label ASC
                """
            ).fetchall()
        return [row_to_document_requirement(row, iso=service._iso) for row in rows]

    def _build_summary(
        self,
        *,
        profile: Any,
        sections: dict[str, list[Any]],
        requirements: list[Any],
    ) -> HouseholdPlanningSummary:
        status_rows = [
            self._section_status(
                section="household",
                label="Household",
                ready=bool(sections["members"]) or profile.adult_count is not None or profile.dependent_count is not None,
                item_count=len(sections["members"]),
                ready_detail="Household structure is captured for budget sizing.",
                missing_detail="Add adults, dependents, or household counts so Jenny sizes the plan correctly.",
            ),
            self._section_status(
                section="income",
                label="Income",
                ready=bool(sections["income_sources"]) or profile.monthly_net_income_target is not None,
                item_count=len(sections["income_sources"]),
                ready_detail="Income sources and pay structure are on record.",
                missing_detail="Add salary, bonus, freelance, or benefit income so budget completeness is defensible.",
            ),
            self._section_status(
                section="debt",
                label="Debt",
                ready=bool(sections["debt_obligations"]),
                item_count=len(sections["debt_obligations"]),
                ready_detail="Debt payments and balances are tracked.",
                missing_detail="Add mortgage, HELOC, student, auto, or other debt obligations.",
            ),
            self._section_status(
                section="housing",
                label="Housing",
                ready=bool(sections["housing_costs"]),
                item_count=len(sections["housing_costs"]),
                ready_detail="Housing costs are visible for baseline planning.",
                missing_detail="Add rent or ownership costs so Jenny can anchor essential spending.",
            ),
            self._section_status(
                section="insurance",
                label="Insurance",
                ready=bool(sections["insurance_policies"]),
                item_count=len(sections["insurance_policies"]),
                ready_detail="Insurance coverage and premiums are tracked.",
                missing_detail="Add health, life, auto, home, or disability coverage details.",
            ),
            self._section_status(
                section="taxes",
                label="Taxes",
                ready=profile.filing_status is not None or profile.effective_tax_rate is not None,
                item_count=int(profile.filing_status is not None) + int(profile.effective_tax_rate is not None),
                ready_detail="Tax filing assumptions are available for planning scenarios.",
                missing_detail="Set filing status or tax-rate assumptions so net planning numbers are more realistic.",
            ),
            self._section_status(
                section="retirement_income",
                label="Retirement Income",
                ready=bool(sections["retirement_income_sources"]),
                item_count=len(sections["retirement_income_sources"]),
                ready_detail="Retirement income sources are captured.",
                missing_detail="Add Social Security, pension, annuity, or bridge-income expectations.",
            ),
            self._section_status(
                section="planned_expenses",
                label="Major Expenses",
                ready=any(item.expense_kind == "major_expense" for item in sections["planned_expenses"]),
                item_count=sum(1 for item in sections["planned_expenses"] if item.expense_kind == "major_expense"),
                ready_detail="Expected one-time expenses are planned explicitly.",
                missing_detail="Capture large known expenses so Jenny can reserve for them early.",
            ),
            self._section_status(
                section="goal_buckets",
                label="Goal Buckets",
                ready=any(item.expense_kind == "goal_bucket" for item in sections["planned_expenses"]),
                item_count=sum(1 for item in sections["planned_expenses"] if item.expense_kind == "goal_bucket"),
                ready_detail="Future goal buckets and sinking funds are tracked.",
                missing_detail="Add sinking-fund style goals for irregular future spending.",
            ),
        ]
        ready_sections = sum(1 for row in status_rows if row.status == "ready")
        total_sections = len(status_rows)
        missing_documents = [item for item in requirements if item.status == "missing"]
        high_priority_documents = [item for item in missing_documents if item.priority in {"critical", "high"}]
        score = round((ready_sections / total_sections) * 100) if total_sections else 0
        return HouseholdPlanningSummary(
            completion_score=score,
            ready_sections=ready_sections,
            total_sections=total_sections,
            missing_document_count=len(missing_documents),
            high_priority_document_count=len(high_priority_documents),
            sections=status_rows,
        )

    def _section_status(
        self,
        *,
        section: str,
        label: str,
        ready: bool,
        item_count: int,
        ready_detail: str,
        missing_detail: str,
    ) -> HouseholdPlanningSectionStatus:
        return HouseholdPlanningSectionStatus(
            section=section,
            label=label,
            status="ready" if ready else "missing",
            item_count=item_count,
            detail=ready_detail if ready else missing_detail,
        )

    def _generate_requirement_seeds(
        self,
        *,
        profile: Any,
        sections: dict[str, list[Any]],
    ) -> list[dict[str, object]]:
        seeds: list[dict[str, object]] = [
            {
                "requirement_key": "core-pay-stub",
                "document_kind": "pay_stub",
                "label": "Recent pay stub",
                "priority": "high",
                "related_section": "income",
                "rationale": "Pay stubs anchor take-home pay, deductions, and benefits assumptions.",
            },
            {
                "requirement_key": "core-tax-return",
                "document_kind": "tax_return",
                "label": "Most recent tax return or W-2 / 1099",
                "priority": "high",
                "related_section": "taxes",
                "rationale": "Tax documents support filing assumptions and validate net planning inputs.",
            },
            {
                "requirement_key": "core-benefits-summary",
                "document_kind": "benefits_summary",
                "label": "Benefits summary",
                "priority": "medium",
                "related_section": "insurance",
                "rationale": "Benefits summaries clarify payroll deductions, employer coverage, and retirement benefits.",
            },
        ]

        if profile.target_retirement_age is not None or profile.target_retirement_spend is not None:
            seeds.append(
                {
                    "requirement_key": "core-social-security",
                    "document_kind": "social_security_statement",
                    "label": "Social Security statement",
                    "priority": "medium",
                    "related_section": "retirement_income",
                    "rationale": "Social Security estimates materially affect retirement readiness projections.",
                }
            )

        for debt in sections["debt_obligations"]:
            document_kind = {
                "mortgage": "mortgage_statement",
                "heloc": "heloc_statement",
                "student_loan": "student_loan_statement",
                "auto_loan": "auto_loan_statement",
            }.get(debt.debt_type)
            if document_kind is None:
                continue
            seeds.append(
                {
                    "requirement_key": f"debt-{debt.id}",
                    "document_kind": document_kind,
                    "label": f"{debt.label} statement",
                    "priority": "high",
                    "related_section": "debt",
                    "related_record_id": debt.id,
                    "rationale": f"{debt.label} statement keeps balances, rates, and payment assumptions current.",
                }
            )

        for policy in sections["insurance_policies"]:
            seeds.append(
                {
                    "requirement_key": f"insurance-{policy.id}",
                    "document_kind": "insurance_policy",
                    "label": f"{policy.label} declarations / policy summary",
                    "priority": "medium",
                    "related_section": "insurance",
                    "related_record_id": policy.id,
                    "rationale": f"{policy.label} documents confirm premium, deductible, and coverage amounts.",
                }
            )

        for income in sections["retirement_income_sources"]:
            document_kind = "pension_statement" if income.source_type == "pension" else "social_security_statement"
            seeds.append(
                {
                    "requirement_key": f"retirement-income-{income.id}",
                    "document_kind": document_kind,
                    "label": f"{income.label} statement",
                    "priority": "medium",
                    "related_section": "retirement_income",
                    "related_record_id": income.id,
                    "rationale": f"{income.label} supports retirement-income timing and amount assumptions.",
                }
            )

        for expense in sections["planned_expenses"]:
            seeds.append(
                {
                    "requirement_key": f"planned-expense-{expense.id}",
                    "document_kind": "major_expense_support",
                    "label": f"Support for {expense.label}",
                    "priority": "medium" if expense.expense_kind == "goal_bucket" else "high",
                    "related_section": "planned_expenses",
                    "related_record_id": expense.id,
                    "rationale": "Quotes, invoices, or estimate documents make one-time expense planning concrete.",
                }
            )

        return seeds

    def _matching_document_id(self, document_kind: str, documents: list[Any]) -> str | None:
        allowed_types = _DOCUMENT_MATCHERS.get(document_kind, set())
        for document in documents:
            if document.document_type in allowed_types:
                return document.id
        return None
