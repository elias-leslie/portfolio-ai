/**
 * React Query hooks for Portfolio API
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchInterval: 1000 * 60 * 15, // Refetch every 15 minutes for price updates
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
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchInterval: 1000 * 60 * 15, // Refetch every 15 minutes for price updates
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
    mutationFn: (data: AddPositionRequest) => addPosition(data),
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
    mutationFn: ({
      positionId,
      data,
    }: {
      positionId: string;
      data: AddPositionRequest;
    }) => updatePosition(positionId, data),
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
    mutationFn: (positionId: string) => deletePosition(positionId),
    onSuccess: () => {
      // Invalidate and refetch both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"], refetchType: 'active' });
    },
  });
}
