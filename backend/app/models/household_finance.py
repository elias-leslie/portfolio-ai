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
    statement_start: str | None = None
    statement_end: str | None = None
    uploaded_at: str
    parsed_at: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class HouseholdDocumentList(BaseModel):
    items: list[HouseholdDocument] = Field(default_factory=list)


class JennyMoneyBrief(BaseModel):
    headline: str
    body: str
    prompts: list[str] = Field(default_factory=list)


class HouseholdFinanceDashboard(BaseModel):
    generated_at: str
    overview: HouseholdOverview
    profile: HouseholdProfile
    budget_readiness: BudgetReadiness
    retirement_preparedness: RetirementPreparedness
    opportunities: list[HouseholdOpportunity] = Field(default_factory=list)
    import_center: ImportCenter
    jenny_brief: JennyMoneyBrief
