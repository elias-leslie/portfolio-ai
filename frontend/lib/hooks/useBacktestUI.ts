/**
 * React Query hooks for Backtesting UI
 *
 * Note: Core backtest hooks are in useBacktest.ts
 * This module adds UI-specific hooks like comparison
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { compareBacktests, runMonteCarlo, type BacktestComparisonResponse, type MonteCarloResponse, type MonteCarloRequest } from "@/lib/api/backtest-ui";

// Re-export core backtest hooks
export {
  useBacktestRuns,
  useBacktestRun,
  useBacktestEquity,
  useStartBacktest,
  useDeleteBacktest,
  backtestKeys,
} from "./useBacktest";

// ============================================================================
// Additional Query Keys for UI
// ============================================================================

export const backtestUIKeys = {
  comparisons: () => ["backtest-comparisons"] as const,
  comparison: (runIds: string[]) => [...backtestUIKeys.comparisons(), runIds.sort()] as const,
};

// ============================================================================
// UI-Specific Query Hooks
// ============================================================================

/**
 * Hook to compare multiple backtest runs
 * Fetches equity curves for all runs for chart overlay
 */
export function useCompareBacktests(runIds: string[], options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== false && runIds.length >= 2 && runIds.length <= 5;

  return useQuery({
    queryKey: backtestUIKeys.comparison(runIds),
    queryFn: () => compareBacktests(runIds),
    enabled,
    staleTime: 1000 * 60 * 5, // 5 minutes (backtest results don't change)
  });
}

/**
 * Hook to run Monte Carlo simulation on a backtest
 * Returns mutation for triggering simulation on demand
 */
export function useMonteCarloSimulation(runId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (params?: MonteCarloRequest) => runMonteCarlo(runId, params),
    onSuccess: () => {
      // Optionally invalidate backtest data to refresh UI
      queryClient.invalidateQueries({ queryKey: ["backtest", runId] });
    },
  });
}
