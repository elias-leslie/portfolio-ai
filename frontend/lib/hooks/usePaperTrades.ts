/**
 * React Query hooks for Paper Trading API
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchPaperTrades,
  fetchPaperTrade,
  fetchPaperTradeSummary,
  closePaperTrade,
  type PaperTrade,
  type PaperTradesListResponse,
  type PaperTradeSummary,
  type CloseTradeRequest,
  type CloseTradeResponse,
} from "@/lib/api/paper-trades";

// ============================================================================
// Query Keys (for cache management)
// ============================================================================

export const paperTradeKeys = {
  all: ["paper-trades"] as const,
  lists: () => [...paperTradeKeys.all, "list"] as const,
  list: (filters?: { status?: string; limit?: number; offset?: number }) =>
    [...paperTradeKeys.lists(), filters] as const,
  details: () => [...paperTradeKeys.all, "detail"] as const,
  detail: (id: string) => [...paperTradeKeys.details(), id] as const,
  summary: () => [...paperTradeKeys.all, "summary"] as const,
};

// ============================================================================
// Query Hooks (GET)
// ============================================================================

/**
 * Hook to fetch all paper trades
 * Automatically refetches every 30 seconds for real-time price updates
 */
export function usePaperTrades(options?: {
  status?: "open" | "closed" | "all";
  limit?: number;
  offset?: number;
  enabled?: boolean;
}) {
  const { status = "all", limit = 100, offset = 0, enabled = true } = options || {};

  return useQuery({
    queryKey: paperTradeKeys.list({ status, limit, offset }),
    queryFn: () => fetchPaperTrades({ status, limit, offset }),
    enabled,
    staleTime: 1000 * 15, // 15 seconds
    refetchInterval: 1000 * 30, // Refetch every 30 seconds for price updates
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
  });
}

/**
 * Hook to fetch paper trading summary statistics
 */
export function usePaperTradeSummary() {
  return useQuery({
    queryKey: paperTradeKeys.summary(),
    queryFn: fetchPaperTradeSummary,
    staleTime: 1000 * 30, // 30 seconds
    refetchInterval: 1000 * 60, // Refetch every minute
  });
}

/**
 * Hook to fetch a single paper trade
 */
export function usePaperTrade(tradeId: string) {
  return useQuery({
    queryKey: paperTradeKeys.detail(tradeId),
    queryFn: () => fetchPaperTrade(tradeId),
    enabled: !!tradeId,
    staleTime: 1000 * 15, // 15 seconds
    refetchInterval: 1000 * 30, // Refetch every 30 seconds
  });
}

// ============================================================================
// Mutation Hooks (POST/PATCH/DELETE)
// ============================================================================

/**
 * Hook to close a paper trade manually
 */
export function useClosePaperTrade() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ tradeId, request }: { tradeId: string; request: CloseTradeRequest }) =>
      closePaperTrade(tradeId, request),
    onMutate: async ({ tradeId }) => {
      // Optimistically update to show closing state
      await queryClient.cancelQueries({ queryKey: paperTradeKeys.detail(tradeId) });

      const previousTrade = queryClient.getQueryData(paperTradeKeys.detail(tradeId));

      // Show loading toast
      toast.loading("Closing trade...");

      return { previousTrade };
    },
    onSuccess: (data) => {
      // Dismiss loading toast
      toast.dismiss();

      // Show success toast with result
      toast.success(data.message);

      // Invalidate all paper trade queries to force refetch
      queryClient.invalidateQueries({
        queryKey: paperTradeKeys.lists(),
        refetchType: "active",
      });
      queryClient.invalidateQueries({
        queryKey: paperTradeKeys.summary(),
        refetchType: "active",
      });
      queryClient.invalidateQueries({
        queryKey: paperTradeKeys.detail(data.trade_id),
        refetchType: "active",
      });
    },
    onError: (error, { tradeId }, context) => {
      // Dismiss loading toast
      toast.dismiss();

      // Rollback optimistic update
      if (context?.previousTrade) {
        queryClient.setQueryData(paperTradeKeys.detail(tradeId), context.previousTrade);
      }

      // Show error toast
      toast.error(`Failed to close trade: ${error instanceof Error ? error.message : "Unknown error"}`);
    },
  });
}
