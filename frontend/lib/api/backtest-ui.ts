/**
 * Backtesting UI API client functions
 *
 * Note: Core backtest functionality is in backtest.ts
 * This module adds UI-specific functions like comparison
 */

import { apiRequest } from './client'

// Re-export core backtest types and functions
export type {
  BacktestEquity,
  BacktestResult,
  BacktestRun,
  BacktestTrade,
  StartBacktestRequest,
  StartBacktestResponse,
} from './backtest'

export {
  deleteBacktestRun,
  fetchBacktestEquity,
  fetchBacktestRun,
  fetchBacktestRuns,
  startBacktest,
} from './backtest'

// ============================================================================
// Additional Types for UI
// ============================================================================

export interface NormalizedEquityPoint {
  date: string
  cumulativeReturnPct: string // Decimal as string
}

export interface RunMetrics {
  runId: string
  symbol: string
  strategyName: string
  startDate: string
  endDate: string
  totalReturnPct: string | null
  sharpeRatio: string | null
  maxDrawdownPct: string | null
  winRate: string | null
  numTrades: number | null
  profitFactor: string | null
  returnRank: number | null
  sharpeRank: number | null
  drawdownRank: number | null
}

export interface BacktestComparisonResponse {
  equityCurves: Record<string, NormalizedEquityPoint[]>
  metrics: RunMetrics[]
  correlationMatrix: Record<string, Record<string, number>> | null
}

export interface MonteCarloStatistics {
  numSimulations: number
  percentile5: number
  percentile25: number
  percentile50: number
  percentile75: number
  percentile95: number
  probabilityOfLoss: number
  valueAtRisk95: number
  expectedShortfall: number
  meanReturn: number
  stdDev: number
  skewness: number
  kurtosis: number
  originalReturn: number
}

export interface HistogramBin {
  binStart: number
  binEnd: number
  frequency: number
}

export interface EquityBand {
  step: number
  p5: number
  p50: number
  p95: number
}

export interface MonteCarloRequest {
  numSimulations?: number
  seed?: number
}

export interface MonteCarloResponse {
  statistics: MonteCarloStatistics
  histogramData: HistogramBin[]
  equityBands: EquityBand[]
  createdAt: string
}

// ============================================================================
// UI-Specific API Functions
// ============================================================================

/**
 * Compare multiple backtest runs for charting overlay
 */
export async function compareBacktests(
  runIds: string[],
): Promise<BacktestComparisonResponse> {
  if (runIds.length < 2) {
    throw new Error('Must provide at least 2 run IDs to compare')
  }

  if (runIds.length > 5) {
    throw new Error('Cannot compare more than 5 runs at once')
  }

  const queryParams = runIds
    .map((id) => `run_ids=${encodeURIComponent(id)}`)
    .join('&')
  return apiRequest<BacktestComparisonResponse>(
    `/api/backtest/compare?${queryParams}`,
    {
      method: 'POST',
    },
  )
}

/**
 * Run Monte Carlo simulation on a backtest
 */
export async function runMonteCarlo(
  runId: string,
  params?: MonteCarloRequest,
): Promise<MonteCarloResponse> {
  return apiRequest<MonteCarloResponse>(
    `/api/backtest/runs/${runId}/monte-carlo`,
    {
      method: 'POST',
      body: JSON.stringify(params || { num_simulations: 1000 }),
    },
  )
}
