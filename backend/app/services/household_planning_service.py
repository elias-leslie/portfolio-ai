"""Household planning snapshot persistence and document-requirement sync."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.logging_config import get_logger
from app.models.household_planning import (
    HouseholdPlanningSectionStatus,
    HouseholdPlanningSnapshot,
    HouseholdPlanningSummary,
    HouseholdPlanningUpdate,
)
from app.services.household_planning_db import (
    _SECTIONS,
    list_section_rows,
    merge_section_rows,
    replace_section_rows,
)
from app.services.household_planning_documents import (
    list_document_requirements,
    sync_document_requirements,
    update_document_requirement_statuses,
)

logger = get_logger(__name__)

_SECTION_ALIAS_MAP: dict[str, dict[str, str]] = {
    "debt_obligations": {"source_type": "debt_type"},
    "housing_costs": {"source_type": "housing_type"},
    "insurance_policies": {"source_type": "coverage_type"},
}


def _section_status(
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


def _build_summary(
    *,
    profile: Any,
    sections: dict[str, list[Any]],
    requirements: list[Any],
) -> HouseholdPlanningSummary:
    status_rows = [
        _section_status(
            section="household",
            label="Household",
            ready=bool(sections["members"]) or profile.adult_count is not None or profile.dependent_count is not None,
            item_count=len(sections["members"]),
            ready_detail="Household structure is captured for budget sizing.",
            missing_detail="Add adults, dependents, or household counts so Jenny sizes the plan correctly.",
        ),
        _section_status(
            section="income",
            label="Income",
            ready=bool(sections["income_sources"]) or profile.monthly_net_income_target is not None,
            item_count=len(sections["income_sources"]),
            ready_detail="Income sources and pay structure are on record.",
            missing_detail="Add salary, bonus, freelance, or benefit income so budget completeness is defensible.",
        ),
        _section_status(
            section="debt",
            label="Debt",
            ready=bool(sections["debt_obligations"]),
            item_count=len(sections["debt_obligations"]),
            ready_detail="Debt payments and balances are tracked.",
            missing_detail="Add mortgage, HELOC, student, auto, or other debt obligations.",
        ),
        _section_status(
            section="housing",
            label="Housing",
            ready=bool(sections["housing_costs"]),
            item_count=len(sections["housing_costs"]),
            ready_detail="Housing costs are visible for baseline planning.",
            missing_detail="Add rent or ownership costs so Jenny can anchor essential spending.",
        ),
        _section_status(
            section="insurance",
            label="Insurance",
            ready=bool(sections["insurance_policies"]),
            item_count=len(sections["insurance_policies"]),
            ready_detail="Insurance coverage and premiums are tracked.",
            missing_detail="Add health, life, auto, home, or disability coverage details.",
        ),
        _section_status(
            section="taxes",
            label="Taxes",
            ready=profile.filing_status is not None or profile.effective_tax_rate is not None,
            item_count=int(profile.filing_status is not None) + int(profile.effective_tax_rate is not None),
            ready_detail="Tax filing assumptions are available for planning scenarios.",
            missing_detail="Set filing status or tax-rate assumptions so net planning numbers are more realistic.",
        ),
        _section_status(
            section="retirement_income",
            label="Retirement Income",
            ready=bool(sections["retirement_income_sources"]),
            item_count=len(sections["retirement_income_sources"]),
            ready_detail="Retirement income sources are captured.",
            missing_detail="Add Social Security, pension, annuity, or bridge-income expectations.",
        ),
        _section_status(
            section="planned_expenses",
            label="Major Expenses",
            ready=any(item.expense_kind == "major_expense" for item in sections["planned_expenses"]),
            item_count=sum(1 for item in sections["planned_expenses"] if item.expense_kind == "major_expense"),
            ready_detail="Expected one-time expenses are planned explicitly.",
            missing_detail="Capture large known expenses so Jenny can reserve for them early.",
        ),
        _section_status(
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


class HouseholdPlanningService:
    """Load and persist typed household planning sections."""

    def get_snapshot(self, service: Any) -> HouseholdPlanningSnapshot:
        profile = service.get_profile()
        sections = self._load_sections(service)
        sync_document_requirements(service, profile=profile, sections=sections)
        requirements = list_document_requirements(service)
        summary = _build_summary(profile=profile, sections=sections, requirements=requirements)
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
                replace_section_rows(conn=conn, config=config, rows=items)
            requirements = update_data.get("document_requirements")
            if requirements is not None:
                update_document_requirement_statuses(conn=conn, updates=requirements)
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
                logger.debug("planning_merge_unknown_section", section=section)
                continue
            payload = {key: value for key, value in raw_item.items() if key != "section" and value is not None}
            if "rationale" in payload and "evidence_note" not in payload:
                payload["evidence_note"] = payload.pop("rationale")
            for alias_key, canonical_key in _SECTION_ALIAS_MAP.get(section, {}).items():
                if alias_key in payload and canonical_key not in payload:
                    payload[canonical_key] = payload.pop(alias_key)
            payload.setdefault("provenance", provenance)
            payload.setdefault("confirmation_status", "inferred")
            if source_document_id and "source_document_id" not in payload:
                payload["source_document_id"] = source_document_id
            grouped[section].append(payload)

        if not grouped:
            return

        # Section readers own short-lived connections. Load them before the
        # write transaction so callers holding a document-level advisory-lock
        # connection never require three simultaneous pool checkouts.
        existing = self._load_sections(service)
        with service.storage.connection() as conn:
            for section, raw_items in grouped.items():
                config = _SECTIONS[section]
                merge_section_rows(
                    conn=conn,
                    config=config,
                    current_items=existing[section],
                    rows=raw_items,
                )
            conn.commit()
        self.get_snapshot(service)

    def sync_document_requirements(self, service: Any, *, profile: Any, sections: dict[str, list[Any]]) -> None:
        sync_document_requirements(service, profile=profile, sections=sections)

    def _load_sections(self, service: Any) -> dict[str, list[Any]]:
        return {key: list_section_rows(service, config) for key, config in _SECTIONS.items()}
