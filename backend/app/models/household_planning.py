"""Typed planning models for household budgeting and retirement data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HouseholdPlanningItemBase(BaseModel):
    confirmation_status: str = "confirmed"
    provenance: str = "manual"
    evidence_note: str | None = None
    source_document_id: str | None = None


class HouseholdPlanningMember(HouseholdPlanningItemBase):
    id: str
    display_name: str
    role: str
    relationship: str | None = None
    birth_year: int | None = None
    is_dependent: bool = False
    lives_in_household: bool = True
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdPlanningMemberInput(HouseholdPlanningItemBase):
    id: str | None = None
    display_name: str
    role: str
    relationship: str | None = None
    birth_year: int | None = None
    is_dependent: bool = False
    lives_in_household: bool = True
    notes: str | None = None


class HouseholdIncomeSource(HouseholdPlanningItemBase):
    id: str
    label: str
    owner_name: str | None = None
    source_type: str
    pay_frequency: str | None = None
    employer_or_source: str | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    monthly_amount: float | None = None
    annual_amount: float | None = None
    variable_income_notes: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdIncomeSourceInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    owner_name: str | None = None
    source_type: str
    pay_frequency: str | None = None
    employer_or_source: str | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    monthly_amount: float | None = None
    annual_amount: float | None = None
    variable_income_notes: str | None = None
    notes: str | None = None


class HouseholdDebtObligation(HouseholdPlanningItemBase):
    id: str
    label: str
    debt_type: str
    lender: str | None = None
    balance: float | None = None
    monthly_payment: float | None = None
    interest_rate: float | None = None
    payoff_target_date: str | None = None
    secured_by: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdDebtObligationInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    debt_type: str
    lender: str | None = None
    balance: float | None = None
    monthly_payment: float | None = None
    interest_rate: float | None = None
    payoff_target_date: str | None = None
    secured_by: str | None = None
    notes: str | None = None


class HouseholdHousingCost(HouseholdPlanningItemBase):
    id: str
    label: str
    housing_type: str
    occupancy_role: str
    monthly_payment: float | None = None
    property_tax_monthly: float | None = None
    hoa_monthly: float | None = None
    insurance_monthly: float | None = None
    utilities_monthly: float | None = None
    maintenance_monthly: float | None = None
    mortgage_balance: float | None = None
    interest_rate: float | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdHousingCostInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    housing_type: str
    occupancy_role: str = "primary"
    monthly_payment: float | None = None
    property_tax_monthly: float | None = None
    hoa_monthly: float | None = None
    insurance_monthly: float | None = None
    utilities_monthly: float | None = None
    maintenance_monthly: float | None = None
    mortgage_balance: float | None = None
    interest_rate: float | None = None
    notes: str | None = None


class HouseholdInsurancePolicy(HouseholdPlanningItemBase):
    id: str
    label: str
    coverage_type: str
    carrier: str | None = None
    premium_monthly: float | None = None
    coverage_amount: float | None = None
    deductible: float | None = None
    employer_sponsored: bool = False
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdInsurancePolicyInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    coverage_type: str
    carrier: str | None = None
    premium_monthly: float | None = None
    coverage_amount: float | None = None
    deductible: float | None = None
    employer_sponsored: bool = False
    notes: str | None = None


class HouseholdRetirementIncomeSource(HouseholdPlanningItemBase):
    id: str
    label: str
    source_type: str
    owner_name: str | None = None
    start_age: int | None = None
    monthly_amount: float | None = None
    annual_amount: float | None = None
    inflation_adjusted: bool = False
    survivor_benefit: bool = False
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdRetirementIncomeSourceInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    source_type: str
    owner_name: str | None = None
    start_age: int | None = None
    monthly_amount: float | None = None
    annual_amount: float | None = None
    inflation_adjusted: bool = False
    survivor_benefit: bool = False
    notes: str | None = None


class HouseholdRetirementHealthcareSchedule(HouseholdPlanningItemBase):
    id: str
    age: int
    real_amount: float
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdRetirementHealthcareScheduleInput(HouseholdPlanningItemBase):
    id: str | None = None
    age: int
    real_amount: float
    notes: str | None = None


class HouseholdPlannedExpense(HouseholdPlanningItemBase):
    id: str
    label: str
    expense_kind: str
    category: str
    target_amount: float | None = None
    target_date: str | None = None
    monthly_saving_target: float | None = None
    priority: str = "medium"
    notes: str | None = None
    created_at: str
    updated_at: str


class HouseholdPlannedExpenseInput(HouseholdPlanningItemBase):
    id: str | None = None
    label: str
    expense_kind: str
    category: str
    target_amount: float | None = None
    target_date: str | None = None
    monthly_saving_target: float | None = None
    priority: str = "medium"
    notes: str | None = None


class HouseholdDocumentRequirement(BaseModel):
    id: str
    requirement_key: str
    document_kind: str
    label: str
    status: str
    priority: str
    related_section: str | None = None
    related_record_id: str | None = None
    rationale: str | None = None
    notes: str | None = None
    source: str = "system"
    satisfied_by_document_id: str | None = None
    created_at: str
    updated_at: str


class HouseholdDocumentRequirementUpdate(BaseModel):
    id: str
    status: str | None = None
    notes: str | None = None


class HouseholdPlanningSectionStatus(BaseModel):
    section: str
    label: str
    status: str
    item_count: int = 0
    detail: str


class HouseholdPlanningSummary(BaseModel):
    completion_score: int = 0
    ready_sections: int = 0
    total_sections: int = 0
    missing_document_count: int = 0
    high_priority_document_count: int = 0
    sections: list[HouseholdPlanningSectionStatus] = Field(default_factory=list)


class HouseholdPlanningSnapshot(BaseModel):
    summary: HouseholdPlanningSummary = Field(default_factory=HouseholdPlanningSummary)
    members: list[HouseholdPlanningMember] = Field(default_factory=list)
    income_sources: list[HouseholdIncomeSource] = Field(default_factory=list)
    debt_obligations: list[HouseholdDebtObligation] = Field(default_factory=list)
    housing_costs: list[HouseholdHousingCost] = Field(default_factory=list)
    insurance_policies: list[HouseholdInsurancePolicy] = Field(default_factory=list)
    retirement_income_sources: list[HouseholdRetirementIncomeSource] = Field(default_factory=list)
    retirement_healthcare_schedule: list[HouseholdRetirementHealthcareSchedule] = Field(default_factory=list)
    planned_expenses: list[HouseholdPlannedExpense] = Field(default_factory=list)
    document_requirements: list[HouseholdDocumentRequirement] = Field(default_factory=list)


class HouseholdPlanningUpdate(BaseModel):
    members: list[HouseholdPlanningMemberInput] | None = None
    income_sources: list[HouseholdIncomeSourceInput] | None = None
    debt_obligations: list[HouseholdDebtObligationInput] | None = None
    housing_costs: list[HouseholdHousingCostInput] | None = None
    insurance_policies: list[HouseholdInsurancePolicyInput] | None = None
    retirement_income_sources: list[HouseholdRetirementIncomeSourceInput] | None = None
    retirement_healthcare_schedule: list[HouseholdRetirementHealthcareScheduleInput] | None = None
    planned_expenses: list[HouseholdPlannedExpenseInput] | None = None
    document_requirements: list[HouseholdDocumentRequirementUpdate] | None = None


def empty_household_planning_snapshot() -> HouseholdPlanningSnapshot:
    return HouseholdPlanningSnapshot()
