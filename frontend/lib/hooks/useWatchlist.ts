/**
 * React Query hooks for watchlist data
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchWatchlistItems,
  fetchWatchlistItem,
  createWatchlistItem,
  updateWatchlistItem,
  deleteWatchlistItem,
  refreshWatchlistScores,
  fetchScoreHistory,
  type WatchlistListResponse,
  type WatchlistItem,
  type WatchlistItemCreate,
  type WatchlistItemUpdate,
  type RefreshResponse,
  type ScoreHistory,
} from "@/lib/api/watchlist";

// Query keys
export const watchlistKeys = {
  all: ["watchlist"] as const,
  lists: () => [...watchlistKeys.all, "list"] as const,
  list: (accountId: string) => [...watchlistKeys.lists(), accountId] as const,
  details: () => [...watchlistKeys.all, "detail"] as const,
  detail: (itemId: string) => [...watchlistKeys.details(), itemId] as const,
  history: (itemId: string) =>
    [...watchlistKeys.detail(itemId), "history"] as const,
};

/**
 * Hook to fetch all watchlist items for an account
 */
export function useWatchlist(accountId: string) {
  return useQuery<WatchlistListResponse, Error>({
    queryKey: watchlistKeys.list(accountId),
    queryFn: () => fetchWatchlistItems(accountId),
    staleTime: 1000 * 60 * 5, // 5 minutes
    enabled: !!accountId,
  });
}

/**
 * Hook to fetch a single watchlist item
 */
export function useWatchlistItem(itemId: string) {
  return useQuery<WatchlistItem, Error>({
    queryKey: watchlistKeys.detail(itemId),
    queryFn: () => fetchWatchlistItem(itemId),
    enabled: !!itemId,
  });
}

/**
 * Hook to fetch score history for an item
 */
export function useScoreHistory(itemId: string) {
  return useQuery<ScoreHistory[], Error>({
    queryKey: watchlistKeys.history(itemId),
    queryFn: () => fetchScoreHistory(itemId),
    enabled: !!itemId,
  });
}

/**
 * Hook to add a ticker to the watchlist
 */
export function useAddTicker() {
  const queryClient = useQueryClient();

  return useMutation<WatchlistItem, Error, WatchlistItemCreate>({
    mutationFn: createWatchlistItem,
    onSuccess: (data) => {
      // Invalidate watchlist query for this account
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(data.account_id),
      });
    },
  });
}

/**
 * Hook to update a watchlist item
 */
export function useUpdateWatchlistItem() {
  const queryClient = useQueryClient();

  return useMutation<
    WatchlistItem,
    Error,
    { itemId: string; data: WatchlistItemUpdate }
  >({
    mutationFn: ({ itemId, data }) => updateWatchlistItem(itemId, data),
    onSuccess: (data) => {
      // Invalidate both list and detail queries
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(data.account_id),
      });
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.detail(data.id),
      });
    },
  });
}

/**
 * Hook to delete a watchlist item
 */
export function useDeleteWatchlistItem() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, { itemId: string; accountId: string }>({
    mutationFn: ({ itemId }) => deleteWatchlistItem(itemId),
    onSuccess: (_, variables) => {
      // Invalidate watchlist query for this account
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(variables.accountId),
      });
    },
  });
}

/**
 * Hook to manually refresh watchlist scores
 */
export function useRefreshWatchlist() {
  const queryClient = useQueryClient();

  return useMutation<RefreshResponse, Error, string>({
    mutationFn: refreshWatchlistScores,
    onSuccess: (_, accountId) => {
      // Invalidate watchlist query to refetch with new scores
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(accountId),
      });
    },
  });
}
