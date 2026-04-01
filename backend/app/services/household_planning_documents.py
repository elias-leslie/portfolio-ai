"""Document requirement sync and persistence for household planning."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.household_planning import HouseholdDocumentRequirementUpdate
from app.services._household_finance_utils import iso
from app.services.household_planning_rows import row_to_document_requirement

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

_DEBT_DOCUMENT_KINDS: dict[str, str] = {
    "mortgage": "mortgage_statement",
    "heloc": "heloc_statement",
    "student_loan": "student_loan_statement",
    "auto_loan": "auto_loan_statement",
}


def matching_document_id(document_kind: str, documents: list[Any]) -> str | None:
    allowed_types = _DOCUMENT_MATCHERS.get(document_kind, set())
    for document in documents:
        if document.document_type in allowed_types:
            return document.id
    return None


def generate_requirement_seeds(*, profile: Any, sections: dict[str, list[Any]]) -> list[dict[str, object]]:
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
        seeds.append({
            "requirement_key": "core-social-security",
            "document_kind": "social_security_statement",
            "label": "Social Security statement",
            "priority": "medium",
            "related_section": "retirement_income",
            "rationale": "Social Security estimates materially affect retirement readiness projections.",
        })

    for debt in sections["debt_obligations"]:
        document_kind = _DEBT_DOCUMENT_KINDS.get(debt.debt_type)
        if document_kind is None:
            continue
        seeds.append({
            "requirement_key": f"debt-{debt.id}",
            "document_kind": document_kind,
            "label": f"{debt.label} statement",
            "priority": "high",
            "related_section": "debt",
            "related_record_id": debt.id,
            "rationale": f"{debt.label} statement keeps balances, rates, and payment assumptions current.",
        })

    for policy in sections["insurance_policies"]:
        seeds.append({
            "requirement_key": f"insurance-{policy.id}",
            "document_kind": "insurance_policy",
            "label": f"{policy.label} declarations / policy summary",
            "priority": "medium",
            "related_section": "insurance",
            "related_record_id": policy.id,
            "rationale": f"{policy.label} documents confirm premium, deductible, and coverage amounts.",
        })

    for income in sections["retirement_income_sources"]:
        document_kind = "pension_statement" if income.source_type == "pension" else "social_security_statement"
        seeds.append({
            "requirement_key": f"retirement-income-{income.id}",
            "document_kind": document_kind,
            "label": f"{income.label} statement",
            "priority": "medium",
            "related_section": "retirement_income",
            "related_record_id": income.id,
            "rationale": f"{income.label} supports retirement-income timing and amount assumptions.",
        })

    for expense in sections["planned_expenses"]:
        seeds.append({
            "requirement_key": f"planned-expense-{expense.id}",
            "document_kind": "major_expense_support",
            "label": f"Support for {expense.label}",
            "priority": "medium" if expense.expense_kind == "goal_bucket" else "high",
            "related_section": "planned_expenses",
            "related_record_id": expense.id,
            "rationale": "Quotes, invoices, or estimate documents make one-time expense planning concrete.",
        })

    return seeds


def list_document_requirements(service: Any) -> list[Any]:
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
    return [row_to_document_requirement(row, iso=iso) for row in rows]


def update_document_requirement_statuses(*, conn: Any, updates: list[dict[str, object]]) -> None:
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


def sync_document_requirements(
    service: Any,
    *,
    profile: Any,
    sections: dict[str, list[Any]],
) -> None:
    desired = generate_requirement_seeds(profile=profile, sections=sections)
    documents = service.list_documents(limit=200).items
    matched_docs = {
        seed["requirement_key"]: matching_document_id(seed["document_kind"], documents)
        for seed in desired
    }

    with service.storage.connection() as conn:
        existing_rows = conn.execute(
            "SELECT id, requirement_key, source, status FROM household_document_requirements"
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
                conn.execute("DELETE FROM household_document_requirements WHERE id = %s", [str(row[0])])
        conn.commit()
