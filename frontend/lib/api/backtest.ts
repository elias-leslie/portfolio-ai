/**
 * Backtesting API client functions
 */

import { apiRequest, del, post } from './client'

// ============================================================================
// Types (matching backend Pydantic models)
// ============================================================================

export interface BacktestRun {
  id: string
  symbol: string
  strategyName: string
  startDate: string
  endDate: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
  initialCapital: string | number
  finalEquity: string | number | null
  totalReturnPct: string | number | null
  sharpeRatio: string | number | null
  maxDrawdownPct: string | number | null
  winRate: string | number | null
  numTrades: number | null
  profitFactor: string | number | null
  errorMessage?: string | null
  completedAt?: string | null
}

export interface BacktestTrade {
  id: string
  runId: string
  symbol: string
  entryDate: string
  entryPrice: string | number
  exitDate: string | null
  exitPrice: string | number | null
  shares: number
  pnl: string | number | null
  pnlPct: string | number | null
  exitReason: 'target' | 'stop' | 'signal' | 'time' | 'eod' | null
  maxFavorablePct: string | number
  maxAdversePct: string | number
  createdAt: string
}

export interface BacktestEquity {
  id: string
  runId: string
  date: string
  equity: string | number
  cash: string | number
  positionValue: string | number
  drawdownPct: string | number
  cumulativeReturnPct: string | number
  createdAt: string
}

export interface BacktestResult {
  run: BacktestRun
  trades: BacktestTrade[]
  equityCurve: BacktestEquity[]
  avgWin?: string | number | null
  avgLoss?: string | number | null
  winLossRatio?: string | number | null
  numWins?: number
  numLosses?: number
  totalDays?: number
}

export interface StrategyParameters {
  stopLossAtrMultiplier?: number
  maxHoldingDays?: number
  targetProfitPct?: number
  minConfirmations?: number
}

export interface StartBacktestRequest {
  symbol: string
  strategy: string
  startDate: string
  endDate: string
  parameters?: StrategyParameters
}

export interface StartBacktestResponse {
  runId: string
  taskId: string
  status: 'running'
  message: string
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Fetch all backtest runs
 */
export async function fetchBacktestRuns(): Promise<BacktestRun[]> {
  return apiRequest<BacktestRun[]>('/api/backtest/runs')
}

/**
 * Fetch a single backtest run details
 */
export async function fetchBacktestRun(runId: string): Promise<BacktestResult> {
  return apiRequest<BacktestResult>(`/api/backtest/runs/${runId}`)
}

/**
 * Fetch equity curve data for a backtest run
 */
export async function fetchBacktestEquity(
  runId: string,
): Promise<BacktestEquity[]> {
  return apiRequest<BacktestEquity[]>(`/api/backtest/runs/${runId}/equity`)
}

/**
 * Start a new backtest
 */
export async function startBacktest(
  request: StartBacktestRequest,
): Promise<StartBacktestResponse> {
  return post<StartBacktestResponse>('/api/backtest/run', request)
}

/**
 * Delete a backtest run
 */
export async function deleteBacktestRun(
  runId: string,
): Promise<{ message: string }> {
  return del<{ message: string }>(`/api/backtest/runs/${runId}`)
}
