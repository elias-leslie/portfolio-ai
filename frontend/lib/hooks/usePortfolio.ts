/**
 * React Query hooks for Portfolio API
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AddPositionRequest,
  CreateAccountRequest,
  addPosition,
  createAccount,
  deleteAccount,
  deletePosition,
  fetchAccounts,
  fetchAnalytics,
  fetchPortfolio,
  updatePosition,
} from "../api/portfolio";

/**
 * Hook to fetch portfolio positions with current values
 * Automatically refetches every 15 minutes to update prices
 */
export function usePortfolio(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: fetchPortfolio,
    enabled: options?.enabled !== false, // Default to true
    staleTime: 1000 * 60 * 2, // 2 minutes (reduced from 5min for fresher data)
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes (reduced from 15min)
  });
}

/**
 * Hook to fetch portfolio analytics
 * Automatically refetches every 15 minutes to update with latest prices
 */
export function usePortfolioAnalytics() {
  return useQuery({
    queryKey: ["portfolio", "analytics"],
    queryFn: fetchAnalytics,
    staleTime: 1000 * 60 * 2, // 2 minutes (reduced from 5min for fresher data)
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes (reduced from 15min)
  });
}

/**
 * Hook to fetch all accounts
 */
export function useAccounts() {
  return useQuery({
    queryKey: ["accounts"],
    queryFn: fetchAccounts,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * Hook to create a new account
 */
export function useCreateAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateAccountRequest) => createAccount(data),
    onSuccess: () => {
      // Invalidate and refetch accounts and portfolio queries
      queryClient.invalidateQueries({ queryKey: ["accounts"], refetchType: 'active' });
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}

/**
 * Hook to delete an account
 */
export function useDeleteAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (accountId: string) => deleteAccount(accountId),
    onSuccess: () => {
      // Invalidate and refetch all portfolio-related queries
      queryClient.invalidateQueries({ queryKey: ["accounts"], refetchType: 'active' });
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}

/**
 * Hook to add or update a position
 */
export function useAddPosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: AddPositionRequest) => {
      const promise = addPosition(data);
      const positionTypeLabel = data.positionType === "paper" ? "paper" : "live";
      toast.promise(promise, {
        loading: `Adding ${data.symbol.toUpperCase()} position...`,
        success: (position) =>
          `${position.symbol} ${positionTypeLabel} position added (${data.shares} shares @ $${data.costBasis.toFixed(2)})`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to add position";
          return `Failed to add ${data.symbol.toUpperCase()}: ${errorMsg}`;
        },
      });
      return promise;
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}

/**
 * Hook to update a position
 */
export function useUpdatePosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      positionId,
      data,
    }: {
      positionId: string;
      data: AddPositionRequest;
    }) => {
      const promise = updatePosition(positionId, data);
      toast.promise(promise, {
        loading: `Updating ${data.symbol.toUpperCase()} position...`,
        success: (position) =>
          `${position.symbol} position updated (${data.shares} shares @ $${data.costBasis.toFixed(2)})`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to update position";
          return `Failed to update ${data.symbol.toUpperCase()}: ${errorMsg}`;
        },
      });
      return promise;
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}

/**
 * Hook to delete a position
 */
export function useDeletePosition() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (positionId: string) => {
      // Get position details for toast message before deleting
      const portfolioData = queryClient.getQueryData<{
        positions: Array<{ id: string; symbol: string; shares: number }>;
      }>(["portfolio"]);
      const position = portfolioData?.positions.find((p) => p.id === positionId);
      const symbol = position?.symbol || "position";

      const promise = deletePosition(positionId);
      toast.promise(promise, {
        loading: `Deleting ${symbol} position...`,
        success: `${symbol} position deleted`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to delete position";
          return `Failed to delete ${symbol}: ${errorMsg}`;
        },
      });
      return promise;
    },
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}
