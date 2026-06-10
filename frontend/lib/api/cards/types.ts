/**
 * TypeScript mirrors of backend/app/models/credit_cards.py (camelCase — the
 * shared API client converts snake_case responses automatically).
 */

export interface CardCredit {
  name: string
  annualValue: number
  /** How easy the credit is to realize: easy | moderate | hard. */
  type: string
}

export interface CreditCardProduct {
  id: string
  slug: string
  issuer: string
  network?: string | null
  productName: string
  cardKind: string
  annualFee: number
  /** Keyed by canonical reward bucket (dining, travel, groceries, gas, other…). */
  rewardMultipliers: Record<string, number>
  pointProgram?: string | null
  estPointValueCents?: number | null
  welcomeBonusPoints: number
  welcomeBonusCash: number
  welcomeMinSpend?: number | null
  welcomeWindowDays?: number | null
  transferPartners: string[]
  credits: CardCredit[]
  issuerRules: Record<string, unknown>
  source: string
  sourceDocumentId?: string | null
  lastVerifiedAt?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

export interface HouseholdCreditCard {
  id: string
  productId: string
  householdAccountId?: string | null
  status: string
  isPrimaryActive: boolean
  /** Which household member holds the card: p1 | p2. */
  player: string
  /** rotating = participates in the 90-day rotation; keeper = held permanently. */
  role: string
  openedDate?: string | null
  closedDate?: string | null
  annualFeeDueDate?: string | null
  welcomeProgressAmount: number
  welcomeDeadline?: string | null
  welcomeStatus: string
  notes?: string | null
  metadata: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
  product?: CreditCardProduct | null
}

export interface SoftCharge {
  id: string
  householdAccountId?: string | null
  amount: number
  description: string
  merchant?: string | null
  category?: string | null
  essentiality?: string | null
  occurredAt: string
  sourceDocumentId?: string | null
  status: string
  matchedPlaidTransactionId?: string | null
  matchedAt?: string | null
  matchConfidence?: number | null
  matchMethod?: string | null
  ledgerTransactionId?: string | null
  metadata: Record<string, unknown>
  createdAt?: string | null
  updatedAt?: string | null
}

export interface SpendProfile {
  monthlyTotal: number
  byBucket: Record<string, number>
  source: string
}

export interface CategoryContribution {
  bucket: string
  monthlySpend: number
  multiplier: number
  pointValueCents: number
  annualValue: number
}

export interface CardRewardEstimate {
  productId: string
  slug: string
  issuer: string
  productName: string
  cardKind: string
  annualFee: number
  assumedPointValueCents: number
  earnValue: number
  creditsValue: number
  annualValue: number
  welcomeValue: number
  welcomeReachable: boolean
  firstYearValue: number
  amortizationYears: number
  steadyStateValue: number
  categoryContributions: CategoryContribution[]
  warnings: string[]
}

export interface CardRanking {
  spendProfile: SpendProfile
  valuationStance: string
  amortizationYears: number
  byFirstYear: CardRewardEstimate[]
  bySteadyState: CardRewardEstimate[]
  assumptions: string[]
  disclaimer: string
}

export interface RotationStepView {
  sequenceIndex: number
  quarterStart?: string | null
  quarterLabel: string
  productId?: string | null
  productSlug?: string | null
  productName?: string | null
  issuer?: string | null
  householdCreditCardId?: string | null
  player?: string | null
  action: string
  targetSpend: number
  projectedWelcomeValue: number
  projectedEarnValue: number
  projectedValue: number
  ruleWarnings: string[]
}

export interface RotationCumulativePoint {
  quarterIndex: number
  quarterLabel: string
  rotationCumulativeValue: number
  baselineCumulativeValue: number
}

export interface RotationPlanView {
  planId?: string | null
  name: string
  objective: string
  horizonQuarters: number
  spendProfile: SpendProfile
  steps: RotationStepView[]
  projectedTotalValue: number
  baselineSingleCardValue: number
  baselineProductSlug?: string | null
  uplift: number
  cumulativeValue: RotationCumulativePoint[]
  warnings: string[]
  assumptions: string[]
  disclaimer: string
}

export type ValuationStance = 'conservative' | 'balanced' | 'optimistic'
export type CreditStance = 'easy_only' | 'balanced' | 'face_value'

export interface RankingRequest {
  monthlyTotal?: number | null
  byBucket?: Record<string, number> | null
  valuationStance: ValuationStance
  amortizationYears: number
  includeOwnedOnly?: boolean
  creditStance: CreditStance
}

export interface RotationRequest {
  objective?: string
  horizonQuarters: number
  valuationStance?: ValuationStance
  creditStance?: CreditStance
  players: string[]
  name?: string | null
  persist?: boolean
}

export interface CreditCardCreate {
  productId: string
  status?: string
  householdAccountId?: string | null
  player: string
  role: string
  openedDate?: string | null
  welcomeDeadline?: string | null
  notes?: string | null
}

export interface CreditCardUpdate {
  status?: string | null
  householdAccountId?: string | null
  player?: string | null
  role?: string | null
  openedDate?: string | null
  closedDate?: string | null
  annualFeeDueDate?: string | null
  welcomeProgressAmount?: number | null
  welcomeDeadline?: string | null
  welcomeStatus?: string | null
  notes?: string | null
}

export interface CardIntakeResult {
  documentId: string
  /** extracted | needs_review | failed */
  status: string
  product?: CreditCardProduct | null
  confidence?: number | null
  unreadableFields: string[]
  extractionNotes?: string | null
}

export interface CardMaterialChange {
  headline?: string
  detail?: string
  severity?: string
}

export interface CatalogResearchResult {
  updatesApplied: number
  candidatesAdded: number
  materialChanges: CardMaterialChange[]
  researchNotes: string
}

export interface SoftChargeCreate {
  amount: number
  description: string
  merchant?: string
  category?: string
  essentiality?: string
  occurredAt?: string
  householdAccountId?: string
  receipt?: File | null
}
