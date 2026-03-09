import { get, post, postForm } from './client'

export interface HouseholdOverview {
  investedAssets: number
  retirementAssets: number
  taxableAssets: number
  cashReserve: number
  totalTrackedAssets: number
  visibilityScore: number
  visibilityLabel: string
  nextBestAction: string
}

export interface HouseholdProfile {
  id: string
  householdName: string
  monthlyNetIncomeTarget: number | null
  monthlyEssentialTarget: number | null
  monthlyDiscretionaryTarget: number | null
  monthlySavingsTarget: number | null
  targetRetirementAge: number | null
  targetRetirementSpend: number | null
  notes: string | null
  createdAt: string
  updatedAt: string
}

export interface BudgetLane {
  name: string
  objective: string
  status: string
}

export interface BudgetReadiness {
  status: string
  summary: string
  priorities: string[]
  missingInputs: string[]
  starterLanes: BudgetLane[]
}

export interface RetirementPreparedness {
  status: string
  summary: string
  retirementAccountShare: number
  strengths: string[]
  blockers: string[]
  nextSteps: string[]
}

export interface HouseholdOpportunity {
  title: string
  category: string
  impact: string
  detail: string
  nextStep: string
}

export interface ImportFormat {
  label: string
  formats: string[]
  extracts: string[]
}

export interface ImportCenter {
  headline: string
  trackedDocuments: number
  parsedDocuments: number
  suggestedFirstUploads: string[]
  automations: string[]
  supportedDocuments: ImportFormat[]
}

export interface HouseholdDocument {
  id: string
  filename: string
  sourceType: string
  documentType: string
  status: string
  accountLabel: string | null
  fileSizeBytes: number
  contentType: string | null
  classificationConfidence: number | null
  statementStart: string | null
  statementEnd: string | null
  uploadedAt: string
  parsedAt: string | null
  metadata: Record<string, unknown>
}

export interface HouseholdDocumentList {
  items: HouseholdDocument[]
}

export interface JennyMoneyBrief {
  headline: string
  body: string
  prompts: string[]
}

export interface HouseholdFinanceDashboard {
  generatedAt: string
  overview: HouseholdOverview
  profile: HouseholdProfile
  budgetReadiness: BudgetReadiness
  retirementPreparedness: RetirementPreparedness
  opportunities: HouseholdOpportunity[]
  importCenter: ImportCenter
  jennyBrief: JennyMoneyBrief
}

export interface HouseholdProfileUpdate {
  householdName?: string
  monthlyNetIncomeTarget?: number | null
  monthlyEssentialTarget?: number | null
  monthlyDiscretionaryTarget?: number | null
  monthlySavingsTarget?: number | null
  targetRetirementAge?: number | null
  targetRetirementSpend?: number | null
  notes?: string | null
}

export interface HouseholdDocumentUpload {
  file: File
  sourceType?: string
  documentType?: string
  accountLabel?: string
}

export async function fetchHouseholdDashboard(): Promise<HouseholdFinanceDashboard> {
  return get<HouseholdFinanceDashboard>('/api/household/dashboard')
}

export async function fetchHouseholdProfile(): Promise<HouseholdProfile> {
  return get<HouseholdProfile>('/api/household/profile')
}

export async function updateHouseholdProfile(
  payload: HouseholdProfileUpdate,
): Promise<HouseholdProfile> {
  return post<HouseholdProfile>('/api/household/profile', payload)
}

export async function fetchHouseholdDocuments(): Promise<HouseholdDocumentList> {
  return get<HouseholdDocumentList>('/api/household/documents')
}

export async function uploadHouseholdDocument(
  payload: HouseholdDocumentUpload,
): Promise<HouseholdDocument> {
  const form = new FormData()
  form.append('file', payload.file)
  if (payload.sourceType) {
    form.append('sourceType', payload.sourceType)
  }
  if (payload.documentType) {
    form.append('documentType', payload.documentType)
  }
  if (payload.accountLabel) {
    form.append('accountLabel', payload.accountLabel)
  }
  return postForm<HouseholdDocument>('/api/household/documents', form)
}
