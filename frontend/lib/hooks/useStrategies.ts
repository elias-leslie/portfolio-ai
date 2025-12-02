/**
 * React Query hooks for strategies API
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  getStrategies,
  getStrategy,
  generateStrategy,
  generateStrategiesBatch,
  updateStrategyStatus,
  getStrategyPerformance,
  type GenerateStrategyRequest,
  type GenerateBatchRequest,
  type UpdateStrategyStatusRequest,
} from "@/lib/api/strategies";

// ============================================================================
// Query Keys
// ============================================================================

export const strategyKeys = {
  all: ["strategies"] as const,
  lists: () => [...strategyKeys.all, "list"] as const,
  list: (params?: { symbol?: string; status?: string; strategy_type?: string }) =>
    [...strategyKeys.lists(), params] as const,
  details: () => [...strategyKeys.all, "detail"] as const,
  detail: (strategyId: string) => [...strategyKeys.details(), strategyId] as const,
  performance: (strategyId: string) =>
    [...strategyKeys.all, "performance", strategyId] as const,
};

// ============================================================================
// Query Hooks
// ============================================================================

export function useStrategies(params?: {
  symbol?: string;
  status?: "testing" | "active" | "archived";
  strategy_type?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: strategyKeys.list(params),
    queryFn: () => getStrategies(params),
    staleTime: 30_000, // 30 seconds
    refetchInterval: 60_000, // 1 minute
  });
}

export function useStrategy(strategyId: string | null) {
  return useQuery({
    queryKey: strategyKeys.detail(strategyId || ""),
    queryFn: () => getStrategy(strategyId!),
    enabled: !!strategyId,
    staleTime: 30_000,
  });
}

export function useStrategyPerformance(strategyId: string | null) {
  return useQuery({
    queryKey: strategyKeys.performance(strategyId || ""),
    queryFn: () => getStrategyPerformance(strategyId!),
    enabled: !!strategyId,
    staleTime: 60_000,
  });
}

// ============================================================================
// Mutation Hooks
// ============================================================================

export function useGenerateStrategy() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: GenerateStrategyRequest) => generateStrategy(request),

    onMutate: ({ symbol }) => {
      toast.loading(`Generating strategy for ${symbol}...`, { id: `generate-${symbol}` });
    },

    onSuccess: (data, { symbol }) => {
      toast.dismiss(`generate-${symbol}`);

      if (data.status === "completed") {
        toast.success(`Strategy generated for ${symbol}`);
      } else if (data.status === "blocked") {
        toast.info(data.message || `Strategy generation blocked for ${symbol}`);
      } else if (data.status === "skipped") {
        toast.info(`Strategy already exists for ${symbol}`);
      } else {
        toast.error(data.error_message || `Strategy generation failed for ${symbol}`);
      }

      queryClient.invalidateQueries({ queryKey: strategyKeys.lists() });
    },

    onError: (error, { symbol }) => {
      toast.dismiss(`generate-${symbol}`);
      toast.error(
        `Failed to generate strategy for ${symbol}: ${
          error instanceof Error ? error.message : "Unknown error"
        }`
      );
    },
  });
}

export function useGenerateStrategiesBatch() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: GenerateBatchRequest) => generateStrategiesBatch(request),

    onMutate: () => {
      toast.loading("Generating strategies...", { id: "generate-batch" });
    },

    onSuccess: (data) => {
      toast.dismiss("generate-batch");

      const generated = data.strategies_generated || 0;
      const processed = data.symbols_processed || data.symbols_evaluated || 0;

      if (generated > 0) {
        toast.success(`Generated ${generated} strategies (${processed} symbols processed)`);
      } else {
        toast.info(`No new strategies generated (${processed} symbols checked)`);
      }

      queryClient.invalidateQueries({ queryKey: strategyKeys.lists() });
    },

    onError: (error) => {
      toast.dismiss("generate-batch");
      toast.error(
        `Batch generation failed: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });
}

export function useUpdateStrategyStatus() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      strategyId,
      request,
    }: {
      strategyId: string;
      request: UpdateStrategyStatusRequest;
    }) => updateStrategyStatus(strategyId, request),

    onSuccess: (data, { strategyId }) => {
      toast.success(data.message);
      queryClient.invalidateQueries({ queryKey: strategyKeys.lists() });
      queryClient.invalidateQueries({ queryKey: strategyKeys.detail(strategyId) });
    },

    onError: (error) => {
      toast.error(
        `Failed to update strategy: ${error instanceof Error ? error.message : "Unknown error"}`
      );
    },
  });
}
