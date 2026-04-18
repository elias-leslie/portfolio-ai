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
  totalReturnPct: number | null
  buyHoldReturnPct: number | null
  excessReturnPct: number | null
  maxDrawdownPct: number | null
  tradeCount: number
  equityCurve: StrategyLabBacktestPoint[]
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
}

export interface StrategyLabListItem extends StrategyLabBaseEvaluation {}

export interface StrategyLabListResponse {
  items: StrategyLabListItem[]
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
