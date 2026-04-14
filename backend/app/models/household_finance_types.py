"""Auxiliary Pydantic models for the household finance dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HouseholdOverview(BaseModel):
    invested_assets: float
    retirement_assets: float
    taxable_assets: float
    cash_reserve: float
    total_tracked_assets: float
    liabilities_total: float = 0.0
    net_worth: float = 0.0
    tracked_account_count: int = 0
    needs_refresh_count: int = 0
    candidate_account_count: int = 0
    gap_count: int = 0
    inbox_count: int = 0
    coverage_months: int = 0
    last_transaction_date: str | None = None
    visibility_score: int
    visibility_label: str
    next_best_action: str
    net_worth_status: str = "current"
    net_worth_detail: str = "Net worth reflects current covered accounts."
    monthly_spend_status: str = "current"
    monthly_spend_detail: str = "Monthly spend reflects current covered transaction accounts."


class HouseholdResolvedValue(BaseModel):
    field_name: str
    label: str
    value: str | None = None
    confidence: float | None = None
    status: str
    source: str
    rationale: str | None = None
    question: str | None = None


class BudgetLane(BaseModel):
    name: str
    objective: str
    status: str


class BudgetReadiness(BaseModel):
    status: str
    summary: str
    priorities: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    starter_lanes: list[BudgetLane] = Field(default_factory=list)


class RetirementPreparedness(BaseModel):
    status: str
    summary: str
    retirement_account_share: float
    strengths: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class HouseholdOpportunity(BaseModel):
    title: str
    category: str
    impact: str
    detail: str
    next_step: str


class HouseholdExecutiveReport(BaseModel):
    headline: str
    summary: str
    average_monthly_spend: float
    average_monthly_essentials: float
    average_monthly_discretionary: float
    recent_30_day_spend: float
    recurring_merchant_count: int
    tracked_expense_count: int
    coverage_months: int


class HouseholdCategoryBreakdown(BaseModel):
    category: str
    essentiality: str
    monthly_average: float
    share_of_spend: float
    total_spend: float


class HouseholdMerchantInsight(BaseModel):
    merchant: str
    total_spend: float
    average_ticket: float
    transaction_count: int
    cadence: str
    category: str
    recommendation: str


class HouseholdPriceInsight(BaseModel):
    merchant: str
    item_name: str
    signal_type: str = "price_change"
    latest_price: float
    previous_price: float
    price_change: float
    price_change_pct: float | None = None
    latest_date: str
    previous_date: str
    latest_unit_label: str | None = None
    previous_unit_label: str | None = None
    unit_measure: str | None = None
    latest_unit_price: float | None = None
    previous_unit_price: float | None = None
    unit_price_change_pct: float | None = None
    size_change_pct: float | None = None
    shrinkflation_flag: bool = False
    confidence: float = 0.0
    recommendation: str


class HouseholdMonthlyTrendPoint(BaseModel):
    month: str
    total_spend: float
    transaction_count: int


class HouseholdRecentTransaction(BaseModel):
    date: str
    merchant: str
    description: str
    amount: float
    category: str
    essentiality: str
    account_label: str | None = None
    source_document_id: str | None = None


class HouseholdReports(BaseModel):
    executive: HouseholdExecutiveReport
    category_breakdown: list[HouseholdCategoryBreakdown] = Field(default_factory=list)
    merchant_highlights: list[HouseholdMerchantInsight] = Field(default_factory=list)
    price_insights: list[HouseholdPriceInsight] = Field(default_factory=list)
    monthly_spend_trend: list[HouseholdMonthlyTrendPoint] = Field(default_factory=list)
    recent_transactions: list[HouseholdRecentTransaction] = Field(default_factory=list)


class HouseholdBudgetSnapshot(BaseModel):
    status: str
    summary: str
    monthly_income_target: float | None = None
    monthly_plan_total: float | None = None
    essential_target: float | None = None
    discretionary_target: float | None = None
    savings_target: float | None = None
    actual_monthly_spend: float = 0.0
    actual_essential_monthly_spend: float = 0.0
    actual_discretionary_monthly_spend: float = 0.0
    month_to_date_spend: float = 0.0
    month_to_date_plan: float | None = None
    pace_status: str = "unknown"
    pace_detail: str
    remaining_cash_after_plan: float | None = None
    discretionary_headroom: float | None = None


class HouseholdCategorizationCandidate(BaseModel):
    id: str
    merchant: str
    description: str
    amount: float
    transaction_date: str
    current_category: str
    current_essentiality: str
    suggested_category: str
    suggested_essentiality: str
    confidence: float
    similar_transaction_count: int = 0
    reason: str


class HouseholdRecurringCommitment(BaseModel):
    merchant: str
    category: str
    cadence: str
    average_amount: float
    annualized_cost: float
    last_seen: str
    next_expected: str | None = None
    days_until_due: int | None = None
    due_status: str = "unknown"
    due_confidence: float = 0.0
    commitment_type: str


class HouseholdTransactionDateIssue(BaseModel):
    id: str
    transaction_id: str | None = None
    document_id: str
    filename: str
    source_type: str
    document_type: str
    transaction_date: str
    uploaded_at: str | None = None
    merchant: str
    description: str
    amount: float
    account_label: str | None = None
    confidence: float | None = None
    reason: str
    source_excerpt: str | None = None


class HouseholdSinkingFund(BaseModel):
    name: str
    monthly_target: float
    annual_cost: float
    rationale: str


class HouseholdRetirementContributionTracker(BaseModel):
    status: str
    monthly_target: float | None = None
    estimated_monthly_contributions: float = 0.0
    monthly_gap: float = 0.0
    detail: str


class HouseholdRetirementScenario(BaseModel):
    name: str
    monthly_spend: float
    annual_spend: float
    funded_years: float
    readiness: str
    detail: str


class ImportFormat(BaseModel):
    label: str
    formats: list[str] = Field(default_factory=list)
    extracts: list[str] = Field(default_factory=list)


class ImportCenter(BaseModel):
    headline: str
    tracked_documents: int = 0
    parsed_documents: int = 0
    suggested_first_uploads: list[str] = Field(default_factory=list)
    automations: list[str] = Field(default_factory=list)
    supported_documents: list[ImportFormat] = Field(default_factory=list)


class HouseholdEvidenceAccount(BaseModel):
    id: str
    document_id: str
    household_account_id: str | None = None
    source_type: str
    asset_group: str
    account_type: str
    institution_name: str | None = None
    account_name: str | None = None
    account_mask: str | None = None
    owner_name: str | None = None
    currency: str | None = None
    balance: float | None = None
    holdings_value: float | None = None
    cash_balance: float | None = None
    as_of_date: str | None = None
    confidence: float | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HouseholdTrackedAccount(BaseModel):
    id: str
    household_account_id: str | None = None
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdTrackedAccountInput(BaseModel):
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None


class HouseholdAccountGap(BaseModel):
    code: str
    severity: str
    title: str
    detail: str


class HouseholdAccountSummary(BaseModel):
    id: str
    household_account_id: str | None = None
    label: str
    asset_group: str
    account_type: str
    source_type: str
    match_key: str | None = None
    institution_name: str | None = None
    owner_name: str | None = None
    account_mask: str | None = None
    notes: str | None = None
    currency: str | None = None
    current_value: float | None = None
    balance: float | None = None
    holdings_value: float | None = None
    cash_balance: float | None = None
    valuation_source: str | None = None
    evidence_count: int = 0
    document_ids: list[str] = Field(default_factory=list)
    latest_document_id: str | None = None
    source_types: list[str] = Field(default_factory=list)
    linked_portfolio_account_id: str | None = None
    linked_portfolio_account_name: str | None = None
    tracked_account_id: str | None = None
    account_origin: str = "evidence"
    money_role: str = "net_worth_only"
    last_evidence_at: str | None = None
    days_since_evidence: int | None = None
    last_balance_at: str | None = None
    days_since_balance: int | None = None
    balance_freshness_status: str = "needs_evidence"
    balance_freshness_label: str = "Needs evidence"
    last_transaction_at: str | None = None
    days_since_transaction: int | None = None
    transaction_freshness_status: str = "needs_evidence"
    transaction_freshness_label: str = "Needs evidence"
    quote_updated_at: str | None = None
    quote_freshness_status: str = "not_applicable"
    quote_freshness_label: str = "No live quotes"
    quote_source: str | None = None
    priced_position_count: int = 0
    freshness_status: str
    freshness_label: str
    match_status: str
    match_confidence: float | None = None
    gap_flags: list[HouseholdAccountGap] = Field(default_factory=list)


class HouseholdInboxItem(BaseModel):
    id: str
    category: str
    priority: str
    title: str
    detail: str
    action_label: str
    action_href: str | None = None
    related_account_id: str | None = None
    related_question_id: str | None = None
    related_document_ids: list[str] = Field(default_factory=list)


class HouseholdDiscoveredAccount(BaseModel):
    key: str
    institution: str
    partial_account: str | None = None
    suggested_label: str
    asset_group: str
    account_type: str
    source_type: str
    confidence: float = 0.0
    occurrence_count: int = 1
    sample_description: str | None = None
    detail: str


class HouseholdDocument(BaseModel):
    id: str
    filename: str
    source_type: str
    document_type: str
    status: str
    account_label: str | None = None
    file_size_bytes: int
    content_type: str | None = None
    classification_confidence: float | None = None
    review_status: str | None = None
    review_summary: str | None = None
    review_confidence: float | None = None
    statement_start: str | None = None
    statement_end: str | None = None
    uploaded_at: str
    parsed_at: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HouseholdDocumentReview(BaseModel):
    id: str
    document_id: str
    status: str
    summary: str | None = None
    confidence: float | None = None
    extracted_text: str | None = None
    structured_data: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class HouseholdDocumentList(BaseModel):
    items: list[HouseholdDocument] = Field(default_factory=list)


class HouseholdQuestion(BaseModel):
    id: str
    field_name: str | None = None
    status: str
    priority: str
    question: str
    rationale: str | None = None
    recommendation: str | None = None
    answer_text: str | None = None
    source_document_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    question_format: str = "short_text"
    options: list[str] | None = None
    direction: str = "jenny_to_user"
    created_at: str
    answered_at: str | None = None


class HouseholdQuestionList(BaseModel):
    items: list[HouseholdQuestion] = Field(default_factory=list)


class JennyNeed(BaseModel):
    id: str
    need_type: str  # "provide" | "confirm" | "set" | "review"
    title: str
    detail: str
    priority: str  # "critical" | "high" | "medium" | "low"
    status: str  # "unsatisfied" | "satisfied"
    recurrence: str  # "periodic" | "one_time" | "as_needed"
    satisfaction_detail: str | None = None
    action_href: str | None = None
    related_question_id: str | None = None
    field_name: str | None = None
    question_format: str | None = None
    options: list[str] | None = None


class HouseholdConfirmedFact(BaseModel):
    fact_key: str
    fact_value: str
    confirmed_at: str


class ConfirmFactRequest(BaseModel):
    fact_key: str
    fact_value: str


class JennyProgression(BaseModel):
    found: list[str] = Field(default_factory=list)
    working_on: str | None = None


class JennyMoneyBrief(BaseModel):
    headline: str
    body: str
    prompts: list[str] = Field(default_factory=list)
    progression: JennyProgression | None = None


class PortfolioHouseholdContext(BaseModel):
    total_portfolio_value: float | None = None
    cash_reserves_months: float | None = None
    portfolio_to_annual_spend_ratio: float | None = None
    insights: list[str] = Field(default_factory=list)
