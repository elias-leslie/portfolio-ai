"""Household finance dashboard and intake service."""

from __future__ import annotations

import json
import math
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from app.config import settings
from app.models.household_finance import (
    HouseholdBudgetVerdict,
    HouseholdConfirmedFact,
    HouseholdEvidenceAccount,
    HouseholdFinanceDashboard,
    HouseholdLedger,
    HouseholdNetWorthTrend,
    HouseholdProfile,
    HouseholdProfileUpdate,
    HouseholdResolvedValue,
    HouseholdSpendingCategory,
    HouseholdSpendingView,
    HouseholdSpendOverrideUpdate,
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
    HouseholdTransactionCategoryUpdate,
    HouseholdTransactionOwnerUpdate,
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
from app.services.household_net_worth_trend_service import build_net_worth_trend
from app.services.household_planning_service import HouseholdPlanningService
from app.services.household_portfolio_position_sync_service import (
    HouseholdPortfolioPositionSyncService,
)
from app.services.household_portfolio_transaction_sync_service import (
    HouseholdPortfolioTransactionSyncService,
)
from app.services.household_product_enrichment_service import HouseholdProductEnrichmentService
from app.services.household_profile_service import HouseholdProfileService
from app.services.household_property_valuation_service import HouseholdPropertyValuationService
from app.services.household_purchase_item_service import HouseholdPurchaseItemService
from app.services.household_question_command_service import HouseholdQuestionCommandService
from app.services.household_question_reconciler import HouseholdQuestionReconciler
from app.services.household_review_agent_service import HouseholdReviewAgentService
from app.services.household_tracked_account_service import HouseholdTrackedAccountService
from app.services.household_transaction_audit_service import HouseholdTransactionAuditService
from app.services.household_transaction_rule_service import HouseholdTransactionRuleService
from app.services.household_transaction_service import HouseholdTransactionService
from app.storage import get_storage

_DASHBOARD_REGISTRY_SYNC_INTERVAL_SECONDS = 30.0
_CATEGORY_BUDGET_PREFIX = "category_budget:"


def _round_budget(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(math.floor((value / 25.0) + 0.5) * 25)


def _recommended_category_budget(
    category: HouseholdSpendingCategory,
    coverage_months: int,
) -> float | None:
    # Caps key off gross monthly spend so a one-off refund credit does not silently
    # pull the suggested cap below the household's real recurring spend.
    cap_basis = category.gross_monthly_spend or category.average_monthly_spend
    if coverage_months < 2 or cap_basis <= 0:
        return None
    if category.essentiality == "essential":
        return _round_budget(cap_basis * 1.02)
    if category.essentiality == "mixed":
        return _round_budget(cap_basis * 0.95)
    return _round_budget(cap_basis * 0.85)


def _category_budget_meta(
    facts: list[HouseholdConfirmedFact],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for fact in facts:
        if not fact.fact_key.startswith(_CATEGORY_BUDGET_PREFIX):
            continue
        category = fact.fact_key.removeprefix(_CATEGORY_BUDGET_PREFIX)
        try:
            parsed = json.loads(fact.fact_value)
        except json.JSONDecodeError:
            parsed = {}
        result[category] = parsed if isinstance(parsed, dict) else {}
    return result


def _confirmed_budget_from_meta(meta: dict[str, Any] | None) -> float | None:
    value = (meta or {}).get("monthlyTarget")
    if isinstance(value, int | float) and math.isfinite(float(value)):
        return float(value)
    return None


# A verdict about a month has to be a verdict about most of the month. Past this
# much spend running outside the plan, "under your caps" is true of a minority of
# the money and false as a sentence about the month.
_UNJUDGED_SPEND_LIMIT = 0.25


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _budget_verdict(
    categories: list[HouseholdSpendingCategory],
    *,
    month_label: str,
) -> HouseholdBudgetVerdict:
    """Did the month come in under the household's own caps, and by what?

    Answers D2's first two sentences in the household's own terms: an overall
    under/over, and the per-category over/under it nets out of. The netting is
    the point -- "over on groceries, under on gas, under overall" is one
    subtraction, and a screen that shows only the breaches cannot say it.
    """
    over_total = 0.0
    under_total = 0.0
    cap_total = 0.0
    capped_actual = 0.0
    over_count = 0
    under_count = 0
    uncapped_spend = 0.0
    uncapped_count = 0
    largest_over: tuple[str, float] | None = None
    largest_under: tuple[str, float] | None = None

    for category in categories:
        if category.budget_disabled:
            continue
        cap = category.confirmed_monthly_budget
        if cap is None:
            if category.total_spend > 0:
                uncapped_spend += category.total_spend
                uncapped_count += 1
            continue
        cap_total += cap
        capped_actual += category.total_spend
        variance = category.total_spend - cap
        if variance > 0:
            over_total += variance
            over_count += 1
            if largest_over is None or variance > largest_over[1]:
                largest_over = (category.category, variance)
        elif variance < 0:
            under_total += -variance
            under_count += 1
            if largest_under is None or -variance > largest_under[1]:
                largest_under = (category.category, -variance)

    variance_total = capped_actual - cap_total
    total_spend = capped_actual + uncapped_spend

    def _netting_sentence() -> str:
        parts: list[str] = []
        if over_count:
            parts.append(
                f"{over_count} over by {_money(over_total)}"
                + (f" (most of it {largest_over[0]})" if largest_over else "")
            )
        if under_count:
            parts.append(
                f"{under_count} under by {_money(under_total)}"
                + (f" (most of it {largest_under[0]})" if largest_under else "")
            )
        if not parts:
            return "Every capped category landed exactly on its cap."
        return " · ".join(parts) + "."

    if cap_total <= 0:
        status = "no_plan"
        headline = f"No caps set, so {month_label} has nothing to be judged against."
        detail = (
            f"{_money(uncapped_spend)} of spending across {uncapped_count} "
            f"categor{'y' if uncapped_count == 1 else 'ies'} is unjudged. Set a cap "
            "on the categories that matter and this becomes a verdict."
        )
    elif total_spend > 0 and uncapped_spend / total_spend > _UNJUDGED_SPEND_LIMIT:
        status = "plan_incomplete"
        headline = (
            f"Only {_money(capped_actual)} of {month_label}'s {_money(total_spend)} "
            "has a cap, so there is no overall verdict yet."
        )
        detail = (
            f"{_money(uncapped_spend)} ran through {uncapped_count} uncapped "
            f"categor{'y' if uncapped_count == 1 else 'ies'}. Of what is capped: "
            + _netting_sentence()
        )
    elif variance_total > 0:
        status = "over_plan"
        headline = f"{month_label} came in {_money(variance_total)} over your caps."
        detail = _netting_sentence()
    else:
        status = "under_plan"
        headline = f"{month_label} came in {_money(-variance_total)} under your caps."
        detail = _netting_sentence()

    return HouseholdBudgetVerdict(
        status=status,
        headline=headline,
        detail=detail,
        cap_total=round(cap_total, 2),
        capped_actual=round(capped_actual, 2),
        variance=round(variance_total, 2),
        over_total=round(over_total, 2),
        under_total=round(under_total, 2),
        over_category_count=over_count,
        under_category_count=under_count,
        uncapped_spend=round(uncapped_spend, 2),
        uncapped_category_count=uncapped_count,
        largest_over_category=largest_over[0] if largest_over else None,
        largest_over_amount=round(largest_over[1], 2) if largest_over else 0.0,
        largest_under_category=largest_under[0] if largest_under else None,
        largest_under_amount=round(largest_under[1], 2) if largest_under else 0.0,
    )


def _with_budget_rollup(
    view: HouseholdSpendingView,
    facts: list[HouseholdConfirmedFact],
) -> HouseholdSpendingView:
    meta_by_category = _category_budget_meta(facts)
    coverage_months = view.summary.coverage_months
    categories: list[HouseholdSpendingCategory] = []
    found_budget_total = 0.0
    confirmed_budget_total = 0.0
    found_budget_category_count = 0
    confirmed_budget_category_count = 0
    found_over_budget_count = 0
    confirmed_over_budget_count = 0

    for category in view.categories:
        meta = meta_by_category.get(category.category)
        disabled = bool((meta or {}).get("disabled") is True)
        found_budget = _recommended_category_budget(category, coverage_months)
        confirmed_budget = _confirmed_budget_from_meta(meta)
        # A cap is suggested from the run-rate across every covered month, but
        # "over budget" is judged on the month being reported. The household says
        # "we overspent on groceries" about a month it lived through, not about a
        # six-month average that no single month resembles.
        actual = category.total_spend
        if disabled:
            budget_source = "disabled"
            budget_status = "disabled"
        elif confirmed_budget is not None:
            budget_source = "confirmed"
            budget_status = "over_budget" if actual > confirmed_budget else "confirmed"
            confirmed_budget_total += confirmed_budget
            confirmed_budget_category_count += 1
            if actual > confirmed_budget:
                confirmed_over_budget_count += 1
        elif found_budget is not None:
            budget_source = "found_unconfirmed"
            budget_status = (
                "found_over_budget" if actual > found_budget else "found_unconfirmed"
            )
            found_budget_total += found_budget
            found_budget_category_count += 1
            if actual > found_budget:
                found_over_budget_count += 1
        else:
            budget_source = "no_budget"
            budget_status = "no_budget"
        effective_budget = (
            None if disabled else (confirmed_budget if confirmed_budget is not None else found_budget)
        )
        categories.append(
            category.model_copy(
                update={
                    "found_monthly_budget": found_budget,
                    "confirmed_monthly_budget": confirmed_budget,
                    "budget_source": budget_source,
                    "budget_status": budget_status,
                    "budget_note": (meta or {}).get("note") or None,
                    "budget_disabled": disabled,
                    "effective_monthly_budget": effective_budget,
                    "budget_variance": (
                        None
                        if effective_budget is None
                        else round(actual - effective_budget, 2)
                    ),
                }
            )
        )

    verdict = _budget_verdict(categories, month_label=view.summary.month_label)
    summary = view.summary.model_copy(
        update={
            "found_budget_total": round(found_budget_total, 2),
            "confirmed_budget_total": round(confirmed_budget_total, 2),
            "budgeted_category_count": found_budget_category_count
            + confirmed_budget_category_count,
            "found_budget_category_count": found_budget_category_count,
            "confirmed_budget_category_count": confirmed_budget_category_count,
            "over_budget_count": found_over_budget_count + confirmed_over_budget_count,
            "found_over_budget_count": found_over_budget_count,
            "confirmed_over_budget_count": confirmed_over_budget_count,
        }
    )
    return view.model_copy(
        update={
            "summary": summary,
            "categories": categories,
            "budget_verdict": verdict,
        }
    )


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
        self.portfolio_position_sync_service = HouseholdPortfolioPositionSyncService()
        self.portfolio_transaction_sync_service = HouseholdPortfolioTransactionSyncService()
        self.product_enrichment_service = HouseholdProductEnrichmentService()
        self.dashboard_composer = HouseholdDashboardComposer()
        self.ledger_service = HouseholdLedgerService()
        self.document_pipeline = HouseholdDocumentPipeline()
        self.question_reconciler = HouseholdQuestionReconciler()
        self.profile_service = HouseholdProfileService()
        self.planning_service = HouseholdPlanningService()
        self.property_valuation_service = HouseholdPropertyValuationService()
        self.question_command_service = HouseholdQuestionCommandService()
        self.transaction_rule_service = HouseholdTransactionRuleService()
        self.purchase_item_service = HouseholdPurchaseItemService()
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
        status: str = "all",
        account: str = "all",
        search: str = "",
        sort: str = "date",
        sort_dir: str = "desc",
        limit: int = 100,
        offset: int = 0,
    ) -> HouseholdLedger:
        return self.ledger_service.get_ledger(
            self,
            window=window,
            kind=kind,
            status=status,
            account=account,
            search=search,
            sort=sort,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    def get_spending(self, *, month: str | None = None) -> HouseholdSpendingView:
        return _with_budget_rollup(
            self.transaction_service.build_spending_view(month=month),
            self.list_confirmed_facts(),
        )

    def get_net_worth_trend(self, *, days: int = 180) -> HouseholdNetWorthTrend:
        return build_net_worth_trend(self, days=days)

    def update_profile(self, payload: HouseholdProfileUpdate) -> HouseholdProfile:
        return self.profile_service.update_profile(self, payload)

    def get_planning_snapshot(self) -> HouseholdPlanningSnapshot:
        return self.planning_service.get_snapshot(self)

    def update_planning_snapshot(self, payload: HouseholdPlanningUpdate) -> HouseholdPlanningSnapshot:
        return self.planning_service.update_snapshot(self, payload)

    def list_property_valuation_histories(
        self,
        *,
        housing_cost_id: str | None = None,
        limit: int = 36,
    ) -> Any:
        return self.property_valuation_service.list_histories(
            self,
            housing_cost_id=housing_cost_id,
            limit=limit,
        )

    def refresh_property_valuation(
        self,
        housing_cost_id: str,
        *,
        address: str | None = None,
    ) -> Any:
        return self.property_valuation_service.refresh(
            self,
            housing_cost_id=housing_cost_id,
            address=address,
        )

    def refresh_due_property_valuations(self, *, max_age_days: int = 30) -> dict[str, object]:
        return self.property_valuation_service.refresh_due(self, max_age_days=max_age_days)

    def merge_planning_items(self, *, items: list[dict[str, object]], provenance: str, source_document_id: str | None = None) -> None:
        self.planning_service.merge_planning_items(self, items=items, provenance=provenance, source_document_id=source_document_id)

    def update_transaction_category(self, transaction_id: str, payload: HouseholdTransactionCategoryUpdate) -> bool:
        return self.transaction_rule_service.update_transaction_category(self, transaction_id, payload)

    def update_transaction_owner(self, transaction_id: str, payload: HouseholdTransactionOwnerUpdate) -> bool:
        return self.transaction_rule_service.update_transaction_owner(self, transaction_id, payload)

    def update_spend_override(self, transaction_id: str, payload: HouseholdSpendOverrideUpdate) -> bool:
        return self.transaction_rule_service.update_spend_override(self, transaction_id, payload)

    def repair_transaction_system(self, *, limit: int = 5000) -> dict[str, int]:
        return self.transaction_service.repair_transaction_system(limit=limit)

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
        return settings.household_upload_dir

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
