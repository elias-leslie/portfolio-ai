"""Pydantic models for the household finance dashboard."""

from __future__ import annotations

from pydantic import AliasChoices, BaseModel, Field

from app.models.household_finance_types import (
    BudgetLane,
    BudgetReadiness,
    ConfirmFactRequest,
    HouseholdAccountControl,
    HouseholdAccountControlIssue,
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdAssetAllocationSlice,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdCategoryBreakdown,
    HouseholdCategoryMonthlyTrendPoint,
    HouseholdConfirmedFact,
    HouseholdDiscoveredAccount,
    HouseholdDocument,
    HouseholdDocumentList,
    HouseholdDocumentReview,
    HouseholdEvidenceAccount,
    HouseholdExecutiveReport,
    HouseholdInboxItem,
    HouseholdLedger,
    HouseholdLedgerEntry,
    HouseholdMerchantInsight,
    HouseholdMonthComparison,
    HouseholdMonthlyTrendPoint,
    HouseholdNetWorthTrend,
    HouseholdNetWorthTrendPoint,
    HouseholdOpportunity,
    HouseholdOverview,
    HouseholdPriceCheckRun,
    HouseholdPriceCheckStatus,
    HouseholdPriceCheckTriggerResponse,
    HouseholdPriceCheckVendorStatus,
    HouseholdPriceFinding,
    HouseholdPriceInsight,
    HouseholdProductDetail,
    HouseholdProductIdentifier,
    HouseholdProductList,
    HouseholdProductMergeRequest,
    HouseholdProductPricePoint,
    HouseholdProductSummary,
    HouseholdPurchaseItem,
    HouseholdPurchaseItemCategoryUpdate,
    HouseholdPurchaseItemOwnerUpdate,
    HouseholdPurchaseItemProductAssignment,
    HouseholdPurchaseItemReviewQueue,
    HouseholdQuestion,
    HouseholdQuestionList,
    HouseholdRecentTransaction,
    HouseholdRecurringCommitment,
    HouseholdReports,
    HouseholdResolvedValue,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdShoppingList,
    HouseholdShoppingListImportRequest,
    HouseholdShoppingListImportResponse,
    HouseholdShoppingListItem,
    HouseholdShoppingListOptimizeRequest,
    HouseholdShoppingListRequest,
    HouseholdShoppingListsResponse,
    HouseholdShoppingListSuggestionDismissRequest,
    HouseholdShoppingListSuggestionItem,
    HouseholdShoppingListSuggestions,
    HouseholdSinkingFund,
    HouseholdSpendingCategory,
    HouseholdSpendingItemSplit,
    HouseholdSpendingSummary,
    HouseholdSpendingTransaction,
    HouseholdSpendingView,
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
    HouseholdTransactionDateIssue,
    HouseholdVendorProfile,
    HouseholdVendorProfileList,
    HouseholdVendorProfileUpdate,
    ImportCenter,
    ImportFormat,
    JennyMoneyBrief,
    JennyNeed,
    JennyProgression,
    PortfolioHouseholdContext,
    RetirementPreparedness,
)
from app.models.household_planning import (
    HouseholdPlanningSnapshot,
    empty_household_planning_snapshot,
)

_HOUSEHOLD_PURCHASE_MODEL_REEXPORTS = (
    HouseholdShoppingList,
    HouseholdShoppingListImportRequest,
    HouseholdShoppingListImportResponse,
    HouseholdShoppingListItem,
    HouseholdShoppingListOptimizeRequest,
    HouseholdShoppingListRequest,
    HouseholdShoppingListsResponse,
    HouseholdShoppingListSuggestionDismissRequest,
    HouseholdShoppingListSuggestionItem,
    HouseholdShoppingListSuggestions,
    HouseholdVendorProfile,
    HouseholdVendorProfileList,
    HouseholdVendorProfileUpdate,
)

