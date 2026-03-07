/**
 * Paper Trading API client functions
 */

import { apiRequest } from './client'

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface PaperTrade {
  ideaId: string
  agentRunId: string
  symbol: string
  ideaType: 'buy' | 'sell'
  shares?: number
  entryPrice?: number
  entryAmount?: number
  entryDate?: string
  targetPrice?: number
  stopLossPrice?: number
  currentPrice?: number
  currentReturnPct?: number
  status: string
  exitPrice?: number
  exitDate?: string
  exitReason?: string
  realizedReturnPct?: number
  holdingDays?: number
  maxFavorablePct?: number
  maxAdversePct?: number
  // AI reasoning fields
  thesis?: string
  confidenceScore?: number
  riskLevel?: string
  // Agent approval details
  workflowId?: string
  strategyAgentApproved?: boolean
  riskAgentApproved?: boolean
  backtestSharpe?: number
  backtestWinRate?: number
  backtestMaxDrawdown?: number
}

export interface PaperTradesListResponse {
  trades: PaperTrade[]
  totalCount: number
}

export interface PaperTradeSummary {
  totalOpen: number
  totalClosed: number
  winRate: number
  avgReturnPct: number
  totalPnlPct: number
  bestTradePct?: number
  worstTradePct?: number
  // Paper trading account balances
  cashBalance?: number
  startingBalance?: number
  positionsValue?: number
  totalPortfolioValue?: number
}

export interface CloseTradeRequest {
  exitPrice?: number
  exitReason?: string
}

export interface CloseTradeResponse {
  status: string
  tradeId: string
  symbol: string
  exitPrice: number
  exitDate: string
  realizedReturnPct: number
  message: string
}

export interface CreateTradeRequest {
  symbol: string
  action: 'buy'
  thesis: string
  targetPrice?: number
  stopLossPct?: number
}

export interface CreateTradeResponse {
  status: string
  tradeId?: string
  symbol?: string
  action?: string
  shares?: number
  entryPrice?: number
  entryAmount?: number
  targetPrice?: number
  stopLossPrice?: number
  cashRemaining?: number
  message: string
  error?: string
}

export interface ResetAccountRequest {
  newStartingBalance?: number
  closeOpenTrades?: boolean
}

export interface ResetAccountResponse {
  status: string
  previousBalance: number
  newBalance: number
  tradesClosed: number
  message: string
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Create a manual paper trade
 */
export async function createPaperTrade(
  request: CreateTradeRequest,
): Promise<CreateTradeResponse> {
  return apiRequest<CreateTradeResponse>('/api/paper-trading/trades', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

/**
 * Fetch all paper trades with optional status filter
 */
export async function fetchPaperTrades(params?: {
  status?: 'open' | 'closed' | 'all'
  limit?: number
  offset?: number
}): Promise<PaperTradesListResponse> {
  const queryParams = new URLSearchParams()
  if (params?.status) queryParams.append('status', params.status)
  if (params?.limit) queryParams.append('limit', String(params.limit))
  if (params?.offset) queryParams.append('offset', String(params.offset))

  const url = `/api/paper-trades${queryParams.toString() ? `?${queryParams}` : ''}`
  return apiRequest<PaperTradesListResponse>(url)
}

/**
 * Fetch paper trading summary statistics
 */
export async function fetchPaperTradeSummary(): Promise<PaperTradeSummary> {
  return apiRequest<PaperTradeSummary>('/api/paper-trades/summary')
}

/**
 * Fetch a single paper trade by ID
 */
export async function fetchPaperTrade(tradeId: string): Promise<PaperTrade> {
  return apiRequest<PaperTrade>(`/api/paper-trades/${tradeId}`)
}

/**
 * Close a paper trade manually
 */
export async function closePaperTrade(
  tradeId: string,
  request: CloseTradeRequest,
): Promise<CloseTradeResponse> {
  return apiRequest<CloseTradeResponse>(`/api/paper-trades/${tradeId}/close`, {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

/**
 * Reset paper trading account to starting balance
 */
export async function resetPaperAccount(
  request: ResetAccountRequest = {},
): Promise<ResetAccountResponse> {
  return apiRequest<ResetAccountResponse>('/api/paper-trades/account/reset', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}
