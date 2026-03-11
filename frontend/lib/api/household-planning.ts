export interface HouseholdPlanningMember {
  id: string
  displayName: string
  role: string
  relationship?: string | null
  birthYear?: number | null
  isDependent?: boolean
  livesInHousehold?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdPlanningMemberInput {
  id?: string | null
  displayName: string
  role: string
  relationship?: string | null
  birthYear?: number | null
  isDependent?: boolean
  livesInHousehold?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdIncomeSource {
  id: string
  label: string
  ownerName?: string | null
  sourceType: string
  payFrequency?: string | null
  employerOrSource?: string | null
  grossAmount?: number | null
  netAmount?: number | null
  monthlyAmount?: number | null
  annualAmount?: number | null
  variableIncomeNotes?: string | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdIncomeSourceInput {
  id?: string | null
  label: string
  ownerName?: string | null
  sourceType: string
  payFrequency?: string | null
  employerOrSource?: string | null
  grossAmount?: number | null
  netAmount?: number | null
  monthlyAmount?: number | null
  annualAmount?: number | null
  variableIncomeNotes?: string | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdDebtObligation {
  id: string
  label: string
  debtType: string
  lender?: string | null
  balance?: number | null
  monthlyPayment?: number | null
  interestRate?: number | null
  payoffTargetDate?: string | null
  securedBy?: string | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdDebtObligationInput {
  id?: string | null
  label: string
  debtType: string
  lender?: string | null
  balance?: number | null
  monthlyPayment?: number | null
  interestRate?: number | null
  payoffTargetDate?: string | null
  securedBy?: string | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdHousingCost {
  id: string
  label: string
  housingType: string
  occupancyRole: string
  monthlyPayment?: number | null
  propertyTaxMonthly?: number | null
  hoaMonthly?: number | null
  insuranceMonthly?: number | null
  utilitiesMonthly?: number | null
  maintenanceMonthly?: number | null
  mortgageBalance?: number | null
  interestRate?: number | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdHousingCostInput {
  id?: string | null
  label: string
  housingType: string
  occupancyRole: string
  monthlyPayment?: number | null
  propertyTaxMonthly?: number | null
  hoaMonthly?: number | null
  insuranceMonthly?: number | null
  utilitiesMonthly?: number | null
  maintenanceMonthly?: number | null
  mortgageBalance?: number | null
  interestRate?: number | null
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdInsurancePolicy {
  id: string
  label: string
  coverageType: string
  carrier?: string | null
  premiumMonthly?: number | null
  coverageAmount?: number | null
  deductible?: number | null
  employerSponsored?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdInsurancePolicyInput {
  id?: string | null
  label: string
  coverageType: string
  carrier?: string | null
  premiumMonthly?: number | null
  coverageAmount?: number | null
  deductible?: number | null
  employerSponsored?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdRetirementIncomeSource {
  id: string
  label: string
  sourceType: string
  ownerName?: string | null
  startAge?: number | null
  monthlyAmount?: number | null
  annualAmount?: number | null
  inflationAdjusted?: boolean
  survivorBenefit?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdRetirementIncomeSourceInput {
  id?: string | null
  label: string
  sourceType: string
  ownerName?: string | null
  startAge?: number | null
  monthlyAmount?: number | null
  annualAmount?: number | null
  inflationAdjusted?: boolean
  survivorBenefit?: boolean
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdPlannedExpense {
  id: string
  label: string
  expenseKind: string
  category: string
  targetAmount?: number | null
  targetDate?: string | null
  monthlySavingTarget?: number | null
  priority: string
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdPlannedExpenseInput {
  id?: string | null
  label: string
  expenseKind: string
  category: string
  targetAmount?: number | null
  targetDate?: string | null
  monthlySavingTarget?: number | null
  priority?: string
  notes?: string | null
  confirmationStatus?: string
  provenance?: string
  evidenceNote?: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdDocumentRequirement {
  id: string
  requirementKey: string
  documentKind: string
  label: string
  status: string
  priority: string
  relatedSection?: string | null
  relatedRecordId?: string | null
  rationale?: string | null
  notes?: string | null
  source: string
  satisfiedByDocumentId?: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdDocumentRequirementUpdate {
  id: string
  status?: string | null
  notes?: string | null
}

export interface HouseholdPlanningSectionStatus {
  section: string
  label: string
  status: string
  itemCount: number
  detail: string
}

export interface HouseholdPlanningSummary {
  completionScore: number
  readySections: number
  totalSections: number
  missingDocumentCount: number
  highPriorityDocumentCount: number
  sections: HouseholdPlanningSectionStatus[]
}

export interface HouseholdPlanningSnapshot {
  summary: HouseholdPlanningSummary
  members: HouseholdPlanningMember[]
  incomeSources: HouseholdIncomeSource[]
  debtObligations: HouseholdDebtObligation[]
  housingCosts: HouseholdHousingCost[]
  insurancePolicies: HouseholdInsurancePolicy[]
  retirementIncomeSources: HouseholdRetirementIncomeSource[]
  plannedExpenses: HouseholdPlannedExpense[]
  documentRequirements: HouseholdDocumentRequirement[]
}

export interface HouseholdPlanningUpdate {
  members?: HouseholdPlanningMemberInput[]
  incomeSources?: HouseholdIncomeSourceInput[]
  debtObligations?: HouseholdDebtObligationInput[]
  housingCosts?: HouseholdHousingCostInput[]
  insurancePolicies?: HouseholdInsurancePolicyInput[]
  retirementIncomeSources?: HouseholdRetirementIncomeSourceInput[]
  plannedExpenses?: HouseholdPlannedExpenseInput[]
  documentRequirements?: HouseholdDocumentRequirementUpdate[]
}
