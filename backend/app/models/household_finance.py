"""Pydantic models for the household finance dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.household_finance_types import (
    BudgetLane,
    BudgetReadiness,
    ConfirmFactRequest,
    HouseholdAccountControl,
    HouseholdAccountControlIssue,
    HouseholdAccountGap,
    HouseholdAccountSummary,
    HouseholdBudgetSnapshot,
    HouseholdCategorizationCandidate,
    HouseholdCategoryBreakdown,
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
    HouseholdMonthlyTrendPoint,
    HouseholdNetWorthTrend,
    HouseholdNetWorthTrendPoint,
    HouseholdOpportunity,
    HouseholdOverview,
    HouseholdPriceInsight,
    HouseholdQuestion,
    HouseholdQuestionList,
    HouseholdRecentTransaction,
    HouseholdRecurringCommitment,
    HouseholdReports,
    HouseholdResolvedValue,
    HouseholdRetirementContributionTracker,
    HouseholdRetirementScenario,
    HouseholdSinkingFund,
    HouseholdSpendingCategory,
    HouseholdSpendingSummary,
    HouseholdSpendingTransaction,
    HouseholdSpendingView,
    HouseholdTrackedAccount,
    HouseholdTrackedAccountInput,
    HouseholdTransactionDateIssue,
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

__all__ = [
    "BudgetLane",
    "BudgetReadiness",
    "ConfirmFactRequest",
    "HouseholdAccountControl",
    "HouseholdAccountControlIssue",
    "HouseholdAccountGap",
    "HouseholdAccountSummary",
    "HouseholdBudgetSnapshot",
    "HouseholdCategorizationCandidate",
    "HouseholdCategoryBreakdown",
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
    "HouseholdMonthlyTrendPoint",
    "HouseholdNetWorthTrend",
    "HouseholdNetWorthTrendPoint",
    "HouseholdOpportunity",
    "HouseholdOverview",
    "HouseholdPriceInsight",
    "HouseholdProfile",
    "HouseholdProfileUpdate",
    "HouseholdQuestion",
    "HouseholdQuestionAnswer",
    "HouseholdQuestionList",
    "HouseholdRecentTransaction",
    "HouseholdRecurringCommitment",
    "HouseholdReports",
    "HouseholdResolvedValue",
    "HouseholdRetirementContributionTracker",
    "HouseholdRetirementScenario",
    "HouseholdSinkingFund",
    "HouseholdSpendingCategory",
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
