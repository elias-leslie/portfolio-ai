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
  /** Credit/debt and non-positive groups excluded, sorted desc by value. */
  assetAllocation: Array<{ assetGroup: string; totalValue: number }>
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

export interface HouseholdAccountControlIssue {
  id: string
  code: string
  severity: string
  title: string
  detail: string
  householdAccountId: string | null
  accountLabel: string | null
  source: string | null
  sourceAccountIds: string[]
  affectsTotals: boolean
}

export interface HouseholdAccountControl {
  status: string
  summary: string
  issueCount: number
  blockingIssueCount: number
  checkedAt: string
  issues: HouseholdAccountControlIssue[]
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
  targetSpouseRetirementAge?: number | null
  targetRetirementSpend: number | null
  retirementInflationRate?: number | null
  retirementHorizonYears?: number | null
  primarySocialSecurityMonthly?: number | null
  spouseSocialSecurityMonthly?: number | null
  primarySocialSecurityAnnualEarnings?: number | null
  spouseSocialSecurityAnnualEarnings?: number | null
  primarySocialSecurityStartAge?: number | null
  spouseSocialSecurityStartAge?: number | null
  socialSecurityPayableRatio?: number | null
  filingStatus?: string | null
  stateOfResidence?: string | null
  effectiveTaxRate?: number | null
  marginalFederalTaxRate?: number | null
  marginalStateTaxRate?: number | null
  emergencyFundTargetMonths?: number | null
  emergencyFundTargetAmount?: number | null
  withdrawalStrategy?: string | null
  withdrawalInitialRate?: number | null
  withdrawalDeclineMode?: string | null
  discretionaryDeclineRate?: number | null
  phaseSlowGoAge?: number | null
  phaseNoGoAge?: number | null
  phaseGoGoPct?: number | null
  phaseSlowGoPct?: number | null
  phaseNoGoPct?: number | null
  bridgeMode?: string | null
  bridgeManualAmount?: number | null
  bridgeRealReturn?: number | null
  bridgeGrowth?: 'fixed' | 'portfolio' | null
  retirementEssentialFloorOverride?: number | null
  retirementDiscretionaryOverride?: number | null
  acaTier?: string | null
  acaPremiumAge21Override?: number | null
  acaOopMonthly?: number | null
  medicareMonthlyPerPerson?: number | null
  spouseNetMonthlyIncome?: number | null
  partialRetirementMonthlySpend?: number | null
  spouseGrossAnnualIncome?: number | null
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

export type HouseholdPriceSignalType =
  | 'shrinkflation'
  | 'unit_price_up'
  | 'price_up'
  | 'price_down'

export interface HouseholdPriceInsight {
  merchant: string
  itemName: string
  signalType: HouseholdPriceSignalType
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

export interface HouseholdNetWorthTrendPoint {
  date: string
  netWorth: number
  totalAssets: number
  liabilities: number
  pricedHoldingsValue: number
  fixedAssets: number
}

export interface HouseholdNetWorthTrend {
  generatedAt: string
  asOfDate: string | null
  status: string
  detail: string
  methodology: string
  points: HouseholdNetWorthTrendPoint[]
  holdingsSymbolCount: number
  holdingsPositionCount: number
  gapCount: number
  needsRefreshCount: number
  missingBalanceAccountCount: number
  staleAccountCount: number
}

export interface HouseholdPropertyValuationPoint {
  id: string
  housingCostId: string
  source: string
  sourceLabel: string
  estimateValue: number
  rangeLow?: number | null
  rangeHigh?: number | null
  confidence?: number | null
  asOf: string
  fetchedAt: string
  methodology?: string | null
  sourceUrl?: string | null
  metadata: Record<string, unknown>
}

export interface HouseholdPropertyValuationHistory {
  housingCostId: string
  latest?: HouseholdPropertyValuationPoint | null
  points: HouseholdPropertyValuationPoint[]
}

export interface HouseholdPropertyValuationHistoryList {
  items: HouseholdPropertyValuationHistory[]
}

export interface HouseholdPropertyValuationRefreshResult {
  valuation: HouseholdPropertyValuationPoint
  history: HouseholdPropertyValuationHistory
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

/** Latest vs previous COMPLETED month, computed on the server clock. */
export interface HouseholdMonthComparison {
  latestMonth: string
  previousMonth: string
  latestTotal: number
  previousTotal: number
  change: number
  changePct: number | null
}

export interface HouseholdReports {
  executive: HouseholdExecutiveReport
  categoryBreakdown: HouseholdCategoryBreakdown[]
  merchantHighlights: HouseholdMerchantInsight[]
  priceInsights?: HouseholdPriceInsight[]
  monthlySpendTrend: HouseholdMonthlyTrendPoint[]
  monthComparison: HouseholdMonthComparison | null
  recentTransactions: HouseholdRecentTransaction[]
}

export interface HouseholdBudgetSnapshot {
  status: string
  summary: string
  monthlyIncomeTarget: number | null
  monthlyPlanTotal: number | null
  monthlyPlanSource: string
  monthlyPlanSourceLabel: string
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
  planIsPartial: boolean
  missingPlanComponents: string[]
  remainingCashAfterPlan: number | null
  discretionaryHeadroom: number | null
  safeToSpend: number | null
  safeToSpendConstraint:
    | 'cash_after_cushion'
    | 'plan_residual'
    | 'discretionary_cap'
    | null
  dueSoonBillsTotal: number | null
  operatingCushion: number
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

export interface RetirementWithdrawalPhaseConfig {
  slowGoAge: number
  noGoAge: number
  goGoPct: number
  slowGoPct: number
  noGoPct: number
}

export interface RetirementWithdrawalBridgeConfig {
  mode: 'auto' | 'manual'
  manualAmount?: number | null
  realReturn: number
  /** fixed = deterministic realReturn; portfolio = rides simulated returns. */
  growth?: 'fixed' | 'portfolio'
}

export interface RetirementAllocationScenarioHolding {
  symbol: string
  weight: number
}

export interface RetirementAllocationScenarioInput {
  id?: string | null
  name: string
  holdings: RetirementAllocationScenarioHolding[]
  bridgeGrowth?: 'fixed' | 'portfolio' | null
  bridgeRealReturn?: number | null
  notes?: string | null
}

export interface RetirementAllocationScenario
  extends RetirementAllocationScenarioInput {
  id: string
  createdAt: string
  updatedAt: string
}

export interface RetirementWithdrawalHealthcarePoint {
  age: number
  realAmount: number
}

export interface RetirementSpendingReduction {
  label: string
  startAge: number
  annualAmount: number
}

export interface RetirementLiquidityEvent {
  label: string
  calendarYear: number
  realAmount: number
}

export interface RetirementIncomeSourceInput {
  label: string
  sourceType?: string | null
  ownerName?: string | null
  startAge: number
  monthlyAmount: number
  inflationAdjusted?: boolean
  survivorBenefit?: number | null
}

export interface RetirementWithdrawalConfig {
  strategy: 'guardrails'
  initialRate: number
  declineMode: 'smooth' | 'phase'
  discretionaryDeclineRate: number
  phase: RetirementWithdrawalPhaseConfig
  bridge: RetirementWithdrawalBridgeConfig
  healthcareSchedule: RetirementWithdrawalHealthcarePoint[]
  essentialFloor?: number | null
  baseDiscretionary?: number | null
}

export interface RetirementPreviewRequest {
  householdId: string
  name?: string | null
  trials?: number
  seed?: number | null
  annualExpenses?: number | null
  annualContribution?: number | null
  assetAllocation?: Record<string, number> | null
  allocationHoldings?: Array<{
    symbol: string
    weight: number
    dividendYield?: number | null
  }> | null
  cashYield?: number | null
  monthlySpend?: number | null
  retirementAge?: number | null
  spouseRetirementAge?: number | null
  horizonYears?: number | null
  inflationRate?: number | null
  primaryAge?: number | null
  spouseAge?: number | null
  primarySocialSecurityMonthly?: number | null
  spouseSocialSecurityMonthly?: number | null
  primarySocialSecurityAnnualEarnings?: number | null
  spouseSocialSecurityAnnualEarnings?: number | null
  primarySocialSecurityStartAge?: number | null
  spouseSocialSecurityStartAge?: number | null
  socialSecurityPayableRatio?: number | null
  /** Partial-retirement window levers (real $); net income gates the feature. */
  spouseNetMonthlyIncome?: number | null
  partialRetirementMonthlySpend?: number | null
  spouseGrossAnnualIncome?: number | null
  withdrawal?: RetirementWithdrawalConfig | null
  /** Explicit schedule (even empty) wins over the persisted one. */
  collegeSchedule?: RetirementCollegeYear[] | null
  /** Living-spend reductions such as children becoming self-funded. */
  spendingReductions?: RetirementSpendingReduction[] | null
  /** One-time real cash events, e.g. planned property sale proceeds. */
  liquidityEvents?: RetirementLiquidityEvent[] | null
  /** Preview-only recurring real income streams from manually modeled assets. */
  extraIncomeSources?: RetirementIncomeSourceInput[] | null
  /** Explicit ACA/Medicare lever config wins over the profile defaults. */
  aca?: RetirementAcaConfig | null
  asOfDate?: string | null
}

export interface RetirementCollegeYear {
  calendarYear: number
  realAmount: number
}

export interface RetirementAcaPerson {
  birthYear: number
  /** Exclusive year coverage ends; null = covered until Medicare at 65. */
  coveredUntilYear?: number | null
}

export interface RetirementAcaConfig {
  tier: 'silver' | 'bronze' | 'none'
  /** Age-21 monthly premium override; null = marketplace anchor. */
  premiumAge21MonthlyOverride?: number | null
  oopMonthly?: number | null
  /** Part B/D + supplement per member 65+; null = published default, 0 = off. */
  medicareMonthlyPerPerson?: number | null
  /** Dependents covered until this age; null = 22 default, 0 = adults only. */
  dependentsCoveredUntilAge?: number | null
  healthcareRealInflation?: number | null
  /** Server-derived from household members; requests omit this. */
  persons?: RetirementAcaPerson[]
  planYear?: number | null
  benchmarkAge21Monthly?: number | null
  chosenAge21Monthly?: number | null
}

export interface RetirementIncomeActualsStream {
  streamKey: string
  label: string
  owner: string | null
  ownerOverride: boolean
  cadence: 'weekly' | 'biweekly' | 'monthly' | 'irregular' | 'one-off'
  monthlyAverage: number
  runRateMonthly: number
  total: number
  transactionCount: number
  firstDate: string
  lastDate: string
  monthsSeen: number
  monthsSpanned: number
  active: boolean
  portfolioYield: boolean
  status:
    | 'active'
    | 'stopped'
    | 'one_off'
    | 'portfolio_yield'
    | 'ignored'
    | 'merged'
  statusOverride:
    | 'active'
    | 'stopped'
    | 'one_off'
    | 'portfolio_yield'
    | 'ignored'
    | 'merged'
    | null
  mergedIntoStreamKey: string | null
}

export interface RetirementIncomeStreamOverrideUpdate {
  ownerName?: string | null
  status?:
    | 'active'
    | 'stopped'
    | 'one_off'
    | 'portfolio_yield'
    | 'ignored'
    | 'merged'
    | null
  mergedIntoStreamKey?: string | null
  label?: string | null
}

export interface RetirementIncomeActuals {
  generatedAt: string
  firstMonth: string | null
  lastMonth: string | null
  coverageMonths: number
  totalMonthlyIncome: number
  /** Active, non-portfolio-yield streams only — the take-home headline. */
  activeMonthlyIncome: number
  sourceLabel: string
  streams: RetirementIncomeActualsStream[]
  aliasRowsCollapsed: number
}

export interface RetirementSpendingActuals {
  generatedAt: string
  firstMonth: string | null
  lastMonth: string | null
  coverageMonths: number
  totalMonthlySpend: number
  healthcareMonthly: number
  sourceLabel: string
  categories: RetirementSpendingActualsCategory[]
}

export interface RetirementSpendingActualsCategory {
  category: string
  essentiality: string
  monthlyAverage: number
  total: number
  transactionCount: number
}

export interface RetirementInputs {
  schemaVersion: number
  householdId: string
  primaryAge: number
  spouseAge: number | null
  retirementAge: number
  spouseRetirementAge?: number | null
  horizonYears: number
  annualExpenses: number
  annualContribution: number
  portfolioValue: number
  assetAllocation: Record<string, number>
  cashYield?: number | null
  incomeSources: Array<Record<string, unknown>>
  spendingReductions?: RetirementSpendingReduction[]
  liquidityEvents?: RetirementLiquidityEvent[]
  inflationRate: number
  socialSecurityPayableRatio: number
  socialSecurityDepletionYear: number | null
  collegeSchedule?: RetirementCollegeYear[]
  college529Value?: number
  /** Resolved ACA/Medicare stream config; absent when the stream is off. */
  aca?: RetirementAcaConfig | null
  asOfDate: string
}

export interface RetirementAccountBucket {
  bucketType: string
  label: string
  accountType: string
  taxTreatment: string
  currentValue: number
  withdrawalPriority: number
}

export interface RetirementHoldingsCoverageAccount {
  label: string
  bucketType: string
  accountType: string
  householdAccountId: string | null
  manualHoldingsEditable: boolean
  currentValue: number
  exactValue: number
  inferredValue: number
  cashValue: number
  pricedPositionCount: number
  coverageStatus: string
  coverageLabel: string
  detail: string
}

export interface HouseholdAccountHoldingPosition {
  symbol: string
  shares: number
  price: number | null
  value: number | null
}

export interface HouseholdAccountHoldings {
  householdAccountId: string
  label: string
  accountType: string
  positions: HouseholdAccountHoldingPosition[]
  pricedValue: number
}

export interface ManualHoldingEntryInput {
  symbol: string
  shares?: number
  percent?: number
}

export interface ManualHoldingsReplaceInput {
  entries: ManualHoldingEntryInput[]
  accountValue?: number
}

export interface RetirementHoldingsCoverage {
  status: string
  label: string
  detail: string
  totalValue: number
  exactValue: number
  inferredValue: number
  cashValue: number
  exactShare: number
  accounts: RetirementHoldingsCoverageAccount[]
}

export interface RetirementAccountAllocationAccount {
  label: string
  bucketType: string
  accountType: string
  currentValue: number
  exactValue: number
  inferredValue: number
  cashValue: number
  pricedPositionCount: number
  allocationStatus: string
  allocationLabel: string
  allocation: Record<string, number>
  detail: string
}

export interface RetirementAccountAllocationCoverage {
  status: string
  label: string
  detail: string
  totalValue: number
  exactValue: number
  inferredValue: number
  cashValue: number
  exactShare: number
  assetAllocation: Record<string, number>
  accounts: RetirementAccountAllocationAccount[]
}

export interface RetirementBucketStrategyHolding {
  symbol: string
  label: string
  assetClass: string
  currentValue: number
  shareOfBucket: number
  source: 'exact' | 'cash' | 'inferred'
  accountLabel: string | null
}

export interface RetirementBucketStrategyBucket {
  bucketId: 'now' | 'soon' | 'later'
  label: string
  timeHorizon: string
  purpose: string
  currentValue: number
  targetValue: number
  targetYears: number
  currentShare: number
  targetShare: number
  fillRatio: number
  gapValue: number
  status: 'underfilled' | 'aligned' | 'overfilled' | 'empty'
  statusLabel: string
  action: string
  assetAllocation: Record<string, number>
  holdings: RetirementBucketStrategyHolding[]
}

export interface RetirementBucketStrategy {
  strategyType: 'dynamic_three_bucket'
  label: string
  status: 'underfilled' | 'aligned' | 'overfilled' | 'empty'
  statusLabel: string
  detail: string
  yearsToRetirement: number
  retirementAge: number
  annualPortfolioNeed: number
  targetTotal: number
  currentTotal: number
  alignmentScore: number
  buckets: RetirementBucketStrategyBucket[]
  rebalanceActions: string[]
  methodology: string[]
  monteCarloDetail: string
}

export interface RetirementDrawdownYear {
  yearIndex: number
  calendarYear: number
  primaryAge: number
  spendingNeed: number
  income: number
  grossWithdrawal: number
  taxEstimate: number
  penaltyEstimate: number
  netWithdrawal: number
  endingBalance: number
  rmdAmount: number
  rmdApplied: boolean
  withdrawalsByBucket: Record<string, number>
  balancesByBucket: Record<string, number>
  // Floor-and-upside engine outputs in real (today's) dollars
  spendingTarget: number
  floorAmount: number
  discretionaryTarget: number
  spendingReduction: number
  guaranteedIncome: number
  bridgeDraw: number
  portfolioDraw: number
  bridgeBalance: number
  withdrawalRate: number
  collegeCost: number
  college529Draw: number
  college529Balance: number
  // ACA/Medicare healthcare stream (real dollars); subsidy is priced
  // off magi, the modeled MAGI that set the credit that year.
  acaPremiumGross: number
  acaSubsidy: number
  acaOop: number
  acaNet: number
  /** Planning-floor net before the MAGI true-up repriced the subsidy. */
  acaPlanningNet: number
  magi: number
  medicarePremium: number
  /** Primary retired, spouse still working: gap funded through the seam. */
  partialRetirementYear: boolean
  /** Spouse nominal take-home offsetting that year's spending. */
  spouseNetIncome: number
}

export interface RetirementLeverImpact {
  id: string
  label: string
  value: string
  successProbability: number
  deltaSuccessProbability: number
  detail: string
}

export interface RetirementAccountRule {
  bucketType: string
  label: string
  taxTreatment: string
  earlyAccess: string
  rmd: string
}

export interface RetirementHoldingIncomeYield {
  symbol: string
  weight: number
  incomeYield: number
  source: string
  taxCategory: string
  asOf: string | null
  freshnessStatus: string
  freshnessLabel: string
}

/**
 * Beyond-success-% framing. Dollar fields are real (today's dollars);
 * failure-depth and warning fields are null when no trial fails.
 */
export interface RetirementOutcomeFraming {
  medianYearsShort: number | null
  medianFloorGapReal: number | null
  tailFloorGapReal: number | null
  medianWarningYears: number | null
  penaltyTrialsShare: number
  medianPenaltyPaidReal: number | null
  endAboveStartShare: number
  startBalanceReal: number
}

export interface RetirementPreview {
  schemaVersion: number
  trustedTotals: boolean
  accountControlStatus: string
  accountControlSummary: string
  inputs: RetirementInputs
  successProbability: number
  medianEndingBalance: number
  sequenceOfReturnsRisk: number
  percentiles: Record<string, number>
  endingBalancePaths: Record<string, number[]>
  accountBuckets: RetirementAccountBucket[]
  holdingsCoverage: RetirementHoldingsCoverage | null
  accountAllocationCoverage: RetirementAccountAllocationCoverage | null
  bucketStrategy: RetirementBucketStrategy | null
  taxAssumptions: Record<string, unknown>
  returnAssumptions: Record<string, unknown>
  drawdownSchedule: RetirementDrawdownYear[]
  accountRules: RetirementAccountRule[]
  leverImpacts: RetirementLeverImpact[]
  firstDepletionAge: number | null
  medianDiscretionaryPath: number[]
  /** Monte Carlo failure counts keyed by primary age at first shortfall. */
  failureAgeDistribution: Record<string, number>
  outcomeFraming: RetirementOutcomeFraming | null
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
  createdAt: string
  updatedAt: string
}

export interface HouseholdTrackedAccountInput {
  householdAccountId?: string | null
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
  affects: string[]
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
  /** Linked purchase items; >0 enables the ledger row item expansion. */
  itemCount: number
  itemCategories: string[]
  flowType?: string | null
  direction: string
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
  originalCategory?: string | null
  categorizationSource?: string | null
  categorizationVersion?: string | null
  categoryUpdatedAt?: string | null
  categoryUpdatedBy?: string | null
  sourceSystem?: string | null
  externalTransactionId?: string | null
  pending?: boolean
  removed?: boolean
  transactionRuleId?: string | null
  datasetType?: string | null
  externalRowId?: string | null
  rowHash: string
  sourceDocumentId?: string | null
  sourceDocumentFilename?: string | null
  sourceType?: string | null
  documentType?: string | null
  balanceAfter?: number | null
  uploadedAt?: string | null
  includedInSpend: boolean
  exclusionReason?: string | null
}

export interface HouseholdLedger {
  generatedAt: string
  timeframeKey: string
  timeframeLabel: string
  startDate?: string | null
  endDate?: string | null
  transactionCount: number
  importRowCount: number
  totalEntryCount: number
  filteredCount: number
  includedCount: number
  excludedCount: number
  offset: number
  limit: number
  returnedCount: number
  accountOptions: string[]
  categoryOptions: string[]
  debitTotal: number
  creditTotal: number
  entries: HouseholdLedgerEntry[]
}

export interface HouseholdLedgerParams {
  window?: string
  kind?: string
  status?: string
  account?: string
  search?: string
  sort?: string
  sortDir?: string
  limit?: number
  offset?: number
}

export interface HouseholdSpendingCategory {
  category: string
  essentiality: string
  totalSpend: number
  averageMonthlySpend: number
  shareOfSpend: number
  transactionCount: number
  grossMonthlySpend?: number
  refundTotal?: number
  foundMonthlyBudget?: number | null
  confirmedMonthlyBudget?: number | null
  budgetSource?: string
  budgetStatus?: string
  budgetNote?: string | null
  budgetDisabled?: boolean
}

export interface HouseholdSpendingItemSplit {
  category: string
  essentiality: string
  amount: number
  itemCount: number
  ownerName?: string | null
}

export interface HouseholdSpendingTransaction {
  id: string
  /** Reconciled purchase-item splits behind this charge (Split badge). */
  itemCount?: number
  itemCategories?: string[]
  itemSplits?: HouseholdSpendingItemSplit[]
  /** Client-created when a budget drill-down shows one itemized category slice. */
  splitParentId?: string | null
  ownerName?: string | null
  ownerSource?: string | null
  date: string
  merchant: string
  description: string
  amount: number
  category: string
  essentiality: string
  originalCategory?: string | null
  categorizationSource?: string | null
  sourceSystem?: string | null
  externalTransactionId?: string | null
  pending?: boolean
  transactionRuleId?: string | null
  categoryConfidence?: number | null
  needsCategoryReview?: boolean
  accountLabel?: string | null
  sourceDocumentId?: string | null
  sourceKind?: string | null
  sourceType?: string | null
  documentType?: string | null
}

export interface HouseholdCategoryMonthlyTrendPoint {
  month: string
  category: string
  essentiality: string
  totalSpend: number
  transactionCount: number
}

export interface HouseholdSpendingSummary {
  timeframeKey: string
  timeframeLabel: string
  startDate?: string | null
  endDate?: string | null
  totalSpend: number
  averageMonthlySpend: number
  transactionCount: number
  coverageMonths: number
  accountCount: number
  grossSpend?: number
  refundTotal?: number
  totalIncome?: number
  averageMonthlyIncome?: number
  netCashFlow?: number
  savingsRate?: number | null
  monthToDateSpend?: number
  // The backend always serializes the budget rollup; the client never recomputes it.
  foundBudgetTotal: number
  confirmedBudgetTotal: number
  budgetedCategoryCount: number
  foundBudgetCategoryCount: number
  confirmedBudgetCategoryCount: number
  overBudgetCount: number
  foundOverBudgetCount: number
  confirmedOverBudgetCount: number
}

export interface HouseholdSpendingView {
  generatedAt: string
  summary: HouseholdSpendingSummary
  categories: HouseholdSpendingCategory[]
  monthlyTrend: HouseholdMonthlyTrendPoint[]
  categoryMonthlyTrend: HouseholdCategoryMonthlyTrendPoint[]
  transactions: HouseholdSpendingTransaction[]
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
  accountControl: HouseholdAccountControl
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
  planning?: import('../household-planning').HouseholdPlanningSnapshot | null
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
  targetSpouseRetirementAge?: number | null
  targetRetirementSpend?: number | null
  retirementInflationRate?: number | null
  retirementHorizonYears?: number | null
  primarySocialSecurityMonthly?: number | null
  spouseSocialSecurityMonthly?: number | null
  primarySocialSecurityAnnualEarnings?: number | null
  spouseSocialSecurityAnnualEarnings?: number | null
  primarySocialSecurityStartAge?: number | null
  spouseSocialSecurityStartAge?: number | null
  socialSecurityPayableRatio?: number | null
  filingStatus?: string | null
  stateOfResidence?: string | null
  effectiveTaxRate?: number | null
  marginalFederalTaxRate?: number | null
  marginalStateTaxRate?: number | null
  emergencyFundTargetMonths?: number | null
  emergencyFundTargetAmount?: number | null
  withdrawalStrategy?: string | null
  withdrawalInitialRate?: number | null
  withdrawalDeclineMode?: string | null
  discretionaryDeclineRate?: number | null
  phaseSlowGoAge?: number | null
  phaseNoGoAge?: number | null
  phaseGoGoPct?: number | null
  phaseSlowGoPct?: number | null
  phaseNoGoPct?: number | null
  bridgeMode?: string | null
  bridgeManualAmount?: number | null
  bridgeRealReturn?: number | null
  bridgeGrowth?: 'fixed' | 'portfolio' | null
  retirementEssentialFloorOverride?: number | null
  retirementDiscretionaryOverride?: number | null
  acaTier?: 'silver' | 'bronze' | 'none' | null
  acaPremiumAge21Override?: number | null
  acaOopMonthly?: number | null
  medicareMonthlyPerPerson?: number | null
  spouseNetMonthlyIncome?: number | null
  partialRetirementMonthlySpend?: number | null
  spouseGrossAnnualIncome?: number | null
  notes?: string | null
}

export interface HouseholdDocumentUpload {
  file?: File
  rawText?: string
  filename?: string
  sourceType?: string
  documentType?: string
  accountLabel?: string
  householdAccountId?: string
  reviewSessionId?: string
}

export interface HouseholdQuestionAnswer {
  answerText: string
}

export interface HouseholdTransactionCategoryUpdate {
  category: string
  essentiality: string
  applyToMerchant?: boolean
}

// --- Item-level purchase tracking (Purchases tab) ---
// Wire keys are digit-free end to end; see backend household_finance_types.

export interface HouseholdPurchaseItem {
  id: string
  transactionId?: string | null
  productId?: string | null
  productName?: string | null
  productMatchStatus: string
  productMatchConfidence?: number | null
  purchaseDate?: string | null
  merchant?: string | null
  description: string
  quantity?: number | null
  unitPrice?: number | null
  amount: number
  allocatedAmount?: number | null
  category: string
  essentiality: string
  categorizationSource: string
  ownerName?: string | null
  ownerSource: string
}

export interface HouseholdProductPricePoint {
  observedDate: string
  merchant?: string | null
  totalPrice: number
  quantity?: number | null
  unitPrice?: number | null
  source: string
}

export interface HouseholdProductSummary {
  id: string
  canonicalName: string
  brand?: string | null
  packageDisplayLabel?: string | null
  imageUrl?: string | null
  purchaseCount: number
  observationCount: number
  needsReviewCount: number
  firstObservedDate?: string | null
  lastObservedDate?: string | null
  latestPrice?: number | null
  latestUnitPrice?: number | null
  latestMerchant?: string | null
  bestResearchedVendorKey?: string | null
  bestResearchedVendor?: string | null
  bestResearchedTotalPrice?: number | null
  bestResearchedUnitPrice?: number | null
  bestResearchedUnitLabel?: string | null
  bestResearchedPackageLabel?: string | null
  bestResearchedObservedDate?: string | null
  bestResearchedConfidence?: number | null
  bestResearchedUrl?: string | null
  bestResearchedSource?: string | null
  catalogStatus: 'active' | 'archived'
  ownerItemId?: string | null
  ownerName?: string | null
  ownerSource: string
  pricePoints: HouseholdProductPricePoint[]
}

export interface HouseholdProductList {
  generatedAt: string
  totalCount: number
  needsReviewTotal: number
  offset: number
  limit: number
  returnedCount: number
  products: HouseholdProductSummary[]
}

export interface HouseholdProductIdentifier {
  kind: string
  value: string
}

export interface HouseholdProductDetail {
  generatedAt: string
  product: HouseholdProductSummary
  identifiers: HouseholdProductIdentifier[]
  observations: HouseholdProductPricePoint[]
  recentItems: HouseholdPurchaseItem[]
}

export interface HouseholdPurchaseItemReviewQueue {
  generatedAt: string
  totalCount: number
  items: HouseholdPurchaseItem[]
}

export interface HouseholdProductListParams {
  search?: string
  sort?:
    | 'recent'
    | 'frequency'
    | 'name'
    | 'price'
    | 'unit_price'
    | 'owner'
    | 'review'
  sortDir?: 'asc' | 'desc'
  scope?: 'active' | 'archived' | 'all'
  limit?: number
  offset?: number
}

export interface HouseholdPurchaseItemCategoryUpdate {
  category: string
  essentiality: string
  applyToProduct?: boolean
}

export interface HouseholdPurchaseItemOwnerUpdate {
  ownerName?: string | null
  applyToProduct?: boolean
}

export interface HouseholdPurchaseItemProductAssignment {
  action: 'confirm' | 'reassign' | 'detach'
  productId?: string | null
}

export interface HouseholdPriceCheckVendorStatus {
  vendorKey: string
  status: 'ok' | 'blocked' | 'error' | 'skipped'
  quoteCount: number
  error?: string | null
}

export interface HouseholdPriceCheckRun {
  id: string
  status:
    | 'queued'
    | 'running'
    | 'completed'
    | 'completed_with_errors'
    | 'failed'
  triggeredBy: string
  productCount: number
  quoteCount: number
  findingCount: number
  error?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  vendors: HouseholdPriceCheckVendorStatus[]
}

export interface HouseholdPriceFinding {
  id: string
  kind: 'cheaper_elsewhere' | 'savings_rollup'
  status: string
  productId?: string | null
  productName?: string | null
  vendorKey?: string | null
  savingsEstimate?: number | null
  householdPrice?: number | null
  vendorPrice?: number | null
  unitLabel?: string | null
  comparisonQuantity?: number | null
  householdPackageLabel?: string | null
  householdEquivalentTotal?: number | null
  vendorTotalPrice?: number | null
  vendorEquivalentTotal?: number | null
  vendorUrl?: string | null
  vendorTitle?: string | null
  vendorPackageLabel?: string | null
  vendorPromoText?: string | null
  detail?: string | null
  createdAt?: string | null
}

export interface HouseholdPriceCheckStatus {
  generatedAt: string
  latestRun?: HouseholdPriceCheckRun | null
  openFindings: HouseholdPriceFinding[]
}

export interface HouseholdPriceCheckTriggerResponse {
  runId: string
  alreadyRunning: boolean
}

export interface HouseholdBuyGuideTrendPoint {
  observedDate: string
  merchant?: string | null
  packageLabel?: string | null
  totalPrice: number
  unitCost: number
  source: string
}

export interface HouseholdBuyGuideItem {
  productId: string
  productName: string
  brand?: string | null
  purchaseCount: number
  unitLabel: string
  currentMerchant?: string | null
  currentPackageLabel?: string | null
  currentTotalPrice: number
  currentUnitCost: number
  currentObservedDate: string
  bestMerchant?: string | null
  bestPackageLabel?: string | null
  bestTotalPrice: number
  bestUnitCost: number
  bestSource: string
  bestObservedDate: string
  bestUrl?: string | null
  bestTitle?: string | null
  savingsPerUnit: number
  savingsPct: number
  estimatedMonthlySavings?: number | null
  monthsToUse?: number | null
  findingKind: string
  recommendation: string
  confidence: number
  confidenceReasons: string[]
  trendPoints: HouseholdBuyGuideTrendPoint[]
}

export interface HouseholdBuyGuide {
  generatedAt: string
  totalCandidates: number
  returnedCount: number
  unitCoverageCount: number
  items: HouseholdBuyGuideItem[]
}

export interface HouseholdShoppingListItem {
  id?: string | null
  productId?: string | null
  productName?: string | null
  freeText?: string | null
  quantity?: number | null
  unit?: string | null
  status: string
  position: number
  matchConfidence?: number | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface HouseholdShoppingList {
  id: string
  name: string
  status: string
  items: HouseholdShoppingListItem[]
  latestOptimization?: Record<string, unknown> | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface HouseholdShoppingListsResponse {
  generatedAt: string
  lists: HouseholdShoppingList[]
}

export interface HouseholdShoppingListSuggestionItem {
  productId: string
  productName: string
  purchaseCount: number
  firstPurchaseDate?: string | null
  lastPurchaseDate?: string | null
  medianGapDays?: number | null
  nextDueDate?: string | null
  daysUntilDue?: number | null
  dueBucket: 'buy_now' | 'soon' | 'watch'
  confidence: number
  reason: string
  latestCategory?: string | null
  latestMerchant?: string | null
  latestPrice?: number | null
  packageLabel?: string | null
  unitLabel?: string | null
  alreadyOnOpenList: boolean
  selectedByDefault: boolean
}

export interface HouseholdShoppingListSuggestions {
  generatedAt: string
  lookbackDays: number
  daysAhead: number
  watchDays: number
  itemCount: number
  buyNowCount: number
  soonCount: number
  watchCount: number
  items: HouseholdShoppingListSuggestionItem[]
}

export interface HouseholdShoppingListRequest {
  name: string
  status?: string
  items?: HouseholdShoppingListItem[] | null
}

export interface HouseholdShoppingListOptimizeRequest {
  maxLocalStores?: number | null
}

export interface HouseholdShoppingListImportRequest {
  text: string
  replace?: boolean
}

export interface HouseholdShoppingListImportResponse {
  shoppingList: HouseholdShoppingList
  parsedCount: number
  matchedCount: number
}

export interface HouseholdVendorProfile {
  vendorKey: string
  displayName: string
  enabled: boolean
  deliveryFee?: number | null
  pickupFee?: number | null
  freeDeliveryThreshold?: number | null
  membershipMonthlyFee?: number | null
  membershipActive: boolean
}

export interface HouseholdVendorProfileList {
  generatedAt: string
  vendors: HouseholdVendorProfile[]
}

export interface HouseholdVendorProfileUpdate {
  vendors: HouseholdVendorProfile[]
}
