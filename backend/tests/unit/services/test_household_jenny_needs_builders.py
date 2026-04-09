from __future__ import annotations

from types import SimpleNamespace

from app.models.household_finance import HouseholdProfile
from app.models.household_planning import (
    HouseholdDocumentRequirement,
    HouseholdPlanningSectionStatus,
    empty_household_planning_snapshot,
)
from app.services._household_jenny_needs_builders import (
    _jenny_account_question_needs,
    _jenny_confirmation_needs,
    _jenny_freshness_needs,
    _jenny_statement_needs,
)
from app.services._money_workspace_routes import (
    MONEY_EVIDENCE_ROUTE,
    MONEY_PLANNING_ROUTE,
)


def _profile() -> HouseholdProfile:
    return HouseholdProfile(
        id="profile-1",
        household_name="Household",
        created_at="2026-03-12T00:00:00+00:00",
        updated_at="2026-03-12T00:00:00+00:00",
    )


def test_statement_and_freshness_needs_link_to_evidence_utility() -> None:
    statement_need = _jenny_statement_needs(coverage_months=0, days_since_latest=None)[0]
    freshness_need = _jenny_freshness_needs(
        documents=[SimpleNamespace(id="doc-1")],
        days_since_latest=61,
    )[0]

    assert statement_need.action_href == MONEY_EVIDENCE_ROUTE
    assert statement_need.title == "Upload financial evidence"
    assert freshness_need.action_href == MONEY_EVIDENCE_ROUTE
    assert freshness_need.title == "Add newer evidence"


def test_confirmation_needs_route_planning_and_document_gaps_to_specific_sections() -> None:
    planning = empty_household_planning_snapshot()
    planning.summary.sections = [
        HouseholdPlanningSectionStatus(
            section="household",
            label="Household",
            status="missing",
            item_count=0,
            detail="Add adults, dependents, or household counts so Jenny sizes the plan correctly.",
        )
    ]
    planning.document_requirements = [
        HouseholdDocumentRequirement(
            id="req-1",
            requirement_key="tax_return",
            document_kind="tax_return",
            label="Most recent tax return or W-2 / 1099",
            status="missing",
            priority="high",
            rationale="Tax documents support filing assumptions and validate net planning inputs.",
            created_at="2026-03-12T00:00:00+00:00",
            updated_at="2026-03-12T00:00:00+00:00",
        )
    ]

    needs = _jenny_confirmation_needs({}, planning, _profile())

    planning_need = next(need for need in needs if need.id == "need_planning_household")
    document_need = next(need for need in needs if need.id == "need_document_req-1")

    assert planning_need.action_href == MONEY_PLANNING_ROUTE
    assert document_need.action_href == MONEY_EVIDENCE_ROUTE


def test_detected_account_upload_needs_link_to_evidence_utility() -> None:
    needs = _jenny_account_question_needs(
        detected_accounts=[
            {
                "institution": "Chase",
                "partial_account": "1234",
                "key": "chase-1234",
            }
        ],
        questions=[],
    )

    assert needs[0].action_href == MONEY_EVIDENCE_ROUTE
    assert needs[0].title == "Add evidence for Chase ...1234"
