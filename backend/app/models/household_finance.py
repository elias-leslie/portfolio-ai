"""Pydantic models for the household finance dashboard."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HouseholdOverview(BaseModel):
    invested_assets: float
    retirement_assets: float
    taxable_assets: float
    cash_reserve: float
    total_tracked_assets: float
    visibility_score: int
    visibility_label: str
    next_best_action: str


class HouseholdProfile(BaseModel):
    id: str
    household_name: str
    monthly_net_income_target: float | None = None
    monthly_essential_target: float | None = None
    monthly_discretionary_target: float | None = None
    monthly_savings_target: float | None = None
    target_retirement_age: int | None = None
    target_retirement_spend: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdResolvedValue(BaseModel):
    field_name: str
    label: str
    value: str | None = None
    confidence: float | None = None
    status: str
    source: str
    rationale: str | None = None
    question: str | None = None


class HouseholdProfileUpdate(BaseModel):
    household_name: str | None = None
    monthly_net_income_target: float | None = None
    monthly_essential_target: float | None = None
    monthly_discretionary_target: float | None = None
    monthly_savings_target: float | None = None
    target_retirement_age: int | None = None
    target_retirement_spend: float | None = None
    notes: str | None = None


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
    monthly_spend_trend: list[HouseholdMonthlyTrendPoint] = Field(default_factory=list)
    recent_transactions: list[HouseholdRecentTransaction] = Field(default_factory=list)


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
    created_at: str
    answered_at: str | None = None


class HouseholdQuestionList(BaseModel):
    items: list[HouseholdQuestion] = Field(default_factory=list)


class HouseholdQuestionAnswer(BaseModel):
    answer_text: str


class JennyMoneyBrief(BaseModel):
    headline: str
    body: str
    prompts: list[str] = Field(default_factory=list)


class HouseholdFinanceDashboard(BaseModel):
    generated_at: str
    overview: HouseholdOverview
    profile: HouseholdProfile
    resolved_values: list[HouseholdResolvedValue] = Field(default_factory=list)
    budget_readiness: BudgetReadiness
    retirement_preparedness: RetirementPreparedness
    opportunities: list[HouseholdOpportunity] = Field(default_factory=list)
    reports: HouseholdReports
    import_center: ImportCenter
    questions: list[HouseholdQuestion] = Field(default_factory=list)
    jenny_brief: JennyMoneyBrief
