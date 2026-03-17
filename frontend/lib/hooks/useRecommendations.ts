/**
 * React Query hooks for recommendations API
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  getRecommendations,
  trackInPortfolio,
} from '@/lib/api/recommendations'

// ============================================================================
// Query Keys
// ============================================================================

export const recommendationKeys = {
  all: ['recommendations'] as const,
  lists: () => [...recommendationKeys.all, 'list'] as const,
  list: (params?: {
    minStrength?: number
    limit?: number
    signalType?: string
    portfolioSize?: number
    positionPct?: number
  }) => [...recommendationKeys.lists(), params] as const,
}

// ============================================================================
// Query Hooks
// ============================================================================

export function useRecommendations(params?: {
  minStrength?: number
  limit?: number
  signalType?: 'BUY' | 'SELL' | 'all'
  portfolioSize?: number
  positionPct?: number
}) {
  return useQuery({
    queryKey: recommendationKeys.list(params),
    queryFn: () => getRecommendations(params),
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // 1 minute
  })
}

// ============================================================================
// Mutation Hooks
// ============================================================================

export function useTrackInPortfolio() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      symbol,
      strategyId,
      accountId,
      shares,
    }: {
      symbol: string
      strategyId: string
      accountId: string
      shares: number
    }) => trackInPortfolio(symbol, strategyId, accountId, shares),

    onMutate: ({ symbol }) => {
      toast.loading(`Adding ${symbol} to portfolio...`, {
        id: `track-${symbol}`,
      })
    },

    onSuccess: (data, { symbol }) => {
      toast.dismiss(`track-${symbol}`)
      toast.success(data.message)

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: recommendationKeys.lists() })
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
    },

    onError: (error, { symbol }) => {
      toast.dismiss(`track-${symbol}`)
      toast.error(
        `Failed to add ${symbol}: ${error instanceof Error ? error.message : 'Unknown error'}`,
      )
    },
  })
}
