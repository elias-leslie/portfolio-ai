import { get, post } from './client'

export type StrategyLabAction = 'buy_now' | 'buy_in_stages' | 'hold' | 'wait'
export type StrategyLabTemplate =
  | 'pullback_accumulator'
  | 'breakout_confirmation'
export type StrategyLabBacktestStatus =
  | 'ready'
  | 'insufficient_history'
  | 'no_trades'
  | 'quote_unavailable'
export type StrategyLabUnavailableReason =
  | 'insufficient_history'
  | 'evaluation_error'
export type StrategyLabSignalStatus =
  | 'valid'
  | 'better_entry'
  | 'caution'
  | 'invalidated'
export type StrategyLabValidation = 'thesis' | 'backtest' | 'both'
export type StrategyLabDecisionAction =
  | 'act_now'
  | 'stage'
  | 'dismiss'
  | 'snooze'

export interface StrategyLabRiskFrame {
  entryPrice: number
  currentPrice: number
  priceChangePct: number
  stopLoss: number
  targetPrice: number
  riskRewardRatio: number
}

export interface StrategyLabSignalSnapshot {
  strategyId: string
  strategyName: string
  strategyType: string
  signalStrength: number
  signalStatus: StrategyLabSignalStatus
  signalReasons: string[]
  signalDate: string
  expectedSharpe: number | null
  validationType: StrategyLabValidation
  risk: StrategyLabRiskFrame
  suggestedSizeDollars: number
  suggestedSizeShares: number
}

export interface StrategyLabDiscoveryItem {
  symbol: string
  strategyName: string
  strategyType: string
  signalStrength: number
  signalStatus: StrategyLabSignalStatus
  validationType: StrategyLabValidation
  expectedSharpe: number | null
  risk: StrategyLabRiskFrame
  backtestSnapshot?: StrategyLabBacktestSnapshot | null
}

export interface StrategyLabDecisionRequest {
  action: StrategyLabDecisionAction
  note?: string | null
}

export interface StrategyLabDecisionResponse {
  symbol: string
  action: StrategyLabDecisionAction
  recordedAt: string
  workflowStage: string | null
  notificationId: string | null
  summary: string
  nextStep: string | null
}

export interface StrategyLabPrimaryAccountTarget {
  accountId: string
  accountName: string
  accountType: string
  cashBalance: number
  heldMarketValue: number | null
}

export interface StrategyLabTicket {
  accountId: string
  accountName: string
  action: StrategyLabAction
  dollars: number
  estimatedShares: number
  firstTrancheDollars: number
  helperText: string | null
}

export interface StrategyLabBacktestPoint {
  date: string
  equity: number
}

export interface StrategyLabBacktestSnapshot {
  status: StrategyLabBacktestStatus
  lookbackDays: number | null
  requestedStartDate: string | null
  requestedEndDate: string | null
  availableStartDate: string | null
  availableEndDate: string | null
  totalReturnPct: number | null
  buyHoldReturnPct: number | null
  excessReturnPct: number | null
  maxDrawdownPct: number | null
  tradeCount: number
  equityCurve: StrategyLabBacktestPoint[]
  buyHoldCurve: StrategyLabBacktestPoint[]
  helperText: string | null
}

export interface StrategyLabReviewCapability {
  available: boolean
  message: string | null
}

export interface StrategyLabBaseEvaluation {
  symbol: string
  action: StrategyLabAction
  strategyTemplate: StrategyLabTemplate
  primaryAccountTarget: StrategyLabPrimaryAccountTarget | null
  updatedAt: string
  helperText: string | null
  signal: StrategyLabSignalSnapshot | null
}

export interface StrategyLabListItem extends StrategyLabBaseEvaluation {
  backtestStatus: StrategyLabBacktestStatus | null
  backtestHelperText: string | null
  backtestLookbackDays: number | null
}

export interface StrategyLabUnavailableItem {
  symbol: string
  reason: StrategyLabUnavailableReason
  message: string
  requestedStartDate: string | null
  requestedEndDate: string | null
  availableStartDate: string | null
  availableEndDate: string | null
  lookbackDays: number | null
}

export interface StrategyLabListResponse {
  items: StrategyLabListItem[]
  unavailableItems: StrategyLabUnavailableItem[]
  discoveries: StrategyLabDiscoveryItem[]
  totalCount: number
}

export interface StrategyLabDetail extends StrategyLabBaseEvaluation {
  whyBullets: string[]
  watchItem: string
  ticket: StrategyLabTicket | null
  backtestSnapshot: StrategyLabBacktestSnapshot
  review: StrategyLabReviewCapability
}

export interface StrategyLabReviewSuccess {
  verdict: string
  summary: string
  tailwinds: string[]
  headwinds: string[]
  invalidationTriggers: string[]
  actNowOrWait: string
  generatedAt: string
}

export interface StrategyLabReviewError {
  status: 'unavailable' | 'timeout' | 'stale_quote'
  message: string
}

export async function fetchStrategyLabList(): Promise<StrategyLabListResponse> {
  return get<StrategyLabListResponse>('/api/strategy-lab')
}

export async function fetchStrategyLabDetail(
  symbol: string,
): Promise<StrategyLabDetail> {
  return get<StrategyLabDetail>(
    `/api/strategy-lab/${encodeURIComponent(symbol)}`,
  )
}

export async function reviewStrategyLabSymbol(
  symbol: string,
): Promise<StrategyLabReviewSuccess | StrategyLabReviewError> {
  return post<StrategyLabReviewSuccess | StrategyLabReviewError>(
    `/api/strategy-lab/${encodeURIComponent(symbol)}/review`,
  )
}

export async function decideStrategyLabSymbol(
  symbol: string,
  payload: StrategyLabDecisionRequest,
): Promise<StrategyLabDecisionResponse> {
  return post<StrategyLabDecisionResponse>(
    `/api/strategy-lab/${encodeURIComponent(symbol)}/decision`,
    payload,
  )
}
