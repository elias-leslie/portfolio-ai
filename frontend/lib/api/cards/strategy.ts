import { get, post, put } from '../client'

export interface StrategySettings {
  remindersEnabled: boolean
  automaticResearch: boolean
  reserveAmazon: boolean
  reserveCostco: boolean
  reserveGas: boolean
  monthlyCap: number | null
  costcoMonthly: number | null
}
export interface StrategyBaseline {
  monthlyAvailable: number
  historicalMonthly: number
  months: { month: string; ordinaryCardSpend: number; reservedSpend: number }[]
  incomeMonthly: number | null
  incomeSource: string
  freeCash: number | null
  cashStatus: string
  reservations: string[]
  warnings: string[]
}
export interface CardCandidate {
  key: string
  productId: string
  productName: string
  player: string
  applicant: string
  applicationOn: string
  applicationBy: string
  minimumSpend: number
  windowDays: number
  bonusValue: number
  annualFee: number
  incrementalValue: number
  monthlyRequired: number
  termsFingerprint: string
  termsCurrent: boolean
  sourceUrls: string[]
  checks: string[]
  rationale: string
}
export type BillPaymentPreference =
  | 'automatic'
  | 'keep_current'
  | 'consider_card'
export interface BillSuggestion {
  key: string
  merchant: string
  amount: number
  cadence: string
  nextExpected: string | null
  currentAccount: string | null
  alreadyCardSpend: boolean
  evidence: string
  status:
    | 'suggested'
    | 'confirmed'
    | 'observed'
    | 'skipped'
    | 'already_on_card'
    | 'kept_in_place'
  paidFromCma: boolean
  paymentPreference: BillPaymentPreference
  keepCurrentPayment: boolean
  paymentReason: string | null
  feePerCharge: number | null
  lostDiscount: number | null
  firstChargeDueOn: string | null
  observedOn: string | null
  observationId: string | null
}
export interface BonusTrack {
  cardId: string
  label: string
  applicant: string
  deadline: string | null
  required: number | null
  posted: number
  pending: number
  remaining: number | null
  daysLeft: number | null
  forecast: number | null
  status: string
  explanation: string
}
export interface SavedStrategy {
  id: string
  fingerprint: string
  status: string
  actualCardId: string | null
  createdAt: string
  approvedAt: string | null
  eligibilityConfirmed: boolean
  snapshot: {
    baseline: StrategyBaseline
    candidate: CardCandidate | null
    bills: BillSuggestion[]
    settings: StrategySettings
    recommendation: string
  }
}
export interface StrategyView {
  asOf: string
  settings: StrategySettings
  baseline: StrategyBaseline
  candidates: CardCandidate[]
  recommendation: string
  active: SavedStrategy | null
  draft: SavedStrategy | null
  history: SavedStrategy[]
  progress: BonusTrack[]
  bills: BillSuggestion[]
  changes: string[]
  reviewEvents: { id: string; title: string; date: string; detail: string }[]
}
export interface StrategyDecision {
  fingerprint: string
  action: 'approve' | 'pause' | 'resume' | 'link_card'
  eligibilityConfirmed?: boolean
  cashFlowConfirmed?: boolean
  cardId?: string
}
export interface BillDecision {
  status: 'confirmed' | 'skipped' | 'reset'
  cardAccepted?: boolean
  benefitsChecked?: boolean
  feePerCharge?: number | null
  lostDiscount?: number | null
  confirmedOn?: string | null
}
const base = '/api/household/cards/strategy'
export const fetchStrategy = (signal?: AbortSignal) =>
  get<StrategyView>(base, { signal })
export const proposeStrategy = (candidateKey?: string, wait = false) =>
  post<SavedStrategy>(base + '/plans', { candidateKey, wait })
export const decideStrategy = (id: string, decision: StrategyDecision) =>
  post<SavedStrategy>(base + '/plans/' + id, decision)
export const saveStrategySettings = (settings: StrategySettings) =>
  put<StrategySettings>(base + '/settings', settings)
export const saveBillPaymentPreference = (
  key: string,
  preference: BillPaymentPreference,
) =>
  put<void>(base + '/bills/' + encodeURIComponent(key) + '/preference', {
    preference,
  })
export const decideBillMove = (
  id: string,
  key: string,
  decision: BillDecision,
) =>
  put<void>(
    base + '/plans/' + id + '/bills/' + encodeURIComponent(key),
    decision,
  )
