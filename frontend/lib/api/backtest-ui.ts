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

export interface BacktestComparisonResponse {
  [runId: string]: BacktestEquity[];
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
