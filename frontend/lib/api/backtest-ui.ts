/**
 * Backtesting UI API client functions
 *
 * Note: Core backtest functionality is in backtest.ts
 * This module adds UI-specific functions like comparison
 */

import { apiRequest } from "./client";
import type { BacktestEquity } from "./backtest";

// Re-export core backtest types and functions
export type {
  BacktestRun,
  BacktestResult,
  BacktestEquity,
  BacktestTrade,
  StartBacktestRequest,
  StartBacktestResponse,
} from "./backtest";

export {
  fetchBacktestRuns,
  fetchBacktestRun,
  fetchBacktestEquity,
  startBacktest,
  deleteBacktestRun,
} from "./backtest";

// ============================================================================
// Additional Types for UI
// ============================================================================

export interface NormalizedEquityPoint {
  date: string;
  cumulative_return_pct: string; // Decimal as string
}

export interface RunMetrics {
  run_id: string;
  symbol: string;
  strategy_name: string;
  start_date: string;
  end_date: string;
  total_return_pct: string | null;
  sharpe_ratio: string | null;
  max_drawdown_pct: string | null;
  win_rate: string | null;
  num_trades: number | null;
  profit_factor: string | null;
  return_rank: number | null;
  sharpe_rank: number | null;
  drawdown_rank: number | null;
}

export interface BacktestComparisonResponse {
  equity_curves: Record<string, NormalizedEquityPoint[]>;
  metrics: RunMetrics[];
  correlation_matrix: Record<string, Record<string, number>> | null;
}

export interface MonteCarloStatistics {
  num_simulations: number;
  percentile_5: number;
  percentile_25: number;
  percentile_50: number;
  percentile_75: number;
  percentile_95: number;
  probability_of_loss: number;
  value_at_risk_95: number;
  expected_shortfall: number;
  mean_return: number;
  std_dev: number;
  skewness: number;
  kurtosis: number;
  original_return: number;
}

export interface HistogramBin {
  bin_start: number;
  bin_end: number;
  frequency: number;
}

export interface EquityBand {
  step: number;
  p5: number;
  p50: number;
  p95: number;
}

export interface MonteCarloRequest {
  num_simulations?: number;
  seed?: number;
}

export interface MonteCarloResponse {
  statistics: MonteCarloStatistics;
  histogram_data: HistogramBin[];
  equity_bands: EquityBand[];
  created_at: string;
}

// ============================================================================
// UI-Specific API Functions
// ============================================================================

/**
 * Compare multiple backtest runs for charting overlay
 */
export async function compareBacktests(
  runIds: string[]
): Promise<BacktestComparisonResponse> {
  if (runIds.length < 2) {
    throw new Error("Must provide at least 2 run IDs to compare");
  }

  if (runIds.length > 5) {
    throw new Error("Cannot compare more than 5 runs at once");
  }

  const queryParams = runIds.map((id) => `run_ids=${encodeURIComponent(id)}`).join("&");
  return apiRequest<BacktestComparisonResponse>(`/api/backtest/compare?${queryParams}`, {
    method: "POST",
  });
}

/**
 * Run Monte Carlo simulation on a backtest
 */
export async function runMonteCarlo(
  runId: string,
  params?: MonteCarloRequest
): Promise<MonteCarloResponse> {
  return apiRequest<MonteCarloResponse>(`/api/backtest/runs/${runId}/monte-carlo`, {
    method: "POST",
    body: JSON.stringify(params || { num_simulations: 1000 }),
  });
}
