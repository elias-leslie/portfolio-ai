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
import { toast } from "sonner";

// Query keys
export const watchlistKeys = {
  all: ["watchlist"] as const,
  lists: () => [...watchlistKeys.all, "list"] as const,
  list: () => [...watchlistKeys.lists()] as const,
  details: () => [...watchlistKeys.all, "detail"] as const,
  detail: (itemId: string) => [...watchlistKeys.details(), itemId] as const,
  history: (itemId: string) =>
    [...watchlistKeys.detail(itemId), "history"] as const,
  refreshStatus: () => [...watchlistKeys.all, "refresh-status"] as const,
};

/**
 * Hook to fetch all watchlist items
 * Auto-refreshes based on user preferences (default: 5 minutes)
 *
 * Watchlist is user-level (not account-specific).
 */
export function useWatchlist() {
  // Fetch preferences to get refresh interval
  const { data: preferences } = useQuery({
    queryKey: ["preferences"],
    queryFn: fetchPreferences,
    staleTime: 1000 * 60 * 5, // Reduced to 5 min to pick up changes faster
  });

  // Use preference or fallback to 5 minutes
  const refreshMinutes = preferences?.watchlist_refresh_minutes ?? 5;
  const refreshIntervalMs = refreshMinutes * 60 * 1000; // Convert to milliseconds

  // Query key should NOT include refreshIntervalMs - that causes unnecessary cache
  // invalidation and resets UI state (modals, etc). The interval is a query option,
  // not part of the query identity. React Query handles interval changes correctly.
  return useQuery<WatchlistListResponse, Error>({
    queryKey: watchlistKeys.list(),
    queryFn: () => fetchWatchlistItems(),
    staleTime: 0, // Always consider data stale to enable frequent updates
    refetchInterval: refreshIntervalMs, // Refetch based on user preference
    refetchIntervalInBackground: true, // Enable background refresh
    refetchOnWindowFocus: true, // Refetch when window regains focus
    refetchOnMount: "always", // CRITICAL FIX: Always refetch to prevent stale cache after deletions
    structuralSharing: true, // Only update changed data, preserves UI state
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
    mutationFn: async (data) => {
      const promise = createWatchlistItem(data);
      toast.promise(promise, {
        loading: `Adding ${data.symbol.toUpperCase()} to watchlist...`,
        success: (item) => `${item.symbol} added to watchlist`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to add ticker";
          return `Failed to add ${data.symbol.toUpperCase()}: ${errorMsg}`;
        },
      });
      return promise;
    },
    onSuccess: () => {
      // Invalidate and refetch watchlist query
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(),
        refetchType: 'active', // Force immediate refetch of active queries
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
      // Invalidate and refetch both list and detail queries
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(),
        refetchType: 'active', // Force immediate refetch of active queries
      });
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.detail(data.id),
        refetchType: 'active', // Force immediate refetch of active queries
      });
    },
  });
}

/**
 * Hook to delete a watchlist item with optimistic updates
 */
type WatchlistMutationContext = { previousData?: WatchlistListResponse } | undefined;

export function useDeleteWatchlistItem() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string, WatchlistMutationContext>({
    mutationFn: async (itemId) => {
      // Get the item details for toast message
      const previousData = queryClient.getQueryData<WatchlistListResponse>(
        watchlistKeys.list()
      );
      const item = previousData?.items.find((i) => i.id === itemId);
      const symbol = item?.symbol || "ticker";

      const promise = deleteWatchlistItem(itemId);
      toast.promise(promise, {
        loading: `Removing ${symbol} from watchlist...`,
        success: `${symbol} removed from watchlist`,
        error: (error) => {
          const errorMsg = error instanceof Error ? error.message : "Failed to delete ticker";
          return `Failed to remove ${symbol}: ${errorMsg}`;
        },
      });
      return promise;
    },
    // Optimistic update: Remove item from cache immediately
    onMutate: async (itemId) => {
      // Cancel any outgoing refetches to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: watchlistKeys.list() });

      // Snapshot previous value for rollback
      const previousData = queryClient.getQueryData<WatchlistListResponse>(
        watchlistKeys.list()
      );

      // Optimistically update cache (remove item)
      queryClient.setQueryData<WatchlistListResponse>(
        watchlistKeys.list(),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.filter((item) => item.id !== itemId),
          };
        }
      );

      // Return snapshot for potential rollback
      return { previousData };
    },
    onSuccess: () => {
      // Invalidate and refetch watchlist query to ensure sync
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(),
        refetchType: 'active',
      });
    },
    onError: (error, itemId, context) => {
      // ROLLBACK: Restore previous data on error
      if (context?.previousData) {
        queryClient.setQueryData(watchlistKeys.list(), context.previousData);
      }

      // CRITICAL FIX (2025-11-09): On 404/410 errors, REMOVE stale cache and force refetch
      // Prevents showing deleted items with old IDs that no longer exist
      // Context: Data loss incident - frontend showed deleted items for hours due to stale cache
      if (
        error.message.includes('404') ||
        error.message.includes('410') ||
        error.message.includes('not found')
      ) {
        // REMOVE the stale cache entirely (don't just invalidate)
        queryClient.removeQueries({
          queryKey: watchlistKeys.list(),
        });
        // Force immediate refetch
        queryClient.refetchQueries({
          queryKey: watchlistKeys.list(),
          type: 'active',
        });
      }
    },
  });
}

/**
 * Hook to manually refresh watchlist scores
 */
export function useRefreshWatchlist() {
  const queryClient = useQueryClient();

  return useMutation<RefreshResponse, Error, void>({
    mutationFn: refreshWatchlistScores,
    onSuccess: () => {
      // Invalidate and refetch watchlist query to show new scores
      queryClient.invalidateQueries({
        queryKey: watchlistKeys.list(),
        refetchType: 'active', // Force immediate refetch of active queries
      });
    },
  });
}

/**
 * Hook to poll refresh status for the watchlist
 * Polls every 1 second when refresh is active or recently completed
 */
export function useRefreshStatus(enabled = true) {
  return useQuery<RefreshStatus, Error>({
    queryKey: watchlistKeys.refreshStatus(),
    queryFn: () => fetchRefreshStatus(),
    enabled,
    refetchInterval: 1000, // Poll every 1 second to catch short refreshes
    refetchIntervalInBackground: false,
    staleTime: 0, // Always consider stale to enable polling
  });
}
