/**
 * React Query hooks for recommendations API
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getRecommendations,
  getRecommendedSymbols,
  paperTradeRecommendation,
  trackInPortfolio,
} from "@/lib/api/recommendations";

// ============================================================================
// Query Keys
// ============================================================================

export const recommendationKeys = {
  all: ["recommendations"] as const,
  lists: () => [...recommendationKeys.all, "list"] as const,
  list: (params?: {
    min_strength?: number;
    limit?: number;
    signal_type?: string;
    portfolio_size?: number;
    position_pct?: number;
  }) => [...recommendationKeys.lists(), params] as const,
  symbols: (minStrength?: number) =>
    [...recommendationKeys.all, "symbols", minStrength] as const,
};

// ============================================================================
// Query Hooks
// ============================================================================

export function useRecommendations(params?: {
  min_strength?: number;
  limit?: number;
  signal_type?: "BUY" | "SELL" | "all";
  portfolio_size?: number;
  position_pct?: number;
}) {
  return useQuery({
    queryKey: recommendationKeys.list(params),
    queryFn: () => getRecommendations(params),
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // 1 minute
  });
}

export function useRecommendedSymbols(minStrength = 5) {
  return useQuery({
    queryKey: recommendationKeys.symbols(minStrength),
    queryFn: () => getRecommendedSymbols(minStrength),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

export function usePaperTrade() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      symbol,
      strategyId,
    }: {
      symbol: string;
      strategyId: string;
    }) => paperTradeRecommendation(symbol, strategyId),

    onMutate: ({ symbol }) => {
      toast.loading(`Creating paper trade for ${symbol}...`, { id: `paper-${symbol}` });
    },

    onSuccess: (data, { symbol }) => {
      toast.dismiss(`paper-${symbol}`);
      toast.success(data.message);

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: recommendationKeys.lists() });
      queryClient.invalidateQueries({ queryKey: ["paper-trades"] });
    },

    onError: (error, { symbol }) => {
      toast.dismiss(`paper-${symbol}`);
      toast.error(
        `Failed to paper trade ${symbol}: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });
}

export function useTrackInPortfolio() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      symbol,
      strategyId,
      accountId,
      shares,
    }: {
      symbol: string;
      strategyId: string;
      accountId: string;
      shares: number;
    }) => trackInPortfolio(symbol, strategyId, accountId, shares),

    onMutate: ({ symbol }) => {
      toast.loading(`Adding ${symbol} to portfolio...`, { id: `track-${symbol}` });
    },

    onSuccess: (data, { symbol }) => {
      toast.dismiss(`track-${symbol}`);
      toast.success(data.message);

      // Invalidate relevant queries
      queryClient.invalidateQueries({ queryKey: recommendationKeys.lists() });
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },

    onError: (error, { symbol }) => {
      toast.dismiss(`track-${symbol}`);
      toast.error(
        `Failed to add ${symbol}: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });
}
