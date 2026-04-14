import { del, get, post, postForm, put } from './client'
import type {
  HouseholdPlanningSnapshot,
  HouseholdPlanningUpdate,
} from './household-planning'

export type {
  HouseholdDocumentRequirement,
  HouseholdPlanningSnapshot,
  HouseholdPlanningUpdate,
} from './household-planning'

export interface HouseholdOverview {
  investedAssets: number
  retirementAssets: number
  taxableAssets: number
  cashReserve: number
  totalTrackedAssets: number
  liabilitiesTotal: number
  netWorth: number
  netWorthStatus: string
  netWorthDetail: string
  trackedAccountCount: number
  needsRefreshCount: number
  candidateAccountCount: number
  gapCount: number
  inboxCount: number
  coverageMonths: number
  lastTransactionDate: string | null
  visibilityScore: number
  visibilityLabel: string
  monthlySpendStatus: string
  monthlySpendDetail: string
  nextBestAction: string
}

export interface HouseholdProfile {
  id: string
  householdName: string
  adultCount?: number | null
  dependentCount?: number | null
  monthlyNetIncomeTarget: number | null
  monthlyEssentialTarget: number | null
  monthlyDiscretionaryTarget: number | null
  monthlySavingsTarget: number | null
  targetRetirementAge: number | null
  targetRetirementSpend: number | null
  filingStatus?: string | null
  stateOfResidence?: string | null
  effectiveTaxRate?: number | null
  marginalFederalTaxRate?: number | null
  marginalStateTaxRate?: number | null
  emergencyFundTargetMonths?: number | null
  emergencyFundTargetAmount?: number | null
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

export interface HouseholdPriceInsight {
  merchant: string
  itemName: string
  signalType: string
  latestPrice: number
  previousPrice: number
  priceChange: number
  priceChangePct?: number | null
  latestDate: string
  previousDate: string
  latestUnitLabel?: string | null
  previousUnitLabel?: string | null
  unitMeasure?: string | null
  latestUnitPrice?: number | null
  previousUnitPrice?: number | null
  unitPriceChangePct?: number | null
  sizeChangePct?: number | null
  shrinkflationFlag: boolean
  confidence: number
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
  priceInsights?: HouseholdPriceInsight[]
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

export interface HouseholdTransactionDateIssue {
  id: string
  transactionId: string | null
  documentId: string
  filename: string
  sourceType: string
  documentType: string
  transactionDate: string
  uploadedAt: string | null
  merchant: string
  description: string
  amount: number
  accountLabel: string | null
  confidence: number | null
  reason: string
  sourceExcerpt: string | null
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

export interface HouseholdEvidenceAccount {
  id: string
  documentId: string
  sourceType: string
  assetGroup: string
  accountType: string
  institutionName: string | null
  accountName: string | null
  accountMask: string | null
  ownerName: string | null
  currency: string | null
  balance: number | null
  holdingsValue: number | null
  cashBalance: number | null
  asOfDate: string | null
  confidence: number | null
  metadata: Record<string, unknown>
}

export interface HouseholdAccountGap {
  code: string
  severity: string
  title: string
  detail: string
}

export interface HouseholdTrackedAccount {
  id: string
  label: string
  assetGroup: string
  accountType: string
  sourceType: string
  matchKey?: string | null
  institutionName: string | null
  ownerName: string | null
  accountMask: string | null
  notes: string | null
  createdAt: string
  updatedAt: string
}

export interface HouseholdTrackedAccountInput {
  label: string
  assetGroup: string
  accountType: string
  sourceType: string
  matchKey?: string | null
  institutionName?: string | null
  ownerName?: string | null
  accountMask?: string | null
  notes?: string | null
}

export interface HouseholdDiscoveredAccount {
  key: string
  institution: string
  partialAccount?: string | null
  suggestedLabel: string
  assetGroup: string
  accountType: string
  sourceType: string
  confidence: number
  occurrenceCount: number
  sampleDescription?: string | null
  detail: string
}

export interface HouseholdAccountSummary {
  id: string
  householdAccountId?: string | null
  label: string
  assetGroup: string
  accountType: string
  sourceType: string
  matchKey?: string | null
  institutionName: string | null
  ownerName: string | null
  accountMask: string | null
  notes: string | null
  currency: string | null
  currentValue: number | null
  balance: number | null
  holdingsValue: number | null
  cashBalance: number | null
  valuationSource?: string | null
  evidenceCount: number
  documentIds: string[]
  latestDocumentId: string | null
  sourceTypes: string[]
  linkedPortfolioAccountId: string | null
  linkedPortfolioAccountName: string | null
  trackedAccountId: string | null
  accountOrigin: string
  moneyRole: string
  lastEvidenceAt: string | null
  daysSinceEvidence: number | null
  lastBalanceAt: string | null
  daysSinceBalance: number | null
  balanceFreshnessStatus: string
  balanceFreshnessLabel: string
  lastTransactionAt: string | null
  daysSinceTransaction: number | null
  transactionFreshnessStatus: string
  transactionFreshnessLabel: string
  quoteUpdatedAt?: string | null
  quoteFreshnessStatus?: string
  quoteFreshnessLabel?: string
  quoteSource?: string | null
  pricedPositionCount?: number
  freshnessStatus: string
  freshnessLabel: string
  matchStatus: string
  matchConfidence: number | null
  gapFlags: HouseholdAccountGap[]
}

export interface HouseholdInboxItem {
  id: string
  category: string
  priority: string
  title: string
  detail: string
  actionLabel: string
  actionHref: string | null
  relatedAccountId: string | null
  relatedQuestionId: string | null
  relatedDocumentIds: string[]
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
  questionFormat?: string
  options?: string[] | null
  direction?: string
  createdAt: string
  answeredAt: string | null
}

export interface HouseholdQuestionList {
  items: HouseholdQuestion[]
}

export interface HouseholdLedgerEntry {
  id: string
  kind: string
  householdAccountId?: string | null
  accountLabel?: string | null
  date?: string | null
  postedDate?: string | null
  merchant?: string | null
  description: string
  amount?: number | null
  currency?: string | null
  category?: string | null
  essentiality?: string | null
  datasetType?: string | null
  externalRowId?: string | null
  rowHash: string
  sourceDocumentId?: string | null
  sourceDocumentFilename?: string | null
  sourceType?: string | null
  documentType?: string | null
  uploadedAt?: string | null
}

export interface HouseholdLedger {
  generatedAt: string
  transactionCount: number
  importRowCount: number
  entries: HouseholdLedgerEntry[]
}

export interface JennyNeed {
  id: string
  needType: string
  title: string
  detail: string
  priority: string
  status: string
  recurrence: string
  satisfactionDetail: string | null
  actionHref: string | null
  relatedQuestionId: string | null
  fieldName: string | null
  questionFormat: string | null
  options: string[] | null
}

export interface HouseholdConfirmedFact {
  factKey: string
  factValue: string
  confirmedAt: string
}

export interface JennyProgression {
  found: string[]
  workingOn: string | null
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
  jennyNeeds: JennyNeed[]
  importCenter: ImportCenter
  evidenceAccounts: HouseholdEvidenceAccount[]
  accounts: HouseholdAccountSummary[]
  discoveredAccounts: HouseholdDiscoveredAccount[]
  inbox: HouseholdInboxItem[]
  questions: HouseholdQuestion[]
  jennyBrief: JennyMoneyBrief
  reports: HouseholdReports
  categorizationQueue: HouseholdCategorizationCandidate[]
  recurringCommitments: HouseholdRecurringCommitment[]
  transactionDateIssues: HouseholdTransactionDateIssue[]
  sinkingFunds: HouseholdSinkingFund[]
  retirementContributionTracker: HouseholdRetirementContributionTracker
  retirementScenarios: HouseholdRetirementScenario[]
  portfolioContext?: PortfolioHouseholdContext | null
  planning?: HouseholdPlanningSnapshot | null
}

export interface HouseholdProfileUpdate {
  householdName?: string
  adultCount?: number | null
  dependentCount?: number | null
  monthlyNetIncomeTarget?: number | null
  monthlyEssentialTarget?: number | null
  monthlyDiscretionaryTarget?: number | null
  monthlySavingsTarget?: number | null
  targetRetirementAge?: number | null
  targetRetirementSpend?: number | null
  filingStatus?: string | null
  stateOfResidence?: string | null
  effectiveTaxRate?: number | null
  marginalFederalTaxRate?: number | null
  marginalStateTaxRate?: number | null
  emergencyFundTargetMonths?: number | null
  emergencyFundTargetAmount?: number | null
  notes?: string | null
}

export interface HouseholdDocumentUpload {
  file?: File
  rawText?: string
  filename?: string
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

export async function fetchHouseholdPlanning(): Promise<HouseholdPlanningSnapshot> {
  return get<HouseholdPlanningSnapshot>('/api/household/planning')
}

export async function updateHouseholdPlanning(
  payload: HouseholdPlanningUpdate,
): Promise<HouseholdPlanningSnapshot> {
  return post<HouseholdPlanningSnapshot>('/api/household/planning', payload)
}

export async function fetchHouseholdDocuments(): Promise<HouseholdDocumentList> {
  return get<HouseholdDocumentList>('/api/intake/evidence')
}

export async function fetchHouseholdLedger(): Promise<HouseholdLedger> {
  return get<HouseholdLedger>('/api/household/ledger')
}

export async function fetchHouseholdQuestions(): Promise<HouseholdQuestionList> {
  return get<HouseholdQuestionList>('/api/household/questions')
}

export async function createHouseholdTrackedAccount(
  payload: HouseholdTrackedAccountInput,
): Promise<HouseholdTrackedAccount> {
  return post<HouseholdTrackedAccount>('/api/household/accounts', payload)
}

export async function updateHouseholdTrackedAccount(
  accountId: string,
  payload: HouseholdTrackedAccountInput,
): Promise<HouseholdTrackedAccount> {
  return put<HouseholdTrackedAccount>(
    `/api/household/accounts/${accountId}`,
    payload,
  )
}

export async function deleteHouseholdTrackedAccount(
  accountId: string,
): Promise<{ ok: boolean }> {
  return del<{ ok: boolean }>(`/api/household/accounts/${accountId}`)
}

export async function uploadHouseholdDocument(
  payload: HouseholdDocumentUpload,
): Promise<HouseholdDocument> {
  const rawText = payload.rawText?.trim()
  const file =
    payload.file ??
    (rawText
      ? new File([rawText], payload.filename?.trim() || 'pasted-evidence.txt', {
          type: 'text/plain',
        })
      : null)
  if (!file) {
    throw new Error('Upload requires a file or pasted text.')
  }
  const form = new FormData()
  form.append('file', file)
  if (payload.sourceType) {
    form.append('source_type', payload.sourceType)
  }
  if (payload.documentType) {
    form.append('document_type', payload.documentType)
  }
  if (payload.accountLabel) {
    form.append('account_label', payload.accountLabel)
  }
  return postForm<HouseholdDocument>('/api/intake/evidence', form)
}

export async function answerHouseholdQuestion(
  questionId: string,
  payload: HouseholdQuestionAnswer,
): Promise<HouseholdQuestion> {
  return post<HouseholdQuestion>(
    `/api/household/questions/${questionId}/answer`,
    payload,
  )
}

export async function fetchConfirmedFacts(): Promise<HouseholdConfirmedFact[]> {
  return get<HouseholdConfirmedFact[]>('/api/household/facts')
}

export async function confirmFact(
  factKey: string,
  factValue: string,
): Promise<HouseholdConfirmedFact> {
  return post<HouseholdConfirmedFact>('/api/household/facts', {
    factKey,
    factValue,
  })
}

export async function askJenny(question: string): Promise<HouseholdQuestion> {
  return post<HouseholdQuestion>('/api/household/ask', { question })
}

export async function categorizeHouseholdTransaction(
  transactionId: string,
  payload: HouseholdTransactionCategoryUpdate,
): Promise<{ ok: boolean }> {
  return post<{ ok: boolean }>(
    `/api/household/transactions/${transactionId}/categorize`,
    payload,
  )
}
