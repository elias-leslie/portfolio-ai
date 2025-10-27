/**
 * React Query hooks for Portfolio API
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AddPositionRequest,
  CreateAccountRequest,
  PortfolioAnalytics,
  PortfolioResponse,
  addPosition,
  createAccount,
  deletePosition,
  fetchAnalytics,
  fetchPortfolio,
} from "../api/portfolio";

/**
 * Hook to fetch portfolio positions with current values
 */
export function usePortfolio() {
  return useQuery({
    queryKey: ["portfolio"],
    queryFn: fetchPortfolio,
    staleTime: 1000 * 60 * 1, // 1 minute
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
  });
}

/**
 * Hook to fetch portfolio analytics
 */
export function usePortfolioAnalytics() {
  return useQuery({
    queryKey: ["portfolio", "analytics"],
    queryFn: fetchAnalytics,
    staleTime: 1000 * 60 * 1, // 1 minute
    refetchInterval: 1000 * 60 * 5, // Refetch every 5 minutes
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
      // Invalidate portfolio query to refetch
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
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
      // Invalidate both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
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
      // Invalidate both portfolio and analytics queries
      queryClient.invalidateQueries({ queryKey: ["portfolio"] });
    },
  });
}
