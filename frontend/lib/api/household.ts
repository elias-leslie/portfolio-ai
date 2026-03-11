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

export interface HouseholdResolvedValue {
  fieldName: string
  label: string
  value: string | null
  confidence: number | null
  status: string
  source: string
  rationale: string | null
  question: string | null
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

export interface HouseholdActionItem {
  title: string
  detail: string
  actionLabel: string
  href: string
  priority: string
  source: string
}

export interface HouseholdExecutiveReport {
  headline: string
  summary: string
  averageMonthlySpend: number
  averageMonthlyEssentials: number
  averageMonthlyDiscretionary: number
  recent30DaySpend: number
  recurringMerchantCount: number
  trackedExpenseCount: number
  coverageMonths: number
}

export interface HouseholdCategoryBreakdown {
  category: string
  essentiality: string
  monthlyAverage: number
  shareOfSpend: number
  totalSpend: number
}

export interface HouseholdMerchantInsight {
  merchant: string
  category: string
  totalSpend: number
  averageTicket: number
  transactionCount: number
  cadence: string
  recommendation: string
}

export interface HouseholdMonthlyTrendPoint {
  month: string
  totalSpend: number
  transactionCount: number
}

export interface HouseholdRecentTransaction {
  date: string
  merchant: string
  description: string
  amount: number
  category: string
  essentiality: string
  accountLabel: string | null
  sourceDocumentId?: string | null
}

export interface HouseholdReports {
  executive: HouseholdExecutiveReport
  categoryBreakdown: HouseholdCategoryBreakdown[]
  merchantHighlights: HouseholdMerchantInsight[]
  monthlySpendTrend: HouseholdMonthlyTrendPoint[]
  recentTransactions: HouseholdRecentTransaction[]
}

export interface HouseholdBudgetSnapshot {
  status: string
  summary: string
  monthlyIncomeTarget: number | null
  monthlyPlanTotal: number | null
  essentialTarget: number | null
  discretionaryTarget: number | null
  savingsTarget: number | null
  actualMonthlySpend: number
  actualEssentialMonthlySpend: number
  actualDiscretionaryMonthlySpend: number
  monthToDateSpend: number
  monthToDatePlan: number | null
  paceStatus: string
  paceDetail: string
  remainingCashAfterPlan: number | null
  discretionaryHeadroom: number | null
}

export interface HouseholdCategorizationCandidate {
  id: string
  merchant: string
  description: string
  amount: number
  transactionDate: string
  currentCategory: string
  currentEssentiality: string
  suggestedCategory: string
  suggestedEssentiality: string
  confidence: number
  similarTransactionCount: number
  reason: string
}

export interface HouseholdRecurringCommitment {
  merchant: string
  category: string
  cadence: string
  averageAmount: number
  annualizedCost: number
  lastSeen: string
  nextExpected: string | null
  daysUntilDue: number | null
  dueStatus: string
  dueConfidence: number
  commitmentType: string
}

export interface HouseholdSinkingFund {
  name: string
  monthlyTarget: number
  annualCost: number
  rationale: string
}

export interface HouseholdRetirementContributionTracker {
  status: string
  monthlyTarget: number | null
  estimatedMonthlyContributions: number
  monthlyGap: number
  detail: string
}

export interface HouseholdRetirementScenario {
  name: string
  monthlySpend: number
  annualSpend: number
  fundedYears: number
  readiness: string
  detail: string
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
  sourceType: string | null
  documentType: string | null
  status: string | null
  accountLabel: string | null
  fileSizeBytes: number
  contentType: string | null
  classificationConfidence: number | null
  reviewStatus: string | null
  reviewSummary: string | null
  reviewConfidence: number | null
  statementStart: string | null
  statementEnd: string | null
  uploadedAt: string
  parsedAt: string | null
  metadata: Record<string, unknown>
}

export interface HouseholdDocumentList {
  items: HouseholdDocument[]
}

export interface HouseholdQuestion {
  id: string
  fieldName: string | null
  status: string
  priority: string
  question: string
  rationale: string | null
  recommendation: string | null
  answerText: string | null
  sourceDocumentId: string | null
  metadata: Record<string, unknown>
  createdAt: string
  answeredAt: string | null
}

export interface HouseholdQuestionList {
  items: HouseholdQuestion[]
}

export interface JennyProgression {
  found: string[]
  workingOn: string | null
  needsFromYou: string[]
}

export interface JennyMoneyBrief {
  headline: string
  body: string
  prompts: string[]
  progression?: JennyProgression | null
}

export interface PortfolioHouseholdContext {
  totalPortfolioValue: number | null
  cashReservesMonths: number | null
  portfolioToAnnualSpendRatio: number | null
  insights: string[]
}

export interface HouseholdFinanceDashboard {
  generatedAt: string
  overview: HouseholdOverview
  profile: HouseholdProfile
  resolvedValues: HouseholdResolvedValue[]
  budgetReadiness: BudgetReadiness
  budgetSnapshot: HouseholdBudgetSnapshot
  retirementPreparedness: RetirementPreparedness
  actionItems: HouseholdActionItem[]
  opportunities: HouseholdOpportunity[]
  importCenter: ImportCenter
  questions: HouseholdQuestion[]
  jennyBrief: JennyMoneyBrief
  reports: HouseholdReports
  categorizationQueue: HouseholdCategorizationCandidate[]
  recurringCommitments: HouseholdRecurringCommitment[]
  sinkingFunds: HouseholdSinkingFund[]
  retirementContributionTracker: HouseholdRetirementContributionTracker
  retirementScenarios: HouseholdRetirementScenario[]
  portfolioContext?: PortfolioHouseholdContext | null
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

export interface HouseholdQuestionAnswer {
  answerText: string
}

export interface HouseholdTransactionCategoryUpdate {
  category: string
  essentiality: string
  applyToMerchant?: boolean
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

export async function fetchHouseholdQuestions(): Promise<HouseholdQuestionList> {
  return get<HouseholdQuestionList>('/api/household/questions')
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

export async function answerHouseholdQuestion(
  questionId: string,
  payload: HouseholdQuestionAnswer,
): Promise<HouseholdQuestion> {
  return post<HouseholdQuestion>(`/api/household/questions/${questionId}/answer`, payload)
}

export async function categorizeHouseholdTransaction(
  transactionId: string,
  payload: HouseholdTransactionCategoryUpdate,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(`/api/household/transactions/${transactionId}/categorize`, payload)
}
