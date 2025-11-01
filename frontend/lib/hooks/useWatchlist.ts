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
  fetchRefreshStatus,
  type WatchlistListResponse,
  type WatchlistItem,
  type WatchlistItemCreate,
  type WatchlistItemUpdate,
  type RefreshResponse,
  type ScoreHistory,
  type ScoreHistoryResponse,
  type RefreshStatus,
} from "@/lib/api/watchlist";
import { fetchPreferences } from "@/lib/api/preferences";

// Query keys
export const watchlistKeys = {
  all: ["watchlist"] as const,
  lists: () => [...watchlistKeys.all, "list"] as const,
  list: (accountId: string) => [...watchlistKeys.lists(), accountId] as const,
  details: () => [...watchlistKeys.all, "detail"] as const,
  detail: (itemId: string) => [...watchlistKeys.details(), itemId] as const,
  history: (itemId: string) =>
    [...watchlistKeys.detail(itemId), "history"] as const,
  refreshStatus: (accountId: string) =>
    [...watchlistKeys.all, "refresh-status", accountId] as const,
};

/**
 * Hook to fetch all watchlist items for an account
 * Auto-refreshes based on user preferences (default: 5 minutes)
 */
export function useWatchlist(accountId: string) {
  // Fetch preferences to get refresh interval
  const { data: preferences } = useQuery({
    queryKey: ["preferences"],
    queryFn: fetchPreferences,
    staleTime: 1000 * 60 * 5, // Reduced to 5 min to pick up changes faster
  });

  // Use preference or fallback to 5 minutes
  const refreshMinutes = preferences?.watchlist_refresh_minutes ?? 5;
  const refreshIntervalMs = refreshMinutes * 60 * 1000; // Convert to milliseconds

  // Include refreshIntervalMs in query key to force new query when interval changes
  // This ensures React Query creates a fresh query observer with the correct interval
  return useQuery<WatchlistListResponse, Error>({
    queryKey: [...watchlistKeys.list(accountId), refreshIntervalMs],
    queryFn: () => fetchWatchlistItems(accountId),
    staleTime: 0, // Always consider data stale to enable frequent updates
    refetchInterval: refreshIntervalMs, // Refetch based on user preference
    refetchIntervalInBackground: true, // Enable background refresh
    refetchOnWindowFocus: true, // Refetch when window regains focus
    refetchOnMount: true, // Refetch when component mounts
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
  return useQuery<ScoreHistoryResponse, Error>({
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

/**
 * Hook to poll refresh status for an account's watchlist
 * Polls every 1 second when refresh is active or recently completed
 */
export function useRefreshStatus(accountId: string, enabled = true) {
  return useQuery<RefreshStatus, Error>({
    queryKey: watchlistKeys.refreshStatus(accountId),
    queryFn: () => fetchRefreshStatus(accountId),
    enabled: !!accountId && enabled,
    refetchInterval: 1000, // Poll every 1 second to catch short refreshes
    refetchIntervalInBackground: false,
    staleTime: 0, // Always consider stale to enable polling
  });
}