__all__ = [
    "BudgetLane",
    "BudgetReadiness",
    "ConfirmFactRequest",
    "HouseholdAccountControl",
    "HouseholdAccountControlIssue",
    "HouseholdAccountGap",
    "HouseholdAccountSummary",
    "HouseholdAssetAllocationSlice",
    "HouseholdBudgetSnapshot",
    "HouseholdCategorizationCandidate",
    "HouseholdCategoryBreakdown",
    "HouseholdCategoryMonthlyTrendPoint",
    "HouseholdConfirmedFact",
    "HouseholdDiscoveredAccount",
    "HouseholdDocument",
    "HouseholdDocumentList",
    "HouseholdDocumentReview",
    "HouseholdEvidenceAccount",
    "HouseholdExecutiveReport",
    "HouseholdFinanceDashboard",
    "HouseholdInboxItem",
    "HouseholdLedger",
    "HouseholdLedgerEntry",
    "HouseholdMerchantInsight",
    "HouseholdMonthComparison",
    "HouseholdMonthlyTrendPoint",
    "HouseholdNetWorthTrend",
    "HouseholdNetWorthTrendPoint",
    "HouseholdOpportunity",
    "HouseholdOverview",
    "HouseholdPriceCheckRun",
    "HouseholdPriceCheckStatus",
    "HouseholdPriceCheckTriggerResponse",
    "HouseholdPriceCheckVendorStatus",
    "HouseholdPriceFinding",
    "HouseholdPriceInsight",
    "HouseholdProductDetail",
    "HouseholdProductIdentifier",
    "HouseholdProductList",
    "HouseholdProductMergeRequest",
    "HouseholdProductPricePoint",
    "HouseholdProductSummary",
    "HouseholdProfile",
    "HouseholdProfileUpdate",
    "HouseholdPurchaseItem",
    "HouseholdPurchaseItemCategoryUpdate",
    "HouseholdPurchaseItemOwnerUpdate",
    "HouseholdPurchaseItemProductAssignment",
    "HouseholdPurchaseItemReviewQueue",
    "HouseholdQuestion",
    "HouseholdQuestionAnswer",
    "HouseholdQuestionList",
    "HouseholdRecentTransaction",
    "HouseholdRecurringCommitment",
    "HouseholdReports",
    "HouseholdResolvedValue",
    "HouseholdRetirementContributionTracker",
    "HouseholdRetirementScenario",
    "HouseholdShoppingList",
    "HouseholdShoppingListImportRequest",
    "HouseholdShoppingListImportResponse",
    "HouseholdShoppingListItem",
    "HouseholdShoppingListOptimizeRequest",
    "HouseholdShoppingListRequest",
    "HouseholdShoppingListSuggestionDismissRequest",
    "HouseholdShoppingListSuggestionItem",
    "HouseholdShoppingListSuggestions",
    "HouseholdShoppingListsResponse",
    "HouseholdSinkingFund",
    "HouseholdSpendingCategory",
    "HouseholdSpendingItemSplit",
    "HouseholdSpendingSummary",
    "HouseholdSpendingTransaction",
    "HouseholdSpendingView",
    "HouseholdTrackedAccount",
    "HouseholdTrackedAccountInput",
    "HouseholdTransactionCategoryUpdate",
    "HouseholdTransactionDateIssue",
    "ImportCenter",
    "ImportFormat",
    "JennyMoneyBrief",
    "JennyNeed",
    "JennyProgression",
    "PortfolioHouseholdContext",
    "RetirementPreparedness",
]


