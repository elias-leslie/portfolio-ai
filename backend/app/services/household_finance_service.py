"""Household finance dashboard and intake service."""

from __future__ import annotations

from typing import Any

from app.models.household_finance import (
    HouseholdFinanceDashboard,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdResolvedValue,
    HouseholdTransactionCategoryUpdate,
)
from app.models.household_planning import HouseholdPlanningSnapshot, HouseholdPlanningUpdate
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services._household_dashboard_queries import fetch_inferred_value_rows
from app.services._household_finance_document_methods import _HFDocumentMethods
from app.services._household_finance_intake_methods import _HFIntakeMethods
from app.services.household_dashboard_composer import HouseholdDashboardComposer
from app.services.household_document_pipeline import HouseholdDocumentPipeline
from app.services.household_document_review import HouseholdDocumentReviewService
from app.services.household_finance_rows import FIELD_LABELS
from app.services.household_planning_service import HouseholdPlanningService
from app.services.household_profile_service import HouseholdProfileService
from app.services.household_question_command_service import HouseholdQuestionCommandService
from app.services.household_question_reconciler import HouseholdQuestionReconciler
from app.services.household_review_agent_service import HouseholdReviewAgentService
from app.services.household_transaction_rule_service import HouseholdTransactionRuleService
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import get_storage


class HouseholdFinanceService(_HFDocumentMethods, _HFIntakeMethods):
    """Build household-finance views and persist intake metadata."""

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.review_agent_service = HouseholdReviewAgentService()
        self.review_service = HouseholdDocumentReviewService(
            agent_service=self.review_agent_service
        )
        self.transaction_service = HouseholdTransactionService()
        self.dashboard_composer = HouseholdDashboardComposer()
        self.document_pipeline = HouseholdDocumentPipeline()
        self.question_reconciler = HouseholdQuestionReconciler()
        self.profile_service = HouseholdProfileService()
        self.planning_service = HouseholdPlanningService()
        self.question_command_service = HouseholdQuestionCommandService()
        self.transaction_rule_service = HouseholdTransactionRuleService()

    def get_dashboard(self) -> HouseholdFinanceDashboard:
        return self.dashboard_composer.build_dashboard(self)

    def get_profile(self) -> HouseholdProfile:
        return self.profile_service.get_profile(self)

    def update_profile(self, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        return self.profile_service.update_profile(self, payload)

    def get_planning_snapshot(self) -> HouseholdPlanningSnapshot:
        return self.planning_service.get_snapshot(self)

    def update_planning_snapshot(self, payload: HouseholdPlanningUpdate) -> HouseholdPlanningSnapshot:
        return self.planning_service.update_snapshot(self, payload)

    def merge_planning_items(self, *, items: list[dict[str, object]], provenance: str, source_document_id: str | None = None) -> None:
        self.planning_service.merge_planning_items(self, items=items, provenance=provenance, source_document_id=source_document_id)

    def update_transaction_category(self, transaction_id: str, payload: HouseholdTransactionCategoryUpdate) -> bool:
        return self.transaction_rule_service.update_transaction_category(self, transaction_id, payload)

    def get_resolved_values(self, *, profile: HouseholdProfile, questions: list[Any]) -> list[HouseholdResolvedValue]:
        inferred_map = fetch_inferred_value_rows(self.storage)
        questions_by_field = {q.field_name: q for q in questions if q.field_name}
        resolved: list[HouseholdResolvedValue] = []
        for field_name, label in FIELD_LABELS.items():
            manual_value = getattr(profile, field_name)
            inferred = inferred_map.get(field_name)
            if manual_value is not None:
                resolved.append(HouseholdResolvedValue(
                    field_name=field_name, label=label, value=str(manual_value),
                    confidence=1.0, status="confirmed", source="manual",
                    rationale="You confirmed or overrode this value directly.",
                ))
            elif inferred is not None:
                conf = inferred["confidence"]
                resolved.append(HouseholdResolvedValue(
                    field_name=field_name, label=label, value=str(inferred["value"]),
                    confidence=float(conf) if conf is not None else None, status=str(inferred["status"]),
                    source="jenny_inference",
                    rationale=str(inferred["rationale"]) if inferred["rationale"] is not None else None,
                    question=questions_by_field[field_name].question if field_name in questions_by_field else None,
                ))
            else:
                question = questions_by_field.get(field_name)
                resolved.append(HouseholdResolvedValue(
                    field_name=field_name, label=label, value=None, confidence=None,
                    status="missing", source="unknown", rationale=None,
                    question=question.question if question is not None else None,
                ))
        return resolved
