/**
 * React Query hooks for Backtesting API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  deleteBacktestRun,
  fetchBacktestEquity,
  fetchBacktestRun,
  fetchBacktestRuns,
  type StartBacktestRequest,
  type StartBacktestResponse,
  startBacktest,
} from '@/lib/api/backtest'

// ============================================================================
// Query Keys (for cache management)
// ============================================================================

export const backtestKeys = {
  all: ['backtests'] as const,
  lists: () => [...backtestKeys.all, 'list'] as const,
  list: () => [...backtestKeys.lists()] as const,
  details: () => [...backtestKeys.all, 'detail'] as const,
  detail: (runId: string) => [...backtestKeys.details(), runId] as const,
  equity: () => [...backtestKeys.all, 'equity'] as const,
  equityCurve: (runId: string) => [...backtestKeys.equity(), runId] as const,
}

// ============================================================================
// Query Hooks (GET)
// ============================================================================

/**
 * Hook to fetch all backtest runs
 * Automatically refetches every 30 seconds to show status updates
 */
export function useBacktestRuns(options?: { enabled?: boolean }) {
  const { enabled = true } = options || {}

  return useQuery({
    queryKey: backtestKeys.list(),
    queryFn: fetchBacktestRuns,
    enabled,
    staleTime: 1000 * 15, // 15 seconds
    refetchInterval: 1000 * 30, // Refetch every 30 seconds to show status updates
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  })
}

/**
 * Hook to fetch a single backtest run details
 */
export function useBacktestRun(runId: string, options?: { enabled?: boolean }) {
  const { enabled = true } = options || {}

  return useQuery({
    queryKey: backtestKeys.detail(runId),
    queryFn: () => fetchBacktestRun(runId),
    enabled: enabled && !!runId,
    staleTime: 1000 * 30, // 30 seconds
    refetchInterval: 1000 * 60, // Refetch every minute
  })
}

/**
 * Hook to fetch equity curve data for a backtest run
 */
export function useBacktestEquity(
  runId: string,
  options?: { enabled?: boolean },
) {
  const { enabled = true } = options || {}

  return useQuery({
    queryKey: backtestKeys.equityCurve(runId),
    queryFn: () => fetchBacktestEquity(runId),
    enabled: enabled && !!runId,
    staleTime: 1000 * 60 * 5, // 5 minutes (backtest results don't change)
  })
}

// ============================================================================
// Mutation Hooks (POST/DELETE)
// ============================================================================

/**
 * Hook to start a new backtest
 */
export function useStartBacktest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (request: StartBacktestRequest) => startBacktest(request),
    onMutate: () => {
      // Show loading toast
      toast.loading('Starting backtest...')
    },
    onSuccess: (_data: StartBacktestResponse, variables: StartBacktestRequest) => {
      // Dismiss loading toast
      toast.dismiss()

      // Show success toast
      toast.success(`Backtest started for ${variables.symbol}`)

      // Invalidate backtest runs list to force refetch
      queryClient.invalidateQueries({
        queryKey: backtestKeys.list(),
        refetchType: 'active',
      })
    },
    onError: (error) => {
      // Dismiss loading toast
      toast.dismiss()

      // Show error toast
      toast.error(
        `Failed to start backtest: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}

/**
 * Hook to delete a backtest run
 */
export function useDeleteBacktest() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (runId: string) => deleteBacktestRun(runId),
    onMutate: (runId) => {
      // Cancel ongoing queries for this run
      queryClient.cancelQueries({ queryKey: backtestKeys.detail(runId) })

      // Show loading toast
      toast.loading('Deleting backtest...')

      return { runId }
    },
    onSuccess: (_data, runId) => {
      // Dismiss loading toast
      toast.dismiss()

      // Show success toast
      toast.success('Backtest deleted successfully')

      // Remove deleted run from cache and force refetch
      queryClient.removeQueries({ queryKey: backtestKeys.detail(runId) })
      queryClient.refetchQueries({ queryKey: backtestKeys.list() })
    },
    onError: (error) => {
      // Dismiss loading toast
      toast.dismiss()

      // Show error toast
      toast.error(
        `Failed to delete backtest: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}