class HouseholdProfile(BaseModel):
    id: str
    household_name: str
    adult_count: int | None = None
    dependent_count: int | None = None
    monthly_net_income_target: float | None = None
    monthly_essential_target: float | None = None
    monthly_discretionary_target: float | None = None
    monthly_savings_target: float | None = None
    target_retirement_age: int | None = None
    target_spouse_retirement_age: int | None = None
    target_retirement_spend: float | None = None
    retirement_inflation_rate: float | None = None
    retirement_horizon_years: int | None = None
    primary_social_security_monthly: float | None = None
    spouse_social_security_monthly: float | None = None
    primary_social_security_annual_earnings: float | None = None
    spouse_social_security_annual_earnings: float | None = None
    primary_social_security_start_age: int | None = None
    spouse_social_security_start_age: int | None = None
    social_security_payable_ratio: float | None = None
    filing_status: str | None = None
    state_of_residence: str | None = None
    effective_tax_rate: float | None = None
    marginal_federal_tax_rate: float | None = None
    marginal_state_tax_rate: float | None = None
    emergency_fund_target_months: float | None = None
    emergency_fund_target_amount: float | None = None
    withdrawal_strategy: str | None = None
    withdrawal_initial_rate: float | None = None
    withdrawal_decline_mode: str | None = None
    discretionary_decline_rate: float | None = None
    phase_slow_go_age: int | None = None
    phase_no_go_age: int | None = None
    phase_go_go_pct: float | None = None
    phase_slow_go_pct: float | None = None
    phase_no_go_pct: float | None = None
    bridge_mode: str | None = None
    bridge_manual_amount: float | None = None
    bridge_real_return: float | None = None
    bridge_growth: str | None = None
    retirement_essential_floor_override: float | None = None
    retirement_discretionary_override: float | None = None
    aca_tier: str | None = None
    aca_premium_age21_override: float | None = None
    aca_oop_monthly: float | None = None
    medicare_monthly_per_person: float | None = None
    spouse_net_monthly_income: float | None = None
    partial_retirement_monthly_spend: float | None = None
    spouse_gross_annual_income: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdProfileUpdate(BaseModel):
    household_name: str | None = None
    adult_count: int | None = None
    dependent_count: int | None = None
    monthly_net_income_target: float | None = None
    monthly_essential_target: float | None = None
    monthly_discretionary_target: float | None = None
    monthly_savings_target: float | None = None
    target_retirement_age: int | None = None
    target_spouse_retirement_age: int | None = None
    target_retirement_spend: float | None = None
    retirement_inflation_rate: float | None = None
    retirement_horizon_years: int | None = None
    primary_social_security_monthly: float | None = None
    spouse_social_security_monthly: float | None = None
    primary_social_security_annual_earnings: float | None = None
    spouse_social_security_annual_earnings: float | None = None
    primary_social_security_start_age: int | None = None
    spouse_social_security_start_age: int | None = None
    social_security_payable_ratio: float | None = None
    filing_status: str | None = None
    state_of_residence: str | None = None
    effective_tax_rate: float | None = None
    marginal_federal_tax_rate: float | None = None
    marginal_state_tax_rate: float | None = None
    emergency_fund_target_months: float | None = None
    emergency_fund_target_amount: float | None = None
    withdrawal_strategy: str | None = None
    withdrawal_initial_rate: float | None = None
    withdrawal_decline_mode: str | None = None
    discretionary_decline_rate: float | None = None
    phase_slow_go_age: int | None = None
    phase_no_go_age: int | None = None
    phase_go_go_pct: float | None = None
    phase_slow_go_pct: float | None = None
    phase_no_go_pct: float | None = None
    bridge_mode: str | None = None
    bridge_manual_amount: float | None = None
    bridge_real_return: float | None = None
    bridge_growth: str | None = None
    retirement_essential_floor_override: float | None = None
    retirement_discretionary_override: float | None = None
    aca_tier: str | None = None
    # The frontend wire layer (es-toolkit) splits camelCase at every
    # letter/digit boundary, so saves arrive as
    # ``aca_premium_age_21_override``; the field name still matches the
    # DB column for the SET clause in update_profile.
    aca_premium_age21_override: float | None = Field(
        None,
        validation_alias=AliasChoices(
            "aca_premium_age21_override", "aca_premium_age_21_override"
        ),
    )
    aca_oop_monthly: float | None = None
    medicare_monthly_per_person: float | None = None
    spouse_net_monthly_income: float | None = None
    partial_retirement_monthly_spend: float | None = None
    spouse_gross_annual_income: float | None = None
    notes: str | None = None


class HouseholdQuestionAnswer(BaseModel):
    answer_text: str


class HouseholdTransactionCategoryUpdate(BaseModel):
    category: str
    essentiality: str
    apply_to_merchant: bool = False


class HouseholdFinanceDashboard(BaseModel):
    generated_at: str
    overview: HouseholdOverview
    account_control: HouseholdAccountControl
    profile: HouseholdProfile
    resolved_values: list[HouseholdResolvedValue] = Field(default_factory=list)
    budget_readiness: BudgetReadiness
    budget_snapshot: HouseholdBudgetSnapshot
    retirement_preparedness: RetirementPreparedness
    jenny_needs: list[JennyNeed] = Field(default_factory=list)
    reports: HouseholdReports
    categorization_queue: list[HouseholdCategorizationCandidate] = Field(default_factory=list)
    recurring_commitments: list[HouseholdRecurringCommitment] = Field(default_factory=list)
    transaction_date_issues: list[HouseholdTransactionDateIssue] = Field(default_factory=list)
    sinking_funds: list[HouseholdSinkingFund] = Field(default_factory=list)
    retirement_contribution_tracker: HouseholdRetirementContributionTracker
    retirement_scenarios: list[HouseholdRetirementScenario] = Field(default_factory=list)
    import_center: ImportCenter
    evidence_accounts: list[HouseholdEvidenceAccount] = Field(default_factory=list)
    accounts: list[HouseholdAccountSummary] = Field(default_factory=list)
    discovered_accounts: list[HouseholdDiscoveredAccount] = Field(default_factory=list)
    inbox: list[HouseholdInboxItem] = Field(default_factory=list)
    questions: list[HouseholdQuestion] = Field(default_factory=list)
    jenny_brief: JennyMoneyBrief
    portfolio_context: PortfolioHouseholdContext | None = None
    planning: HouseholdPlanningSnapshot = Field(default_factory=empty_household_planning_snapshot)
