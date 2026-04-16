"""Household finance dashboard and intake service."""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from app.models.household_finance import (
    HouseholdEvidenceAccount,
    HouseholdFinanceDashboard,
    HouseholdLedger,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdResolvedValue,
    HouseholdSpendingView,
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
    HouseholdTransactionCategoryUpdate,
)
from app.models.household_planning import HouseholdPlanningSnapshot, HouseholdPlanningUpdate
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services._household_dashboard_queries import fetch_inferred_value_rows
from app.services._household_finance_document_methods import _HFDocumentMethods
from app.services._household_finance_intake_methods import _HFIntakeMethods
from app.services.household_account_registry_service import HouseholdAccountRegistryService
from app.services.household_dashboard_composer import HouseholdDashboardComposer
from app.services.household_document_pipeline import HouseholdDocumentPipeline
from app.services.household_document_review import HouseholdDocumentReviewService
from app.services.household_evidence_service import HouseholdEvidenceService
from app.services.household_finance_rows import FIELD_LABELS
from app.services.household_ledger_service import HouseholdLedgerService
from app.services.household_planning_service import HouseholdPlanningService
from app.services.household_product_enrichment_service import HouseholdProductEnrichmentService
from app.services.household_profile_service import HouseholdProfileService
from app.services.household_question_command_service import HouseholdQuestionCommandService
from app.services.household_question_reconciler import HouseholdQuestionReconciler
from app.services.household_review_agent_service import HouseholdReviewAgentService
from app.services.household_tracked_account_service import HouseholdTrackedAccountService
from app.services.household_transaction_audit_service import HouseholdTransactionAuditService
from app.services.household_transaction_rule_service import HouseholdTransactionRuleService
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import get_storage

_DASHBOARD_REGISTRY_SYNC_INTERVAL_SECONDS = 30.0


class HouseholdFinanceService(_HFDocumentMethods, _HFIntakeMethods):
    """Build household-finance views and persist intake metadata."""

    _dashboard_registry_sync_lock = Lock()
    _last_dashboard_registry_sync_monotonic = 0.0

    def __init__(self) -> None:
        self.storage = get_storage()
        self.portfolio_mgr = PortfolioManager(self.storage)
        self.price_fetcher = PriceDataFetcher(self.storage)
        self.review_agent_service = HouseholdReviewAgentService()
        self.review_service = HouseholdDocumentReviewService(
            agent_service=self.review_agent_service
        )
        self.transaction_service = HouseholdTransactionService()
        self.evidence_service = HouseholdEvidenceService()
        self.account_registry_service = HouseholdAccountRegistryService()
        self.product_enrichment_service = HouseholdProductEnrichmentService()
        self.dashboard_composer = HouseholdDashboardComposer()
        self.ledger_service = HouseholdLedgerService()
        self.document_pipeline = HouseholdDocumentPipeline()
        self.question_reconciler = HouseholdQuestionReconciler()
        self.profile_service = HouseholdProfileService()
        self.planning_service = HouseholdPlanningService()
        self.question_command_service = HouseholdQuestionCommandService()
        self.transaction_rule_service = HouseholdTransactionRuleService()
        self.transaction_audit_service = HouseholdTransactionAuditService()
        self.tracked_account_service = HouseholdTrackedAccountService()

    def get_dashboard(self) -> HouseholdFinanceDashboard:
        self._ensure_dashboard_registry_sync(limit=1000)
        return self.dashboard_composer.build_dashboard(self)

    def _ensure_dashboard_registry_sync(self, *, limit: int, force: bool = False) -> None:
        now = monotonic()
        last_sync = type(self)._last_dashboard_registry_sync_monotonic
        if not force and now - last_sync < _DASHBOARD_REGISTRY_SYNC_INTERVAL_SECONDS:
            return

        with type(self)._dashboard_registry_sync_lock:
            now = monotonic()
            last_sync = type(self)._last_dashboard_registry_sync_monotonic
            if not force and now - last_sync < _DASHBOARD_REGISTRY_SYNC_INTERVAL_SECONDS:
                return
            self.account_registry_service.sync_registry(self, limit=limit)
            type(self)._last_dashboard_registry_sync_monotonic = monotonic()

    def get_profile(self) -> HouseholdProfile:
        return self.profile_service.get_profile(self)

    def get_ledger(
        self,
        *,
        window: str = "all",
        kind: str = "all",
        limit: int = 10000,
    ) -> HouseholdLedger:
        return self.ledger_service.get_ledger(
            self,
            window=window,
            kind=kind,
            limit=limit,
        )

    def get_spending(self, *, window: str = "1m") -> HouseholdSpendingView:
        return self.transaction_service.build_spending_view(window=window)

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

    def list_evidence_accounts(
        self,
        limit: int = 20,
        *,
        dedupe: bool = True,
    ) -> list[HouseholdEvidenceAccount]:
        return self.evidence_service.list_accounts(self, limit=limit, dedupe=dedupe)

    def list_tracked_accounts(self, limit: int = 100) -> list[HouseholdTrackedAccount]:
        return self.tracked_account_service.list_accounts(self, limit=limit)

    def create_tracked_account(
        self,
        payload: HouseholdTrackedAccountInput,
    ) -> HouseholdTrackedAccount:
        return self.tracked_account_service.create_account(self, payload)

    def update_tracked_account(
        self,
        account_id: str,
        payload: HouseholdTrackedAccountInput,
    ) -> HouseholdTrackedAccount | None:
        return self.tracked_account_service.update_account(self, account_id, payload)

    def delete_tracked_account(self, account_id: str) -> bool:
        return self.tracked_account_service.delete_account(self, account_id)

    def sync_linked_tracked_accounts(self, *, limit: int = 500) -> int:
        return int(self.account_registry_service.sync_registry(self, limit=limit).get("tracked_linked", 0))

    def _upload_root(self) -> Path:
        return Path(__file__).resolve().parents[2] / "data" / "household_uploads"

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
